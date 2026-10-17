import { readFileSync } from 'node:fs'

export type Config = {
  walletAddress: string; keyId: string; privateKey: string; dbEncryptionKey: string
  port: number; dbPath: string; opTimeoutMs: number
}

/** Valida el entorno al arrancar. Nombra la variable que falla, nunca imprime su valor. */
export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const need = (name: string) => {
    const v = env[name]
    if (!v || !v.trim()) throw new Error(`Missing required environment variable: ${name}`)
    return v.trim()
  }
  const walletAddress = need('WALLET_ADDRESS')
  if (!/^https?:\/\//.test(walletAddress)) throw new Error('Invalid environment variable: WALLET_ADDRESS (must be a URL)')
  const keyId = need('KEY_ID')
  const keyPath = need('PRIVATE_KEY_PATH')
  let privateKey: string
  try { privateKey = readFileSync(keyPath, 'utf8') } catch { throw new Error('Invalid environment variable: PRIVATE_KEY_PATH (file not readable)') }
  const dbEncryptionKey = need('DB_ENCRYPTION_KEY')
  if (Buffer.from(dbEncryptionKey, 'base64').length !== 32)
    throw new Error('Invalid environment variable: DB_ENCRYPTION_KEY (must be 32 bytes in base64)')
  const num = (name: string, def: number) => {
    const raw = env[name]
    if (!raw) return def
    const n = Number(raw)
    if (!Number.isInteger(n) || n <= 0) throw new Error(`Invalid environment variable: ${name}`)
    return n
  }
  return { walletAddress, keyId, privateKey, dbEncryptionKey, port: num('PORT', 4000), dbPath: env.DB_PATH?.trim() || './payments.db', opTimeoutMs: num('OP_TIMEOUT_MS', 8000) }
}
