import { describe, expect, it } from 'vitest';
import { BoundedSet } from '../../src/utils/boundedSet';

describe('BoundedSet', () => {
  it('deduplicates and reports new insertions', () => {
    const s = new BoundedSet<string>(3);
    expect(s.add('a')).toBe(true);
    expect(s.add('a')).toBe(false);
    expect(s.has('a')).toBe(true);
    expect(s.size).toBe(1);
  });

  it('evicts oldest entries beyond capacity (bounded memory)', () => {
    const s = new BoundedSet<string>(2);
    s.add('a');
    s.add('b');
    s.add('c'); // evicts 'a'
    expect(s.has('a')).toBe(false);
    expect(s.has('b')).toBe(true);
    expect(s.has('c')).toBe(true);
    expect(s.size).toBe(2);
  });

  it('rejects non-positive capacity', () => {
    expect(() => new BoundedSet<string>(0)).toThrow();
  });
});
