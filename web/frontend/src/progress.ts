import type { ProgressItem } from './types';

export const maxLogItems = 10;

export function progressItemKey(item: ProgressItem) {
  if (typeof item === 'string') return item;
  return item.key || item.label;
}

export function upsertProgressItem(items: ProgressItem[], message: ProgressItem) {
  const key = progressItemKey(message);
  if (!key) return [...items, message].slice(-maxLogItems);
  const next = items.filter((item) => progressItemKey(item) !== key);
  return [...next, message].slice(-maxLogItems);
}
