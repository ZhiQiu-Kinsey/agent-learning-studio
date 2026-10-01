/**
 * First-come slot pool. Holders keep a slot until they release it; waiters are
 * promoted in request order. Used to keep at most one WebGL effect alive.
 */
export function createSlotPool(capacity: number) {
  const holders: symbol[] = [];
  const waiters: symbol[] = [];
  const listeners = new Set<() => void>();
  const notify = () => listeners.forEach((listener) => listener());

  return {
    request(token: symbol) {
      if (holders.includes(token) || waiters.includes(token)) return;
      if (holders.length < capacity) holders.push(token);
      else waiters.push(token);
      notify();
    },
    release(token: symbol) {
      const held = holders.indexOf(token);
      const waiting = waiters.indexOf(token);
      if (held < 0 && waiting < 0) return;
      if (held >= 0) holders.splice(held, 1);
      if (waiting >= 0) waiters.splice(waiting, 1);
      while (holders.length < capacity && waiters.length)
        holders.push(waiters.shift()!);
      notify();
    },
    has: (token: symbol) => holders.includes(token),
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

export type SlotPool = ReturnType<typeof createSlotPool>;
