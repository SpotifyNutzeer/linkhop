# Apple-Music-Adapter — Design-Spezifikation

**Datum:** 2026-07-22
**Status:** Design, genehmigt für Implementierungsplanung
**Autor:** Paul Weber (brainstorming mit Claude)

## Überblick

linkhop unterstützt Spotify, Deezer, Tidal und YouTube Music. Apple Music
war im V1-Design ([2026-04-18-linkhop-design.md](2026-04-18-linkhop-design.md))
explizit Nicht-Ziel, weil die offizielle Apple Music API einen
kostenpflichtigen Developer-Account erfordert. Dieses Spec liefert Apple
Music trotzdem nach — über die **kostenlose, credential-freie iTunes
Search/Lookup API**, die ISRC- und UPC-Lookups unterstützt und damit dem
Deezer-Muster entspricht. Der Vorbehalt aus V1 ist damit umgangen, nicht
gebrochen.

## Ziele und Nicht-Ziele

### Ziele

- **Bidirektionale Konvertierung** mit Apple Music als Quelle und Ziel,
  für Tracks, Alben und Artists
- **Keine Credentials**: iTunes Search API ohne Auth — kein Secret,
  Helm-Chart bleibt einfach
- **ISRC/UPC-Matching Richtung Apple Music** (`confidence = 1.0`), soweit
  die API es hergibt
- **Kein Eingriff** in `matching.py` oder `pipeline.py`

### Nicht-Ziele

- **Kein MusicKit / keine Apple Music API**: kein bezahlter
  Developer-Account, keine JWT-Signierung. Upgrade-Pfad bleibt offen (die
  API-Aufrufe sind im Adapter gekapselt), wird aber nicht vorbereitet.
- **Keine Storefront-Erhaltung**: die Storefront eingehender Links wird
  verworfen; alle Lookups und erzeugten Links nutzen die konfigurierte
  Storefront (Default `de`).
- **Kein clientseitiges Throttling** gegen das ~20-req/min-Limit in V1 —
  der Redis-Cache (7 d TTL) federt ab; siehe Risiken.
- **Keine Playlists** (wie in V1 generell).

## Entscheidungsgrundlage: API-Wahl

| Ansatz | Bewertung |
|---|---|
| **iTunes Search/Lookup API (gewählt)** | Kostenlos, ohne Credentials, ISRC/UPC-Lookup als Eingabe, stabil seit Jahren. Nachteile: ~20 req/min, Antworten enthalten kein ISRC/UPC, Metadaten dünner. |
| Apple Music API (MusicKit) | Bessere Daten (inkl. ISRC in Antworten), höhere Limits — aber 99 €/Jahr Developer-Programm, ES256-Key als Deployment-Secret, JWT-Generierung. Für ein Hobby-Deployment unverhältnismäßig. |
| iTunes jetzt, MusicKit-Abstraktion vorbereiten | YAGNI — die Adapter-Schnittstelle selbst ist bereits die Austauschgrenze. |

## Architektur

### Adapter (`backend/src/linkhop/adapters/apple_music.py`)

- Klasse `AppleMusicAdapter`, `service_id = "apple_music"`,
  `AdapterCapabilities(track=True, album=True, artist=True)`
- Konstruktor erhält `httpx.AsyncClient` und `storefront: str` (aus
  `Settings`, injizierbar für Tests) — Muster wie `DeezerAdapter`
- Basis-URL `https://itunes.apple.com`; alle Requests tragen
  `country=<storefront>`

### `resolve(parsed)`

| Typ | Aufruf | Mapping |
|---|---|---|
| Track | `GET /lookup?id=<id>` | `wrapperType == "track"`: `trackName`, `artistName`, `collectionName`, `trackTimeMillis` → `duration_ms`, URL aus `trackViewUrl` |
| Album | `GET /lookup?id=<id>` | `wrapperType == "collection"`: `collectionName`, `artistName`, URL aus `collectionViewUrl` |
| Artist | `GET /lookup?id=<id>` | `wrapperType == "artist"`: `artistName`, URL aus `artistLinkUrl` |

- Lookup nach ID ist typlos — der Adapter prüft den `wrapperType` des
  Ergebnisses gegen den erwarteten Typ und liefert bei Mismatch `None`
  (falsche ID-Art ist ein Not-Found, kein Fehler).
- `resultCount == 0` → `None`.
- **Artwork:** `artworkUrl100`, Substring `100x100` → `600x600`
  (dokumentierter CDN-Trick, kein API-Feature). Artists liefern oft kein
  Artwork → leerer String, wie bei den anderen Adaptern.
- **Kein ISRC/UPC in Antworten** — Felder bleiben `None` (siehe Matching).
- Die Pipeline lädt Suchkandidaten per `resolve()` nach (`_score_hit`);
  IDs aus `search()`-Treffern (`trackId`/`collectionId`/`artistId`) müssen
  daher denselben Lookup-Pfad durchlaufen — tun sie, da alles numerische
  Katalog-IDs sind.

### `search(meta, target_type)`

| Fall | Aufruf | Ergebnis |
|---|---|---|
| Track mit ISRC | `GET /lookup?isrc=<isrc>` | erster Song-Treffer, `confidence=1.0, match="isrc"` |
| Album mit UPC | `GET /lookup?upc=<upc>` | erster Collection-Treffer, `confidence=1.0, match="upc"` |
| Fallback Track | `GET /search?term=<titel artist>&media=music&entity=song&limit=3` | bis 3 × `confidence=0.0, match="metadata"` |
| Fallback Album | `…&entity=album&limit=3` | dito |
| Fallback Artist | `…&entity=musicArtist&limit=3` | dito |

- Query-Term: Titel + erster Artist, unbehandelt (die iTunes-Suche hat
  keine Feld-Syntax wie Deezer, daher kein Quote-Stripping nötig)
- `SearchHit.url` aus `trackViewUrl`/`collectionViewUrl`/`artistLinkUrl` —
  die View-URLs zeigen auf `music.apple.com/<storefront>/…` entsprechend
  dem `country`-Parameter des Requests

### URL-Parser (`url_parser.py`)

Hosts: `music.apple.com`, `geo.music.apple.com`, `itunes.apple.com`
(Legacy-Links, gleiche Pfadstruktur mit `id`-Präfix).

| Muster | Typ | Hinweis |
|---|---|---|
| `/<sf>/song/<slug>/<id>` | track | Slug optional |
| `/<sf>/album/<slug>/<id>?i=<trackId>` | track | `?i=` gewinnt über den Album-Pfad — erstmals Query-Parsing für einen Nicht-YTM-Dienst |
| `/<sf>/album/<slug>/<id>` | album | |
| `/<sf>/artist/<slug>/<id>` | artist | |

- Storefront-Segment (`de`, `us`, …) optional (Links ohne Storefront
  existieren und redirecten); es wird geparst und verworfen.
- Legacy-Form `itunes.apple.com/<sf>/album/<slug>/id<zahl>`: das
  `id`-Präfix vor der Zahl wird toleriert.
- Alles andere unter diesen Hosts → `UnsupportedUrlError`.

## Matching und Datenfluss

> **Revision 2026-07-22 (nach Live-Verifikation):** Der ursprünglich
> geplante ISRC-Lookup-Pfad wurde ersatzlos entfernt. Der `isrc`-Parameter
> des iTunes-Lookups liefert real durchgängig `resultCount: 0` (mehrere
> bekannte ISRCs, mit/ohne `entity=song`, mehrere Storefronts). Mit der
> geplanten Miss-Semantik (leeres Ergebnis ohne Fallback) wäre jeder Track
> mit ISRC auf Apple Music als „nicht gefunden" geendet. Entscheidung
> (Paul, 2026-07-22): Tracks gehen immer direkt in die Metadaten-Suche.
> Der UPC-Pfad funktioniert nachweislich und bleibt.

- **Andere Dienste → Apple Music, Alben:** UPC-Lookup, `confidence = 1.0`.
- **Andere Dienste → Apple Music, Tracks:** Metadaten-Suche
  (`score_candidate`-Scoring der Pipeline), nie `1.0`.
- **Apple Music als Quelle:** iTunes-Antworten enthalten kein ISRC/UPC →
  `ResolvedContent` ohne Industry-IDs → Ziel-Dienste matchen über den
  Metadaten-Pfad. `trackTimeMillis` liefert die Dauer und stützt die
  Track-Genauigkeit.

Das ist die ehrliche Abbildung der Datenlage (wie bei YouTube Music) und
wird im README dokumentiert, nicht kaschiert.

## Fehlerbehandlung

- „Nicht gefunden" (`resultCount == 0`, Typ-Mismatch) → `None` / `[]`
- HTTP ≥ 400 (insbesondere 403/429 beim Rate-Limit) →
  `AdapterError("apple_music", …)` — die Pipeline degradiert pro Ziel auf
  `status: "error"`, die Gesamt-Konvertierung läuft weiter
- Nicht-JSON-Antworten (die API liefert bei manchen Fehlern text/html) →
  `AdapterError`

## Konfiguration und Rollout

- `config.py`: `enable_apple_music: bool = True`,
  `apple_music_storefront: str = "de"`
- `deps.py`: Registrierung ohne Credential-Check (wie Deezer/YTM),
  Storefront aus Settings durchreichen
- `routes/services.py`: `_NAMES["apple_music"] = "Apple Music"`
- Frontend `ServiceItem.svelte`: `--brand: #fa243c`
- Frontend `InputBar.svelte`: Placeholder um Apple Music ergänzen
- Helm-Chart: `config.enableAppleMusic: true`,
  `config.appleMusicStorefront: "de"` in `values.yaml`, Env-Wiring
  (`LINKHOP_ENABLE_APPLE_MUSIC`, `LINKHOP_APPLE_MUSIC_STOREFRONT`) im
  `backend-deployment.yaml` — keine Secret-Keys
- Keine neue Python-Dependency (nur `httpx`)
- READMEs: Haupt-README-Tabelle (+ Hinweis auf ISRC-Asymmetrie),
  `backend/README.md` Env-Var-Referenz

## Tests

Nach bestehendem Muster:

- `tests/adapters/test_apple_music.py`: respx-gemockt, Antworten aus
  JSON-Fixtures (`tests/fixtures/apple_music_*.json`). Abgedeckt:
  - `resolve` für alle drei Typen (inkl. Artwork-Upscaling,
    `country`-Parameter, Typ-Mismatch → `None`, `resultCount 0` → `None`)
  - `search`: ISRC-Pfad, UPC-Pfad, Metadaten-Fallback pro Typ,
    Limit/Slicing, SearchHit-Felder
  - Fehler: HTTP 429/500 → `AdapterError`, Nicht-JSON-Body → `AdapterError`
- `test_url_parser.py`: Positivfälle für alle vier Muster (mit/ohne
  Storefront, mit/ohne Slug, `?i=`-Vorrang, Legacy-`id`-Präfix,
  `geo.`-Host), Negativfälle (Playlist-Pfad, fremder Host, nicht-numerische
  ID)
- `test_config.py` / `test_deps.py`: neue Settings + Registrierung
- Live-Integration-Test hinter `LINKHOP_LIVE_TESTS=1`, wie bei den anderen
  Adaptern

## Risiken

| Risiko | Einschätzung |
|---|---|
| Rate-Limit ~20 req/min | Redis-Cache (7 d) fängt Wiederholungen; eine Konvertierung kostet ≤ ~4 Apple-Calls. Bei realen 429s: Throttling/Backoff als Folgearbeit. |
| iTunes-API ist „legacy", könnte abgeschaltet werden | Seit > 15 Jahren stabil, breit genutzt. Fehler degradieren pro Ziel; MusicKit bleibt als Ausweichpfad. |
| iTunes-Katalog ≠ Apple-Music-Katalog in Randfällen (Apple-Music-exklusive Inhalte) | Betroffene Lookups liefern `resultCount 0` → sauberes `not_found`, kein Fehler. Akzeptiert. |
| Storefront-Mismatch: Inhalt in `de` nicht verfügbar, obwohl Quell-Link (z. B. `us`) existiert | Bewusste Design-Entscheidung (konfigurierbare Storefront); `not_found` ist das korrekte Ergebnis für den konfigurierten Katalog. |
