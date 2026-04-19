import { beforeEach, describe, expect, it } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import ThemeToggle from './ThemeToggle.svelte';

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('cycles auto → dark → light → auto on click', async () => {
    const { getByRole } = render(ThemeToggle);
    const btn = getByRole('button');
    expect(btn.getAttribute('aria-label')).toContain('automatisch');
    await fireEvent.click(btn);
    expect(btn.getAttribute('aria-label')).toContain('dunkel');
    await fireEvent.click(btn);
    expect(btn.getAttribute('aria-label')).toContain('hell');
    await fireEvent.click(btn);
    expect(btn.getAttribute('aria-label')).toContain('automatisch');
  });
});
