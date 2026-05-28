import type { ProgressEvent } from './types';

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function streamAction(path: string, body: unknown, onProgress: (event: ProgressEvent) => void): Promise<unknown> {
  const res = await fetch(path, {
    method: 'POST',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(await res.text());
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let donePayload: unknown;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() || '';
    for (const event of events) {
      const lines = event.split('\n');
      const eventLine = lines.find((line) => line.startsWith('event: '));
      const dataLine = lines.find((line) => line.startsWith('data: '));
      if (!dataLine) continue;
      const data = dataLine.slice(6);
      if (eventLine?.slice(7) === 'error') {
        try {
          const parsed = JSON.parse(data);
          throw new Error(parsed.error || data);
        } catch (error) {
          if (error instanceof Error && error.message !== data) throw error;
          throw new Error(data);
        }
      }
      if (eventLine?.slice(7) === 'done') {
        donePayload = JSON.parse(data);
        continue;
      }
      if (eventLine?.slice(7) !== 'progress') continue;
      onProgress(JSON.parse(data) as ProgressEvent);
    }
  }
  return donePayload;
}
