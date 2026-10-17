# Builder 11 — `INVALID_REQUEST` en `api/` (contrato v1.2, AB-1)

Mensaje del 17 de octubre de 2026 del supervisor (Claude Code, sesión "coordinator") al builder 2
(agente opencode "Configuración de Agente Constructor"), como adenda a la unidad 7. Unidad pedida por
Alexander (@jhonosorno-cmd): "contrato v1.2 — INVALID_REQUEST (ratificado por el equipo el 17 oct)".

---

````text
ADENDA A LA UNIDAD 7 — INVALID_REQUEST (contrato v1.2, AB-1)

CONTEXTO
El equipo ratificó el 17 oct el código `INVALID_REQUEST` (HTTP 400) en el ErrorCode de los Contratos A y B, para peticiones mal formadas: JSON inválido, campos obligatorios faltantes o inválidos, ruta desconocida. Ya lo escribí en openapi/ (rama payments/contract-v1-2) y en docs/contratos-cambios-v1.2.md. Mientras el PR no esté en main lo podés leer en C:\Users\Admin\ezpay-verify\openapi\contract-b.yaml (solo lectura).

QUÉ HACER (dentro de tu unidad 7, en tu rama; sin esperar a nada, es chico)
 1) Ruta desconocida y método no permitido en api/app/main.py: hoy el handler de HTTPException responde con el status de la excepción (404/405) y el código INVALID_REQUEST. Según AB-1 toda petición mal formada o ruta desconocida responde 400 INVALID_REQUEST. Escribí la prueba primero (GET a una ruta inexistente y un método no permitido → 400 INVALID_REQUEST, cuerpo {error:{code,message}}), vela fallar y corregí. Cuidado: SESSION_NOT_FOUND (404, del contrato) debe seguir igual.
 2) Cuerpo JSON inválido y campos de tipo inválido en /api/budget y /api/grant-callback → 400 INVALID_REQUEST (ya lo hace por RequestValidationError; confirmalo con la prueba de respuesta validada contra el contract-b.yaml nuevo).
 3) En api/payments_client: prueba (con httpx.MockTransport) de que un 400 INVALID_REQUEST de Node eleva PaymentsError con code "INVALID_REQUEST", NO se reintenta (una sola llamada) y NO es UpstreamUnavailable ni PaymentPending. Si el cliente ya lo cumple, solo agregá la prueba (podés tocar api/tests/payments_client/ para esto; el código del cliente solo si la prueba falla, y avisame).
 4) Orquestador: si Node responde INVALID_REQUEST a una llamada de tu orquestador, es un defecto propio (el orquestador armó mal la petición): el turno responde 500 INTERNAL_ERROR al frontend y se registra solo el código y la operación (nada de cuerpos). Cubrilo con una prueba.
Un commit separado (fix(api): ... / test(api): ...). Mismas reglas de seguridad y reporte de la unidad 7: agregá una sección "INVALID_REQUEST" a tu reporte con qué cambió y qué prueba viste fallar.
````
