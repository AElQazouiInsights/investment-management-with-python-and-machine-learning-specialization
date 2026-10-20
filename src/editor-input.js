// Separate the byte payload from its 32-bit length and ready flag.
const encoder = new TextEncoder()
const decoder = new TextDecoder()

export function sendInput(text, bytes, state) {
  const encoded = encoder.encode(text)
  if (encoded.length > bytes.length) return false
  bytes.set(encoded)
  Atomics.store(state, 1, encoded.length)
  Atomics.store(state, 0, 1)
  Atomics.notify(state, 0)
  // Only the consumer resets readiness, so early responses cannot be lost.
  return true
}

export function receiveInput(bytes, state, interrupt) {
  while (Atomics.load(state, 0) === 0) {
    if (interrupt && Atomics.load(interrupt, 0) === 2) return ''
    Atomics.wait(state, 0, 0, 100)
  }
  const length = Atomics.load(state, 1)
  const text = decoder.decode(bytes.slice(0, length))
  Atomics.store(state, 0, 0)
  return text
}
