import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import HistoryDropdown from './HistoryDropdown.svelte';
import { history } from '$lib/stores/history';

const THREE_ENTRIES = [
  { sourceUrl: 'https://a', title: 'Alpha', artists: ['A1'], coverUrl: null, timestamp: 3 },
  { sourceUrl: 'https://b', title: 'Bravo', artists: ['B1'], coverUrl: null, timestamp: 2 },
  { sourceUrl: 'https://c', title: 'Charlie', artists: ['C1'], coverUrl: null, timestamp: 1 }
];

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
    await fireEvent.click(getByRole('option', { name: /T/ }));
    expect(handler).toHaveBeenCalledWith({ url: 'https://a' });
  });

  describe('keyboard navigation', () => {
    it('ArrowDown from first option focuses second option', async () => {
      history.set(THREE_ENTRIES);
      const { getByRole, getAllByRole } = render(HistoryDropdown, { props: { open: true } });
      const listbox = getByRole('listbox', { name: /verlauf/i });
      const options = getAllByRole('option');
      options[0].focus();
      await fireEvent.keyDown(listbox, { key: 'ArrowDown' });
      expect(document.activeElement).toBe(options[1]);
      expect(options[1].getAttribute('aria-selected')).toBe('true');
    });

    it('ArrowUp from first option wraps to last', async () => {
      history.set(THREE_ENTRIES);
      const { getByRole, getAllByRole } = render(HistoryDropdown, { props: { open: true } });
      const listbox = getByRole('listbox', { name: /verlauf/i });
      const options = getAllByRole('option');
      options[0].focus();
      await fireEvent.keyDown(listbox, { key: 'ArrowUp' });
      expect(document.activeElement).toBe(options[2]);
    });

    it('ArrowDown from last option wraps to first', async () => {
      history.set(THREE_ENTRIES);
      const { getByRole, getAllByRole } = render(HistoryDropdown, { props: { open: true } });
      const listbox = getByRole('listbox', { name: /verlauf/i });
      const options = getAllByRole('option');
      options[2].focus();
      // Simulate listbox active index = 2: move there first via End
      await fireEvent.keyDown(listbox, { key: 'End' });
      await fireEvent.keyDown(listbox, { key: 'ArrowDown' });
      expect(document.activeElement).toBe(options[0]);
    });

    it('Home jumps to first option', async () => {
      history.set(THREE_ENTRIES);
      const { getByRole, getAllByRole } = render(HistoryDropdown, { props: { open: true } });
      const listbox = getByRole('listbox', { name: /verlauf/i });
      const options = getAllByRole('option');
      // Move to middle via ArrowDown from first
      options[0].focus();
      await fireEvent.keyDown(listbox, { key: 'ArrowDown' });
      expect(document.activeElement).toBe(options[1]);
      await fireEvent.keyDown(listbox, { key: 'Home' });
      expect(document.activeElement).toBe(options[0]);
    });

    it('End jumps to last option', async () => {
      history.set(THREE_ENTRIES);
      const { getByRole, getAllByRole } = render(HistoryDropdown, { props: { open: true } });
      const listbox = getByRole('listbox', { name: /verlauf/i });
      const options = getAllByRole('option');
      options[0].focus();
      await fireEvent.keyDown(listbox, { key: 'ArrowDown' }); // index 1
      await fireEvent.keyDown(listbox, { key: 'End' });
      expect(document.activeElement).toBe(options[2]);
    });

    it('Enter on a focused option dispatches select', async () => {
      history.set(THREE_ENTRIES);
      const handler = vi.fn();
      const { getByRole, getAllByRole, component } = render(HistoryDropdown, {
        props: { open: true }
      });
      component.$on('select', (e: CustomEvent) => handler(e.detail));
      const listbox = getByRole('listbox', { name: /verlauf/i });
      const options = getAllByRole('option');
      options[0].focus();
      await fireEvent.keyDown(listbox, { key: 'ArrowDown' }); // move to index 1
      // Native button activates on Enter via click — simulate click (what the browser does).
      await fireEvent.click(options[1]);
      expect(handler).toHaveBeenCalledWith({ url: 'https://b' });
    });

    it('Escape dispatches close event', async () => {
      history.set(THREE_ENTRIES);
      const handler = vi.fn();
      const { getByRole, component } = render(HistoryDropdown, { props: { open: true } });
      component.$on('close', () => handler());
      const listbox = getByRole('listbox', { name: /verlauf/i });
      await fireEvent.keyDown(listbox, { key: 'Escape' });
      expect(handler).toHaveBeenCalledTimes(1);
    });

    it('aria-selected tracks activeIndex', async () => {
      history.set(THREE_ENTRIES);
      const { getByRole, getAllByRole } = render(HistoryDropdown, { props: { open: true } });
      const listbox = getByRole('listbox', { name: /verlauf/i });
      const options = getAllByRole('option');
      options[0].focus();
      await fireEvent.keyDown(listbox, { key: 'ArrowDown' });
      const selected = options.filter((o) => o.getAttribute('aria-selected') === 'true');
      expect(selected).toHaveLength(1);
      expect(selected[0]).toBe(options[1]);
    });

    it('tabindex tracks activeIndex (roving)', async () => {
      history.set(THREE_ENTRIES);
      const { getByRole, getAllByRole } = render(HistoryDropdown, { props: { open: true } });
      const listbox = getByRole('listbox', { name: /verlauf/i });
      const options = getAllByRole('option');
      options[0].focus();
      await fireEvent.keyDown(listbox, { key: 'ArrowDown' });
      const zeroes = options.filter((o) => o.getAttribute('tabindex') === '0');
      const minusOnes = options.filter((o) => o.getAttribute('tabindex') === '-1');
      expect(zeroes).toHaveLength(1);
      expect(zeroes[0]).toBe(options[1]);
      expect(minusOnes).toHaveLength(2);
    });
  });
});
