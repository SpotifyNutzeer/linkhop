import { describe, expect, it } from 'vitest';
import { sanity } from './sanity';

describe('sanity', () => {
  it('returns linkhop', () => {
    expect(sanity()).toBe('linkhop');
  });
});
