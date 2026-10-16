import { AsyncLocalStorage } from 'node:async_hooks'
import { randomUUID } from 'node:crypto'
import express, { type NextFunction, type Request, type Response } from 'express'
import { AppError } from '../errors.js'
import type { PaymentsService } from '../domain/service.js'
import type { OpenPaymentsPort } from '../ports.js'

type Metrics = { opCalls: number; opMs: number }
const als = new AsyncLocalStorage<Metrics>()

/** Envuelve el puerto para contar llamadas y duración por request (observabilidad). */
export function instrument(port: OpenPaymentsPort): OpenPaymentsPort {
  return new Proxy(port, {
    get(target, prop, recv) {
      const v = Reflect.get(target, prop, recv)
      if (typeof v !== 'function') return v
      return async (...args: unknown[]) => {
        const m = als.getStore()
        const t0 = performance.now()
        try { return await v.apply(target, args) } finally {
          if (m) { m.opCalls++; m.opMs += performance.now() - t0 }
        }
      }
    },
  })
}

type Deps = { svc: PaymentsService; ping: () => void; log?: (line: object) => void }

export function createApp({ svc, ping, log = (l) => console.log(JSON.stringify(l)) }: Deps) {
  const app = express()
  app.disable('x-powered-by')
  app.use((req, res, next) => {
    const requestId = String(req.header('x-request-id') || randomUUID())
    const t0 = performance.now()
    const metrics: Metrics = { opCalls: 0, opMs: 0 }
    res.setHeader('X-Request-Id', requestId)
    res.on('finish', () => log({
      requestId, method: req.method, path: req.path, status: res.statusCode,
      durationMs: Math.round(performance.now() - t0), opCalls: metrics.opCalls, opMs: Math.round(metrics.opMs),
    }))
    als.run(metrics, next)
  })
  app.use(express.json({ limit: '32kb' }))

  const h = (fn: (req: Request, res: Response) => Promise<void> | void) =>
    (req: Request, res: Response, next: NextFunction) => Promise.resolve(fn(req, res)).catch(next)

  const v1 = express.Router()
  v1.get('/health', h((_req, res) => { ping(); res.json({ ok: true }) }))
  v1.post('/grants', h(async (req, res) => { res.status(201).json(await svc.createGrant(req.body)) }))
  v1.post('/grants/:id/continue', h(async (req, res) => { res.json(await svc.continueGrant(String(req.params.id), req.body)) }))
  v1.get('/grants/:id', h(async (req, res) => { res.json(await svc.getGrant(String(req.params.id))) }))
  v1.delete('/grants/:id', h(async (req, res) => { await svc.cancelGrant(String(req.params.id)); res.status(204).end() }))
  v1.post('/quotes', h(async (req, res) => { res.status(201).json(await svc.createQuote(req.body)) }))
  v1.post('/payments', h(async (req, res) => {
    const r = await svc.pay(req.header('idempotency-key') || undefined, req.body)
    res.status(r.status).json(r.body)
  }))
  v1.get('/payments/:id', h(async (req, res) => { res.json(await svc.getPayment(String(req.params.id))) }))
  app.use('/v1', v1)

  app.use((_req, res) => { res.status(404).json({ error: { code: 'NOT_FOUND', message: 'route not found' } }) })
  app.use((e: unknown, _req: Request, res: Response, _next: NextFunction) => {
    if (e instanceof AppError) return void res.status(e.status).json({ error: { code: e.code, message: e.message } })
    if ((e as any)?.type === 'entity.parse.failed')
      return void res.status(400).json({ error: { code: 'INVALID_REQUEST', message: 'malformed JSON body' } })
    log({ level: 'error', error: e instanceof Error ? e.name : 'unknown' })
    res.status(500).json({ error: { code: 'INTERNAL_ERROR', message: 'unexpected error' } })
  })
  return app
}
