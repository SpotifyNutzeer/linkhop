import { describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import ErrorPanel from './ErrorPanel.svelte';
import { ApiError } from '$lib/api/types';

describe('ErrorPanel', () => {
  it('renders friendly message for invalid_url', () => {
    const err = new ApiError('invalid_url', 400, 'bad', 'https://x');
    const { getByText } = render(ErrorPanel, { props: { error: err } });
    expect(getByText(/ungültiger link/i)).toBeInTheDocument();
  });

  it('renders offline message', () => {
    const err = new ApiError('offline', 0, 'net', 'https://x');
    const { getByText } = render(ErrorPanel, { props: { error: err } });
    expect(getByText(/keine verbindung/i)).toBeInTheDocument();
  });

  it('copy-debug writes format-B string to clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const err = new ApiError('invalid_url', 400, 'bad url', 'https://x');
    const { getByRole } = render(ErrorPanel, { props: { error: err } });
    await fireEvent.click(getByRole('button', { name: /debug.*kopieren/i }));
    expect(writeText).toHaveBeenCalledTimes(1);
    const text = writeText.mock.calls[0][0] as string;
    expect(text).toMatch(/^invalid_url: bad url/);
    expect(text).toContain('URL: https://x');
    expect(text).toMatch(/Zeit: \d{4}-\d{2}-\d{2}T/);
  });
});
