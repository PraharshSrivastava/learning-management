import { sha256Text } from './sha256Text.js'

// Independently computed vectors, including UTF-8 and multiple block padding.
it.each([
  ['', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'],
  ['abc', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'],
  ['नमस्ते 🙂', '8c1d31e9559fe6ec196c8c9d1c3ed397547afbbf1a25c902e5ca6b1a774e2ace'],
  ['a'.repeat(1000), '41edece42d63e8d9bf515a9ba6932e1c20cbc9f5a5d134645adb5db1b9737ea3'],
])('matches SHA-256 UTF-8 vectors', (text, expected) => {
  expect(sha256Text(text!)).toBe(expected)
})
