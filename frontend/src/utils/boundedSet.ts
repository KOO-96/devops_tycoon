/**
 * Insertion-ordered set with a bounded capacity (FIFO eviction). Used for
 * `recent_event_ids` so de-duplication memory cannot grow without limit (§26).
 */
export class BoundedSet<T> {
  private readonly order: T[] = [];
  private readonly set = new Set<T>();

  constructor(private readonly capacity: number) {
    if (capacity <= 0) throw new Error('BoundedSet capacity must be > 0');
  }

  has(value: T): boolean {
    return this.set.has(value);
  }

  /** Add a value; returns true if it was new. Evicts the oldest when full. */
  add(value: T): boolean {
    if (this.set.has(value)) return false;
    this.set.add(value);
    this.order.push(value);
    while (this.order.length > this.capacity) {
      const oldest = this.order.shift();
      if (oldest !== undefined) this.set.delete(oldest);
    }
    return true;
  }

  get size(): number {
    return this.set.size;
  }
}
