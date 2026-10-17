# Contratos — cambios de v1.2

**Estado: [DECIDIDO] — ratificado por los cuatro el 17 de octubre.** Contrato vigente = [`contratos-http-v1.md`](./contratos-http-v1.md)
más [`contratos-cambios-propuestos-v1.1.md`](./contratos-cambios-propuestos-v1.1.md) más este documento;
si chocan, gana el más nuevo. Las novedades que surjan se deciden en equipo y se agregan acá.

## Contratos A y B

| # | Cambio | Motivo | Afecta |
|---|---|---|---|
| AB-1 | Nuevo código `INVALID_REQUEST` (HTTP `400`) en el `ErrorCode` de los Contratos A y B, para peticiones mal formadas: JSON inválido, campos obligatorios faltantes o inválidos, ruta desconocida | Hasta ahora esos casos respondían `500 INTERNAL_ERROR` (decisión D-10 a de Pagos) y el cliente no podía distinguir un error suyo de una falla del servicio | `openapi/contract-a.yaml`, `openapi/contract-b.yaml`, servicio de Node, `api/app` |

Reemplaza el mapeo provisorio a `INTERNAL_ERROR` de D-10 a. Un `interval` no soportado sigue siendo
`400 INVALID_AMOUNT`, salvo que un spec diga otra cosa.

**Cómo debe tratarlo el cliente:** `INVALID_REQUEST` es un error del llamador, no una caída del
servicio. El cliente de Python de Node no lo reintenta ni lo trata como `UPSTREAM_ERROR`; el
orquestador lo registra como defecto propio.
