import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import ServiceItem from './ServiceItem.svelte';
import type { TargetResult } from '$lib/api/types';

describe('ServiceItem', () => {
  beforeEach(() => {
    // Reset clipboard between tests.
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
      writable: true
    });
  });

  it('renders an ok link without ~match badge', () => {
    const result: TargetResult = { status: 'ok', url: 'https://spotify/track/1' };
    const { getByRole, queryByText } = render(ServiceItem, {
      props: { serviceId: 'spotify', displayName: 'Spotify', result }
    });
    expect(getByRole('link').getAttribute('href')).toBe('https://spotify/track/1');
    expect(queryByText(/~match/)).toBeNull();
  });

  it('shows ~match badge for ok_low status', () => {
    const result: TargetResult = { status: 'ok_low', url: 'https://tidal/track/9' };
    const { getByRole, getByText } = render(ServiceItem, {
      props: { serviceId: 'tidal', displayName: 'Tidal', result }
    });
    expect(getByRole('link').getAttribute('href')).toBe('https://tidal/track/9');
    expect(getByText(/~match/)).toBeInTheDocument();
  });

  it('shows "nicht gefunden" for not_found and no link', () => {
    const result: TargetResult = { status: 'not_found' };
    const { getByText, queryByRole } = render(ServiceItem, {
      props: { serviceId: 'deezer', displayName: 'Deezer', result }
    });
    expect(getByText(/nicht gefunden/i)).toBeInTheDocument();
    expect(queryByRole('link')).toBeNull();
  });

  it('shows "Fehler" for error status', () => {
    const result: TargetResult = { status: 'error', message: 'boom' };
    const { getByText } = render(ServiceItem, {
      props: { serviceId: 'deezer', displayName: 'Deezer', result }
    });
    expect(getByText(/Fehler/)).toBeInTheDocument();
  });

  it('copy button writes url to clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
      writable: true
    });
    const result: TargetResult = { status: 'ok', url: 'https://spotify/track/42' };
    const { getByRole } = render(ServiceItem, {
      props: { serviceId: 'spotify', displayName: 'Spotify', result }
    });
    await fireEvent.click(getByRole('button', { name: /link kopieren/i }));
    expect(writeText).toHaveBeenCalledWith('https://spotify/track/42');
  });
});
