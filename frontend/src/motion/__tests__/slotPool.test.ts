import { describe, expect, it, vi } from "vitest";
import { createSlotPool } from "../slotPool";

describe("slot pool", () => {
  it("grants one slot and promotes waiters in request order", () => {
    const pool = createSlotPool(1);
    const [a, b, c] = [Symbol("a"), Symbol("b"), Symbol("c")];
    pool.request(a);
    pool.request(b);
    pool.request(c);
    expect([pool.has(a), pool.has(b), pool.has(c)]).toEqual([true, false, false]);
    pool.release(a);
    expect([pool.has(b), pool.has(c)]).toEqual([true, false]);
    pool.release(c); // a waiter can leave without ever holding the slot
    pool.release(b);
    expect(pool.has(c)).toBe(false);
  });

  it("ignores duplicate requests and unknown releases, notifying only on change", () => {
    const pool = createSlotPool(1);
    const listener = vi.fn();
    const unsubscribe = pool.subscribe(listener);
    const a = Symbol("a");
    pool.request(a);
    pool.request(a);
    pool.release(Symbol("stranger"));
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    pool.release(a);
    expect(listener).toHaveBeenCalledTimes(1);
  });
});
