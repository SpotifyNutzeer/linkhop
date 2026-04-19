import { describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import { services } from './services';

describe('services store', () => {
  it('starts empty', () => {
    expect(get(services)).toEqual({});
  });
  it('can be set', () => {
    services.set({
      spotify: { id: 'spotify', name: 'Spotify', capabilities: ['track'] }
    });
    expect(get(services).spotify.name).toBe('Spotify');
  });
});
