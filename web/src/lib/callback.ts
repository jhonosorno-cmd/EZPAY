import type { GrantCallback } from "../api/types"

/** Lee lo que la wallet devolvió en finishUri, sin validar ni descartar nada (wallet-handoff). */
export function readCallbackParams(search: string): GrantCallback {
  const p = new URLSearchParams(search)
  const out: GrantCallback = {}
  const ref = p.get("interact_ref"), hash = p.get("hash"), result = p.get("result")
  if (ref !== null) out.interactRef = ref
  if (hash !== null) out.hash = hash
  if (result !== null) out.result = result
  return out
}
