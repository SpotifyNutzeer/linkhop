import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, fireEvent, findByText, waitFor } from '@testing-library/svelte';
import ShareButton from './ShareButton.svelte';
import * as client from '$lib/api/client';
import { ApiError } from '$lib/api/types';

describe('ShareButton', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
      writable: true
    });
    vi.restoreAllMocks();
  });

  it('initially renders a "Teilen" button', () => {
    const { getByRole } = render(ShareButton, {
      props: { sourceUrl: 'https://spotify.com/track/1' }
    });
    expect(getByRole('button', { name: /teilen/i })).toBeInTheDocument();
  });

  it('fetches share-id on click and displays short link', async () => {
    const captured: { url: string; opts: Parameters<typeof client.convert>[1] }[] = [];
    const spy = vi.spyOn(client, 'convert').mockImplementation(async (url, opts) => {
      captured.push({ url, opts });
      return {
        source: { service: 'spotify' },
        targets: {},
        cache: { hit: false, ttl_seconds: 0 },
        share: { id: 'ab3x9k', url: 'https://example.com/c/ab3x9k' }
      } as Awaited<ReturnType<typeof client.convert>>;
    });
    const { getByRole, container } = render(ShareButton, {
      props: { sourceUrl: 'https://spotify.com/track/1' }
    });
    await fireEvent.click(getByRole('button', { name: /teilen/i }));
    const code = await findByText(container as HTMLElement, /https:\/\/example\.com\/c\/ab3x9k$/);
    expect(code).toBeInTheDocument();
    expect(captured).toHaveLength(1);
    expect(captured[0].opts?.share).toBe(true);
    expect(captured[0].opts?.signal).toBeInstanceOf(AbortSignal);
    spy.mockRestore();
  });

  it('shows error message on server error', async () => {
    const spy = vi.spyOn(client, 'convert').mockRejectedValue(
      new ApiError('server_error', 500, 'boom', 'https://spotify.com/track/1')
    );
    const { getByRole, container } = render(ShareButton, {
      props: { sourceUrl: 'https://spotify.com/track/1' }
    });
    await fireEvent.click(getByRole('button', { name: /teilen/i }));
    await waitFor(async () => {
      const msg = await findByText(container as HTMLElement, /fehler beim erzeugen/i);
      expect(msg).toBeInTheDocument();
    });
    spy.mockRestore();
  });
});
