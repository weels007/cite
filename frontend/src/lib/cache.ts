/**
 * A tiny time to live cache for the chain reads.
 *
 * Every page used to ask the node for the same numbers on every request, so
 * the second visitor waited for the same round trip. Markets only change at
 * the close, at the resolution and at a payout, so a short window is enough
 * and the page becomes instant.
 */

type Entry = { value: unknown; expires: number }

const store = new Map<string, Entry>()

export async function cached<T>(
  key: string,
  ttlMs: number,
  load: () => Promise<T>
): Promise<T> {
  const now = Date.now()
  const hit = store.get(key)

  if (hit && hit.expires > now) {
    return hit.value as T
  }

  // Collapse the stampede: while the first call is in flight, everybody else
  // waits for it instead of asking the node again.
  const inFlight = pending.get(key)
  if (inFlight) {
    return inFlight as Promise<T>
  }

  const promise = load()
    .then((value) => {
      store.set(key, { value, expires: Date.now() + ttlMs })
      pending.delete(key)
      return value
    })
    .catch((error) => {
      pending.delete(key)
      throw error
    })

  pending.set(key, promise)
  return promise
}

const pending = new Map<string, Promise<unknown>>()

/** Drop everything, for instance right after a write. */
export function invalidate(prefix?: string) {
  if (!prefix) {
    store.clear()
    return
  }
  for (const key of Array.from(store.keys())) {
    if (key.startsWith(prefix)) store.delete(key)
  }
}
