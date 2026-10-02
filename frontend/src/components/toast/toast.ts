import { useSyncExternalStore } from "react";

/**
 * App-wide notifications. Callers only describe what happened; the host
 * (ToastHost) decides how to show it. Text must already be translated and must
 * report real outcomes only (a run that actually finished, a save that succeeded).
 */
export type ToastTone = "success" | "error" | "info";
export interface Toast {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
}

let toasts: Toast[] = [];
let nextId = 1;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((listener) => listener());

export function notify(toast: Omit<Toast, "id" | "tone"> & { tone?: ToastTone }) {
  const id = nextId++;
  toasts = [...toasts, { tone: "info", ...toast, id }];
  emit();
  return id;
}

export function dismiss(id: number) {
  toasts = toasts.filter((toast) => toast.id !== id);
  emit();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

export const useToasts = () =>
  useSyncExternalStore(subscribe, () => toasts, () => toasts);
