# YouTube-Music-Adapter — Design-Spezifikation

**Datum:** 2026-06-12
**Status:** Design, genehmigt für Implementierungsplanung
**Autor:** Paul Weber (brainstorming mit Claude)

## Überblick

linkhop unterstützt bisher Spotify, Deezer und Tidal. YouTube Music war im
ursprünglichen V1-Design ([2026-04-18-linkhop-design.md](2026-04-18-linkhop-design.md))
bereits vorgesehen und steht im README als unterstützt — der Adapter wurde
aber nie implementiert. Dieses Spec schließt die Lücke: ein vierter
Service-Adapter auf Basis von `ytmusicapi`, ohne Authentifizierung.

## Ziele und Nicht-Ziele

### Ziele

- **Bidirektionale Konvertierung** mit YouTube Music als Quelle und Ziel,
  für Tracks, Alben und Artists
- **Keine Credentials**: unauthentifizierte `ytmusicapi`-Nutzung — kein
  Secret, keine Cookie-Rotation, Helm-Chart bleibt einfach
- **Kein Eingriff** in `matching.py` oder `pipeline.py` — der Adapter fügt
  sich in die bestehende Architektur ein

### Nicht-Ziele

- **Keine youtube.com/youtu.be-Links**: nur `music.youtube.com` wird als
  Eingabe akzeptiert. Normale YouTube-Videos sind mehrheitlich keine Musik;
  die Ambiguität ist den Reichweitengewinn nicht wert.
- **Keine Playlists** (wie in V1 generell): normale Playlist-Links
  (`list=PL…`) bleiben `UnsupportedUrlError`. Nur auto-generierte
  Album-Playlists (`list=OLAK5uy_…`) werden als Album interpretiert.
- **Keine Cookie-/OAuth-Auth in V1**: kann nachgerüstet werden, falls
  YouTube Server-IPs drosselt (siehe Risiken).

## Entscheidungsgrundlage: Ansatzwahl

| Ansatz | Bewertung |
|---|---|
| **`ytmusicapi` + `asyncio.to_thread` (gewählt)** | Gepflegte Library kapselt das undokumentierte InnerTube-Protokoll; Community fixt Breakage. Sync-Library, daher Thread-Wrapping. |
| InnerTube direkt via `httpx` | Konsistent async, keine Dependency — aber undokumentiertes, instabiles JSON-Parsing müsste selbst gepflegt werden. Zu teuer. |
| YouTube Data API v3 | Offiziell, aber Quota (~100 Suchen/Tag bei Default-Kontingent), kein ISRC/UPC, Alben/Artists nur als Playlists/Channels. Ungeeignet. |

## Architektur

### Adapter (`backend/src/linkhop/adapters/youtube_music.py`)

- Klasse `YouTubeMusicAdapter`, `service_id = "youtube_music"`,
  `AdapterCapabilities(track=True, album=True, artist=True)`
- Konstruktor erhält eine `YTMusic`-Instanz (unauthentifiziert, erzeugt in
  `deps.py`) — injizierbar für Tests
- `ytmusicapi` ist synchron (`requests`-basiert): jeder Library-Aufruf läuft
  durch `asyncio.to_thread()`, damit der Event-Loop nicht blockiert

### `resolve(parsed)`

| Typ | Aufruf | Besonderheit |
|---|---|---|
| Track | `get_song(videoId)` | `lengthSeconds` × 1000 → `duration_ms`; kein ISRC |
| Album | `get_album(browseId)` | ID-Übersetzung nötig, siehe unten; kein UPC |
| Artist | `get_artist(channelId)` | `UC…`-Channel-IDs |

**Album-ID-Dualität:** Geteilte URLs enthalten eine Audio-Playlist-ID
(`OLAK5uy_…`), `ytmusicapi`-Suchergebnisse liefern eine Browse-ID
(`MPREb_…`). `resolve()` erkennt die Form am Präfix: bei `OLAK5uy_` wird
zuerst `get_album_browse_id()` zur Übersetzung aufgerufen, dann
`get_album()`. Beide Formen müssen funktionieren, weil die Pipeline in
`_score_hit` Suchkandidaten per `resolve()` nachlädt — dort kommen
Browse-IDs an, während User-Eingaben Playlist-IDs liefern.

Generierte URLs (Ausgaberichtung):

- Track: `https://music.youtube.com/watch?v=<videoId>`
- Album: `https://music.youtube.com/playlist?list=<audioPlaylistId>`
  (aus der `get_album`-Antwort)
- Artist: `https://music.youtube.com/channel/<channelId>`

### `search(meta, target_type)`

- `search(query, filter="songs"|"albums"|"artists", limit=3)`, Query aus
  Titel + erstem Artist
- Die ersten 3 Treffer als `SearchHit` mit `confidence=0.0`,
  `match="metadata"` (defensiv slicen — `ytmusicapi` behandelt `limit`
  als Richtwert, nicht als harte Grenze)
- **Keine ISRC/UPC-Pfade**: YouTube Music exponiert keine Industry-IDs.
  Die ID-Shortcuts der anderen Adapter entfallen ersatzlos.

### URL-Parser (`url_parser.py`)

Nur Host `music.youtube.com`:

| Muster | Typ | Hinweis |
|---|---|---|
| `/watch?v=<id>` | track | ID steckt im Query-Parameter — der Parser braucht erstmals Query-Parsing (`parse_qs`) |
| `/playlist?list=OLAK5uy_<…>` | album | nur `OLAK5uy_`-Präfix; `PL…` u. a. → `UnsupportedUrlError` |
| `/browse/<MPREb_…>` | album | linkhop erzeugt selbst `/browse/`-Ziel-URLs für Album-Suchtreffer (dort ist nur die Browse-ID bekannt) — der Round-Trip eigener Links muss parsen |
| `/channel/<UC…>` | artist | |

## Matching und Datenfluss

Ohne ISRC/UPC läuft Matching in beide Richtungen immer über den bestehenden
Metadaten-Pfad (`score_candidate`: Titel-Similarity + Artist-Overlap,
+ Dauer bei Tracks). `get_song` liefert die Dauer, was die Track-Genauigkeit
stützt.

**Bewusste Konsequenz:** YouTube-Music-Ergebnisse erreichen nie
`confidence = 1.0`. Gute Treffer landen im `ok`-Bucket (≥ 0.7), Grenzfälle
zeigen das `~match`-Badge (`ok_low`). Das ist die ehrliche Abbildung der
Datenlage, keine zu behebende Schwäche.

## Fehlerbehandlung

- „Nicht gefunden“ → `None` (`resolve`) bzw. `[]` (`search`)
- Alle anderen `ytmusicapi`-Exceptions → `AdapterError("youtube_music", …)`
- Die Pipeline degradiert damit pro Ziel auf `status: "error"`, ohne die
  Gesamt-Konvertierung zu beeinträchtigen — wichtig bei einer inoffiziellen
  API, die ohne Ankündigung brechen kann

## Konfiguration und Rollout

- `config.py`: `enable_youtube_music: bool = True` — kein Credential-Check
  in `deps.py`, da auth-frei
- `routes/services.py`: `_NAMES["youtube_music"] = "YouTube Music"`
- Frontend `ServiceItem.svelte`: `--brand: #ff0000`
- Helm-Chart: `youtubeMusic.enabled`-Value analog zu den anderen Services,
  ohne Secret-Keys
- `pyproject.toml`: neue Dependency `ytmusicapi`
- READMEs: Haupt-README-Tabelle stimmt danach; `backend/README.md`
  Env-Var-Referenz um `LINKHOP_ENABLE_YOUTUBE_MUSIC` ergänzen

## Tests

Nach bestehendem Muster:

- `tests/adapters/test_youtube_music.py`: gemockt wird die
  `YTMusic`-Instanz selbst (nicht httpx/respx — die Library nutzt eigenes
  `requests`), Antworten aus JSON-Fixtures
  (`tests/fixtures/youtube_music_*.json`). Abgedeckt:
  - `resolve` für alle drei Typen
  - Album-ID-Übersetzung `OLAK5uy_…` → `MPREb_…`
  - `search` pro Typ (Filter, Limit, SearchHit-Felder)
  - Fehler → `AdapterError`, not-found → `None` / `[]`
- `test_url_parser.py`: Positivfälle für alle drei Muster, Negativfälle
  (normale `PL…`-Playlist, `youtube.com`-/`youtu.be`-Host, fehlendes
  `v=`/`list=`)
- Live-Integration-Test hinter `LINKHOP_LIVE_TESTS=1`, wie bei den anderen
  Adaptern

## Risiken

| Risiko | Einschätzung |
|---|---|
| `ytmusicapi` ist inoffiziell und kann brechen | Bereits im V1-Spec dokumentiert. Fehler degradieren pro Ziel (`status: "error"`); Community-Fixes via Dependency-Update. |
| YouTube drosselt unauthentifizierte Server-IPs | Beobachten. Falls real: OAuth-Auth (`ytmusicapi` TV-Client-Flow) als Folgearbeit nachrüsten — Refresh-Token hält länger als Cookies. |
| `to_thread`-Aufrufe belegen Threadpool-Slots | Default-Executor reicht für die erwartete Last (3 Suchen + ≤ 3 Nachlade-Resolves pro Konvertierung). Kein eigener Executor in V1. |
