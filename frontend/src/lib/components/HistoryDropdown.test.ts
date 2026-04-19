import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import HistoryDropdown from './HistoryDropdown.svelte';
import { history } from '$lib/stores/history';

describe('HistoryDropdown', () => {
  beforeEach(() => history.set([]));

  it('renders nothing when empty', () => {
    const { container } = render(HistoryDropdown, { props: { open: true } });
    expect(container.querySelector('.dropdown')).toBeNull();
  });

  it('renders entries when open and non-empty', () => {
    history.set([
      { sourceUrl: 'https://a', title: 'Nightcall', artists: ['Kavinsky'], coverUrl: null, timestamp: 1 }
    ]);
    const { getByText } = render(HistoryDropdown, { props: { open: true } });
    expect(getByText('Nightcall')).toBeInTheDocument();
  });

  it('dispatches select on click', async () => {
    history.set([
      { sourceUrl: 'https://a', title: 'T', artists: [], coverUrl: null, timestamp: 1 }
    ]);
    const handler = vi.fn();
    const { getByRole, component } = render(HistoryDropdown, { props: { open: true } });
    component.$on('select', (e: CustomEvent) => handler(e.detail));
    await fireEvent.click(getByRole('button', { name: /T/ }));
    expect(handler).toHaveBeenCalledWith({ url: 'https://a' });
  });
});
