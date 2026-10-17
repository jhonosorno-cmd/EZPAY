// Tipos del Contrato B, derivados de openapi/contract-b.yaml (fuente: docs/contratos-http-v1.md + v1.1).
// No editar contract-b.gen.ts a mano: `npm run gen:api` lo regenera cuando cambia el contrato.
import type { components } from "./contract-b.gen"

type S = components["schemas"]

export type Amount = S["Amount"]
export type ErrorCode = S["ErrorCode"]
export type ErrorBody = S["ErrorBody"]
export type Budget = S["Budget"]
export type TurnState = S["TurnState"]
// El cliente tolera estados que todavía no conoce (web-conversation, "Estado desconocido").
export type TurnResponse = Omit<S["TurnResponse"], "state"> & { state: TurnState | (string & {}) }
export type Payment = NonNullable<S["TurnResponse"]["payment"]>
export type RecipientOption = NonNullable<S["TurnResponse"]["options"]>[number]
export type GrantCallback = { interactRef?: string; hash?: string; result?: string }
export type Enrollment = { enrolled: boolean }
