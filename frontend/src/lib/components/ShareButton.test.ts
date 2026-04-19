import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { render, fireEvent, findByText, waitFor } from '@testing-library/svelte';
import ShareButton from './ShareButton.svelte';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('ShareButton', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
      writable: true
    });
  });

  it('initially renders a "Teilen" button', () => {
    const { getByRole } = render(ShareButton, {
      props: { sourceUrl: 'https://spotify.com/track/1' }
    });
    expect(getByRole('button', { name: /teilen/i })).toBeInTheDocument();
  });

  it('renders shortUrl after successful share call', async () => {
    server.use(
      http.get('*/api/v1/convert', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('share')).toBe('true');
        return HttpResponse.json({
          source: { service: 'spotify' },
          targets: {},
          cache: { hit: false, ttl_seconds: 0 },
          share: { id: 'ab3x9k' }
        });
      })
    );
    const { getByRole, container } = render(ShareButton, {
      props: { sourceUrl: 'https://spotify.com/track/1' }
    });
    await fireEvent.click(getByRole('button', { name: /teilen/i }));
    const code = await findByText(container as HTMLElement, /\/c\/ab3x9k$/);
    expect(code).toBeInTheDocument();
  });

  it('shows error message on 500 response', async () => {
    server.use(
      http.get('*/api/v1/convert', () =>
        HttpResponse.json({ code: 'server_error', message: 'boom' }, { status: 500 })
      )
    );
    const { getByRole, container } = render(ShareButton, {
      props: { sourceUrl: 'https://spotify.com/track/1' }
    });
    await fireEvent.click(getByRole('button', { name: /teilen/i }));
    await waitFor(async () => {
      const msg = await findByText(container as HTMLElement, /fehler beim erzeugen/i);
      expect(msg).toBeInTheDocument();
    });
  });
});
