export class AppError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message?: string,
  ) {
    super(message ?? code)
  }
}

/** Errores que el adaptador de Open Payments lanza hacia el dominio. */
export type OpErrorKind = 'timeout' | 'network' | 'unauthorized' | 'forbidden' | 'invalid_quote' | 'not_found' | 'server' | 'other'

export class OpError extends Error {
  constructor(
    readonly kind: OpErrorKind,
    message = kind,
  ) {
    super(message)
  }
}

export const isUpstream = (e: unknown) =>
  e instanceof OpError && ['timeout', 'network', 'server'].includes(e.kind)
