// wallet-handoff: la moneda sale de la configuración y debe coincidir con ASSET_CODE/ASSET_SCALE de Python.
export const ASSET_CODE = import.meta.env.VITE_ASSET_CODE ?? "COP"
export const ASSET_SCALE = Number(import.meta.env.VITE_ASSET_SCALE ?? "2") // escala, no dinero
export const DEMO_BUDGET = {
  value: import.meta.env.VITE_DEMO_BUDGET_VALUE ?? "20000000", // 200.000 COP
  assetCode: ASSET_CODE,
  assetScale: ASSET_SCALE,
}
export const PENDING_CHECK_MS = 20_000 // turno único de verificación de PAYMENT_PENDING (B-2)
export const MAX_RECORDING_MS = 15_000 // F-5 [PROPUESTA]
export const MIN_RECORDING_MS = 400 // menos que esto es un toque accidental
