import { Cipher } from './crypto.js'
import { loadConfig } from './config.js'
import { PaymentsService } from './domain/service.js'
import { createApp, instrument } from './http/app.js'
import { SdkOpenPayments } from './op/adapter.js'
import { Store } from './store/db.js'

let cfg
try {
  cfg = loadConfig()
} catch (e) {
  console.error((e as Error).message)
  process.exit(1)
}

const store = new Store(cfg.dbPath, new Cipher(cfg.dbEncryptionKey))
const op = instrument(await SdkOpenPayments.create({
  walletAddress: cfg.walletAddress, keyId: cfg.keyId, privateKey: cfg.privateKey, timeoutMs: cfg.opTimeoutMs,
}))
const svc = new PaymentsService(store, op)
svc.recover()

// Solo acceso local, sin CORS.
const server = createApp({ svc, ping: () => store.ping() }).listen(cfg.port, '127.0.0.1', () =>
  console.log(JSON.stringify({ msg: 'payments service listening', host: '127.0.0.1', port: cfg.port })))

const stop = () => { server.close(() => { store.close(); process.exit(0) }) }
process.on('SIGINT', stop)
process.on('SIGTERM', stop)
