import { createCipheriv, createDecipheriv, createHash, randomBytes, timingSafeEqual } from 'node:crypto'

/** AES-256-GCM con IV aleatorio por valor. Formato: base64(iv | tag | ciphertext). */
export class Cipher {
  private readonly key: Buffer
  constructor(base64Key: string) {
    this.key = Buffer.from(base64Key, 'base64')
    if (this.key.length !== 32) throw new Error('key must be 32 bytes')
  }
  encrypt(plain: string): string {
    const iv = randomBytes(12)
    const c = createCipheriv('aes-256-gcm', this.key, iv)
    const enc = Buffer.concat([c.update(plain, 'utf8'), c.final()])
    return Buffer.concat([iv, c.getAuthTag(), enc]).toString('base64')
  }
  decrypt(blob: string): string {
    const raw = Buffer.from(blob, 'base64')
    const d = createDecipheriv('aes-256-gcm', this.key, raw.subarray(0, 12))
    d.setAuthTag(raw.subarray(12, 28))
    return Buffer.concat([d.update(raw.subarray(28)), d.final()]).toString('utf8')
  }
}

/** base64(sha256(clientNonce \n interactNonce \n interactRef \n grantEndpointUri)), con padding. */
export function interactHash(clientNonce: string, interactNonce: string, interactRef: string, grantEndpointUri: string) {
  return createHash('sha256').update(`${clientNonce}\n${interactNonce}\n${interactRef}\n${grantEndpointUri}`).digest('base64')
}

export function safeEqual(a: string, b: string) {
  const x = Buffer.from(a)
  const y = Buffer.from(b)
  return x.length === y.length && timingSafeEqual(x, y)
}
