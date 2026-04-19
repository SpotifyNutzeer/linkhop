import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { convert, lookup, services, ApiError } from './client';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('api client', () => {
  it('convert returns response on 200', async () => {
    server.use(
      http.get('*/api/v1/convert', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('url')).toBe('https://example.com/track/1');
        return HttpResponse.json({ source: { service: 'tidal' }, targets: {} });
      })
    );
    const res = await convert('https://example.com/track/1');
    expect(res.source.service).toBe('tidal');
  });

  it('convert throws ApiError with mapped code on 400', async () => {
    server.use(
      http.get('*/api/v1/convert', () =>
        HttpResponse.json({ code: 'invalid_url', message: 'bad' }, { status: 400 })
      )
    );
    await expect(convert('https://bad')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'invalid_url',
      status: 400
    });
  });

  it('convert throws ApiError offline on network exception', async () => {
    server.use(http.get('*/api/v1/convert', () => HttpResponse.error()));
    await expect(convert('https://x')).rejects.toMatchObject({ code: 'offline' });
  });

  it('convert passes share=true', async () => {
    server.use(
      http.get('*/api/v1/convert', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('share')).toBe('true');
        return HttpResponse.json({ source: {}, targets: {}, share: { id: 'ab3x9k' } });
      })
    );
    await convert('https://x', { share: true });
  });

  it('lookup GETs /c/<id>', async () => {
    server.use(
      http.get('*/api/v1/c/ab3x9k', () =>
        HttpResponse.json({ source: { service: 'spotify' }, targets: {} })
      )
    );
    const res = await lookup('ab3x9k');
    expect(res.source.service).toBe('spotify');
  });

  it('lookup 404 maps to not_found code', async () => {
    server.use(
      http.get('*/api/v1/c/missing', () =>
        HttpResponse.json({ code: 'not_found', message: 'nope' }, { status: 404 })
      )
    );
    await expect(lookup('missing')).rejects.toMatchObject({ code: 'not_found' });
  });

  it('services returns list', async () => {
    server.use(
      http.get('*/api/v1/services', () =>
        HttpResponse.json({
          services: [{ id: 'spotify', name: 'Spotify', capabilities: ['track'] }]
        })
      )
    );
    const res = await services();
    expect(res.services).toHaveLength(1);
    expect(res.services[0]).toMatchObject({ id: 'spotify', name: 'Spotify' });
  });
});
