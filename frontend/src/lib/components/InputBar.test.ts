import { describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import InputBar from './InputBar.svelte';

describe('InputBar', () => {
  it('dispatches submit with url on button click', async () => {
    const handler = vi.fn();
    const { getByRole, component } = render(InputBar);
    component.$on('submit', (e: CustomEvent) => handler(e.detail));
    const input = getByRole('textbox');
    await fireEvent.input(input, { target: { value: 'https://x' } });
    await fireEvent.click(getByRole('button', { name: /konvertieren/i }));
    expect(handler).toHaveBeenCalledWith({ url: 'https://x' });
  });

  it('dispatches submit on Enter', async () => {
    const handler = vi.fn();
    const { getByRole, component } = render(InputBar);
    component.$on('submit', (e: CustomEvent) => handler(e.detail));
    const input = getByRole('textbox');
    await fireEvent.input(input, { target: { value: 'https://y' } });
    await fireEvent.keyDown(input, { key: 'Enter' });
    expect(handler).toHaveBeenCalledWith({ url: 'https://y' });
  });

  it('does not submit empty value', async () => {
    const handler = vi.fn();
    const { getByRole, component } = render(InputBar);
    component.$on('submit', (e: CustomEvent) => handler(e.detail));
    await fireEvent.click(getByRole('button', { name: /konvertieren/i }));
    expect(handler).not.toHaveBeenCalled();
  });
});
