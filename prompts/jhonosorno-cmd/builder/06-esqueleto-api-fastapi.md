# Builder 06 — Esqueleto FastAPI de `api/` (Contrato B)

Brief enviado el 17 de octubre de 2026 por el supervisor (Claude Code, sesión "coordinator") al
builder (agente opencode "Configuración Builder Pagos EZPAY"). Aprobado por Alexander
(@jhonosorno-cmd) con "OK al plan de la unidad 5. Mandale el brief al builder cuando termine la 4b."

---

````text
UNIDAD 5 — Esqueleto FastAPI de api/ (rutas del Contrato B, sesiones, AWAITING_PIN)

OBJETIVO
Dejar corriendo el servidor Python con las rutas del Contrato B y respuestas válidas contra openapi/contract-b.yaml, con un almacén de sesiones y el estado del turno. NO hay orquestador real todavía (unidad 7), NO se llama a Node (unidad 6) y NO se integran api/voice, api/decision ni api/pin. Cada ruta devuelve respuestas del contrato con lógica mínima y determinista.

PREPARACIÓN (rama)
git fetch origin; git switch -c payments/api-skeleton origin/main (sin upstream, sin push). La rama parte de main, que ya incluye voz, motor y PIN de otros roles. Leé api/README.md, api/README-ml2.md y openapi/contract-b.yaml + openapi/components.yaml. Las pruebas existentes de api/ usan unittest con `PYTHONPATH=. python -m unittest discover -s tests/<modulo>` desde api/: seguí ese estilo. Verificá que esas pruebas pasen ANTES de tocar nada y anotá cuántas son.

RUTAS (Contrato B, prefijo /api, puerto 8000)
 - POST /api/enrollment y GET /api/enrollment
 - POST /api/budget y GET /api/budget
 - POST /api/grant-callback
 - POST /api/turns (multipart: exactamente uno de `audio` o `text`; o `kind=verify_pending` con `sessionId` y sin audio ni texto)
Respondé con los códigos de estado y cuerpos de los ejemplos del contrato. Errores: {error:{code,message}} con los códigos del contrato (AUDIO_OR_TEXT_REQUIRED, SESSION_NOT_FOUND, etc.). Montos como {value:string de dígitos, assetCode, assetScale}, nunca floats (CONV-1). Header X-Request-Id si el contrato lo define.

SESIONES Y ESTADO
 - Almacén de sesiones en memoria (módulo propio, sin base de datos): crear, leer, expirar. SESSION_NOT_FOUND para sesión desconocida.
 - Estado del turno como enumeración con los estados del contrato (AWAITING_COMMAND, AWAITING_CONFIRMATION, AWAITING_PIN, AWAITING_RECIPIENT_CHOICE, AWAITING_AUTHORIZATION, COMPLETED, PAYMENT_PENDING, REJECTED).
 - En AWAITING_PIN, un turno con `text` se interpreta como PIN y la respuesta lleva `transcript: null` (B-7). El PIN NUNCA se guarda en el estado de la sesión ni se escribe en logs. En esta unidad NO valides el PIN real: solo la forma de la respuesta.
 - Logs del turno sin el cuerpo del request (ni audio, ni text, ni PIN): solo requestId, ruta, estado, duración.

DEPENDENCIAS
 - No existe archivo de dependencias en main. Creá api/requirements.txt con versiones EXACTAS (fastapi, uvicorn, python-multipart, httpx para TestClient, pyyaml y jsonschema para validar contra el contrato). Otros roles agregarán líneas al mismo archivo: hacé `git fetch origin` y revisá si ya existe en origin/main justo antes de commitear; si existe, solo AGREGÁ líneas, no reescribas. Entorno virtual en api/.venv (ya está ignorado por git).

PRUEBAS PRIMERO (unittest, en api/tests/app/; que se vean fallar antes del código)
 1. Una prueba por ruta (y por estado de turno): la respuesta se valida contra el esquema del contrato (openapi/contract-b.yaml con sus $ref a components.yaml).
 2. Errores: AUDIO_OR_TEXT_REQUIRED (ni audio ni texto, o ambos), SESSION_NOT_FOUND, y el error de formato del body.
 3. kind=verify_pending sin audio ni texto es válido; sin sessionId es error.
 4. AWAITING_PIN: el cuerpo de la respuesta tiene transcript null y el PIN no aparece en logs (capturá el logger) ni en el estado de la sesión.
 5. Los logs no contienen el cuerpo del request.

SEGURIDAD
 - Repo público: nada de .env, tokens, llaves, audio, embeddings ni transcripciones de voces reales. Los textos de prueba son inventados. Revisá `git diff --cached` antes de commitear.
 - CORS: solo http://localhost:5173 (el origen del frontend), no "*".

ARCHIVOS PERMITIDOS
api/app/** (nuevo), api/requirements.txt, api/tests/app/** y una línea nueva en api/README.md que diga cómo arrancar (`uvicorn app.main:app --port 8000`, desde api/) y cómo correr las pruebas. NO toques api/voice, api/decision, api/pin, api/scripts, web/, payments/, openapi/, openspec/, docs/, AI_USAGE.md ni prompts/. Sin push.

CRITERIO DE TERMINADO (yo lo verifico)
 - Las pruebas de api/tests/app/ existen, vistas fallar primero; todas pasan; las pruebas previas de api/ (decision, pin, voice) siguen pasando con el mismo número que anotaste.
 - El servidor arranca con uvicorn y GET /api/budget responde un cuerpo que valida contra el contrato.
 - git status limpio; commits convencionales (feat(api): add FastAPI skeleton for Contract B routes, test(api): validate responses against contract-b, docs(api): how to run the skeleton).
 - Reporte: 1) resumen de 5 líneas; 2) commits y git diff --stat; 3) rutas y estados cubiertos con la prueba que los cubre; 4) pruebas vistas fallar; 5) lo que NO comprobaste; 6) hallazgos "esperaba X, pasó Y, cambio Z" contra el contrato; 7) preguntas D-n (máximo 3, solo si el contrato no las resuelve).
````
