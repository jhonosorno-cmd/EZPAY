# Builder 07 — Cliente de Node en Python (`payments-client`)

Brief enviado el 17 de octubre de 2026 por el supervisor (Claude Code, sesión "coordinator") al
segundo builder (agente opencode "Configuración de Agente Constructor"). Aprobado por Alexander
(@jhonosorno-cmd) con "OK al plan de la unidad 6. Mandale el brief al builder 2."

---

````text
UNIDAD 6 — Cliente de Node en Python (api/payments_client/)

OBJETIVO
Clase Python que habla con el servicio de Pagos (Contrato A, /v1, puerto 4000) con las reglas de add-payments-client que son del CLIENTE HTTP: idempotencia, reintentos, errores por código, polling y PAYMENT_PENDING. NO es el orquestador: no maneja el estado del turno ni el grant puntual como flujo (unidad 7, con el motor real); tampoco depende de api/app (lo construye el builder 1). Leíste ya los specs: este brief no los repite, los fija como fuente de verdad (openspec/changes/add-payments-client/specs/payments-client/spec.md y openapi/contract-a.yaml; v1.1 gana si chocan).

PREPARACIÓN
Tu worktree C:\Users\Admin\ezpay-backend-b2, rama payments/payments-client. Antes de empezar: git fetch origin; git merge origin/main (sin push). Entorno virtual FUERA del repo o en api/.venv (ignorado); instalá httpx, pyyaml y jsonschema ahí con versiones exactas SIN crear api/requirements.txt (lo crea el builder 1; anotá en el reporte las versiones exactas que usaste para que yo las unifique). Anotá cuántas pruebas pasan hoy en api/ antes de tocar nada.

ALCANCE (api/payments_client/)
 1) Configuración: lee de variables de entorno NODE_BASE_URL (por defecto http://localhost:4000/v1), ASSET_CODE y ASSET_SCALE. Si falta ASSET_CODE o ASSET_SCALE, error claro al construir el cliente (no arranca). Moneda y escala SOLO desde el entorno, nunca escritas en el código.
 2) Un método por operación del Contrato A: create_grant, continue_grant, get_grant, cancel_grant (DELETE, A-1), create_quote, create_payment, get_payment, health. Montos como {value: str de dígitos, assetCode, assetScale}; nada de float (CONV-1). Propaga X-Request-Id si se lo pasan.
 3) Errores: un tipo de excepción o resultado con `code` y `status` tomados de {error:{code,message}}; se decide por `code`, nunca por el texto. Un error sin forma de contrato (red caída, timeout, cuerpo no JSON) es un tipo aparte (UPSTREAM_UNAVAILABLE) y NO se confunde con un error de negocio.
 4) Pago con idempotencia: create_payment recibe la clave (UUID) que genera el llamador por quote; el cliente NO inventa claves nuevas al reintentar. Ante 502, 500, error de red/timeout o 409 PAYMENT_IN_PROGRESS reintenta con la MISMA clave y el mismo quoteId: hasta 3 intentos, esperas de 0,5 s y 1 s, tope total de 15 s. Si se agota devuelve el resultado PAYMENT_PENDING (con el paymentId si se conoce), NUNCA un rechazo. No reintenta 4xx de negocio (QUOTE_EXPIRED, QUOTE_NOT_FOUND, LIMIT_EXCEEDED, GRANT_INVALID): los devuelve para que decida el orquestador. El sleep es inyectable (para pruebas sin esperar).
 5) Polling: wait_for_payment(paymentId) consulta GET /v1/payments/{id} cada ~10 s (intervalo y tope configurables; reloj inyectable) hasta COMPLETED o FAILED; si sigue PROCESSING al vencer devuelve PAYMENT_PENDING; FAILED devuelve el fallo; NUNCA declara fallo por tiempo.
 6) Logs: logger estándar sin interact_ref, hash, tokens, paymentId completo ni cuerpos; solo operación, status, code y requestId.

PRUEBAS PRIMERO (unittest, api/tests/payments_client/; que se vean fallar antes del código)
 a) Con httpx.MockTransport: una prueba por operación (ruta, método, cuerpo y header) y por cada código de error del contrato que el cliente distingue.
 b) Validación contra el contrato: las respuestas simuladas de las pruebas se validan con jsonschema contra openapi/contract-a.yaml (resolviendo sus $ref), para que el doble no se desvíe del contrato.
 c) Idempotencia: 502 → 502 → 201 usa la misma clave y quoteId los 3 envíos; agotar 3 intentos → PAYMENT_PENDING; PAYMENT_IN_PROGRESS → igual; un 4xx de negocio no se reintenta.
 d) Polling: PROCESSING → PROCESSING → COMPLETED; PROCESSING hasta vencer → PAYMENT_PENDING; FAILED → fallo; sin llamadas extra tras el estado final.
 e) Configuración: falta ASSET_CODE o ASSET_SCALE → error; los montos que salen del cliente usan solo valores del entorno.
 f) Logs: capturá el logger y comprobá que no aparecen el hash, interact_ref ni tokens de ejemplo.
 g) Una prueba de humo OPCIONAL (se salta si Prism no está) contra `npm run mock:a` del repo, solo si arranca limpio; si no, anotalo en el reporte.

SEGURIDAD
 - Repo público: nada de .env, tokens, llaves, audio ni transcripciones. Datos de prueba inventados. NO llames al servicio de Node real ni a la wallet real. Revisá `git diff --cached` antes de cada commit.

ARCHIVOS PERMITIDOS
api/payments_client/** (nuevo) y api/tests/payments_client/** (nuevo). NO toques api/app, api/voice, api/decision, api/pin, api/requirements.txt, payments/, web/, openapi/, openspec/, docs/, AI_USAGE.md ni prompts/. Si necesitás otro archivo, pedímelo. Sin push.

CRITERIO DE TERMINADO (yo lo verifico)
 - Pruebas a-f existen, vistas fallar primero, todas pasan; las pruebas previas de api/ siguen con el mismo número.
 - Ninguna constante de moneda o escala en el código del cliente.
 - git status limpio; commits convencionales (feat(api): add the Node payments client, test(api): cover idempotency retries and polling).
 - Reporte: 1) resumen de 5 líneas; 2) commits y git diff --stat; 3) tabla regla del spec → prueba que la cubre; 4) pruebas vistas fallar; 5) versiones exactas de dependencias usadas; 6) lo que NO comprobaste; 7) hallazgos "esperaba X, pasó Y, cambio Z" contra spec y contrato; 8) preguntas D-n (máx 3).
````
