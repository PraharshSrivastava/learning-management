// SHA-256 for HTTP deployments where SubtleCrypto is unavailable.
export function sha256Text(text) {
  const bytes = new TextEncoder().encode(text),
    count = bytes.length
  const padded = new Uint8Array(Math.ceil((count + 9) / 64) * 64)
  padded.set(bytes)
  padded[count] = 128
  const view = new DataView(padded.buffer)
  view.setUint32(padded.length - 4, count * 8)
  const primes = [],
    constants = [],
    state = []
  for (let n = 2; primes.length < 64; n++) {
    if (primes.some((p) => n % p === 0)) continue
    primes.push(n)
    constants.push(((Math.cbrt(n) % 1) * 4294967296) >>> 0)
    if (state.length < 8) state.push(((Math.sqrt(n) % 1) * 4294967296) >>> 0)
  }
  const rotate = (x, n) => (x >>> n) | (x << (32 - n))
  for (let offset = 0; offset < padded.length; offset += 64) {
    const words = new Uint32Array(64)
    for (let i = 0; i < 16; i++) words[i] = view.getUint32(offset + i * 4)
    for (let i = 16; i < 64; i++) {
      const x = words[i - 15],
        y = words[i - 2]
      words[i] =
        words[i - 16] +
        (rotate(x, 7) ^ rotate(x, 18) ^ (x >>> 3)) +
        words[i - 7] +
        (rotate(y, 17) ^ rotate(y, 19) ^ (y >>> 10))
    }
    let [a, b, c, d, e, f, g, h] = state
    for (let i = 0; i < 64; i++) {
      const first =
        (h +
          (rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25)) +
          ((e & f) ^ (~e & g)) +
          constants[i] +
          words[i]) >>>
        0
      const second =
        ((rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0
      h = g
      g = f
      f = e
      e = (d + first) >>> 0
      d = c
      c = b
      b = a
      a = (first + second) >>> 0
    }
    ;[a, b, c, d, e, f, g, h].forEach((word, i) => {
      state[i] = (state[i] + word) >>> 0
    })
  }
  return state.map((word) => word.toString(16).padStart(8, '0')).join('')
}
