import type { components } from './schema';

export type ConvertResponse = components['schemas']['ConvertResponse'];
export type ServicesResponse = components['schemas']['ServicesResponse'];
export type ServiceInfo = components['schemas']['ServiceInfo'];
export type TargetResult = components['schemas']['TargetResult'];

export type ApiErrorCode =
  | 'invalid_url'
  | 'unsupported_service'
  | 'not_found'
  | 'rate_limited'
  | 'server_error'
  | 'offline';

export class ApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode,
    public readonly status: number,
    message: string,
    public readonly sourceUrl?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
