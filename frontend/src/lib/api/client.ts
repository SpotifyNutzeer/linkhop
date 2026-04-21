import { ApiError, type ApiErrorCode, type ConvertResponse, type ServicesResponse } from './types';

const BASE = '/api/v1';

function mapStatus(status: number, code: string | undefined): ApiErrorCode {
  if (code === 'invalid_url' || code === 'unsupported_service') return code;
  if (code === 'rate_limited' || status === 429) return 'rate_limited';
  if (status === 404) return 'not_found';
  if (status >= 500) return 'server_error';
  if (status === 400) return 'invalid_url';
  return 'server_error';
}

async function request<T>(path: string, opts?: { sourceUrl?: string; signal?: AbortSignal }): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { signal: opts?.signal });
  } catch (e) {
    if ((e as { name?: string } | null)?.name === 'AbortError') throw e;
    throw new ApiError('offline', 0, 'Keine Verbindung zum Server', opts?.sourceUrl);
  }
  if (!res.ok) {
    let code: string | undefined;
    let message: string | undefined;
    try {
      const json = await res.json();
      // Backend wraps errors as {"error": {"code": ..., "message": ...}}
      const err = json.error ?? json;
      code = err.code;
      message = err.message;
    } catch { /* body leer / kein JSON */ }
    throw new ApiError(
      mapStatus(res.status, code),
      res.status,
      message ?? res.statusText,
      opts?.sourceUrl
    );
  }
  return res.json() as Promise<T>;
}

export async function convert(
  url: string,
  opts: { share?: boolean; targets?: string[]; signal?: AbortSignal } = {}
): Promise<ConvertResponse> {
  const qs = new URLSearchParams({ url });
  if (opts.share) qs.set('share', 'true');
  if (opts.targets?.length) qs.set('targets', opts.targets.join(','));
  return request<ConvertResponse>(`${BASE}/convert?${qs}`, { sourceUrl: url, signal: opts.signal });
}

export async function lookup(shortId: string): Promise<ConvertResponse> {
  return request<ConvertResponse>(`${BASE}/c/${encodeURIComponent(shortId)}`);
}

export async function services(): Promise<ServicesResponse> {
  return request<ServicesResponse>(`${BASE}/services`);
}

export { ApiError } from './types';
