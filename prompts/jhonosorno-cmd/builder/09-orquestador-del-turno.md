# Builder 09 — Orquestador del turno (unidad 7)

Brief enviado el 17 de octubre de 2026 por el supervisor (Claude Code, sesión "coordinator") al
builder 2 (agente opencode "Configuración de Agente Constructor"). Aprobado por Alexander
(@jhonosorno-cmd) con "Ok al plan" tras el plan de la siguiente unidad.

---

````text
UNIDAD 7 — Orquestador del turno en api/app/ (voz + motor + PIN + cliente de Node)

OBJETIVO
Reemplazar la lógica mínima del esqueleto (api/app/turns.py y las rutas /api/turns, /api/budget y /api/grant-callback de api/app/main.py) por el orquestador real descrito en openspec/changes/add-payments-client/specs/turn-orchestration/spec.md: intención (api/voice) → agenda de contactos → verificación de voz → quote con api/payments_client → motor (api/decision) → transición de TurnState → llamadas a Node. Todo contra Node SIMULADO: nada de red real ni de Test Wallet en esta unidad.

PREPARACIÓN (rama)
git fetch origin; git switch -c payments/turn-orchestrator origin/main (sin upstream, sin push; ya incluye el esqueleto del PR #21 y tu cliente). En tu carpeta no existe api/requirements.txt hasta que traigas main: usalo. Entorno virtual en api/.venv. Antes de tocar nada corré y anotá cuántas pruebas hay: tests/app (34), tests/payments_client (50), tests/decision (129), tests/pin (35) con `PYTHONPATH=. python -m unittest discover -s tests/<modulo>` desde api/; tests/voice usa pytest (553).
Leé COMPLETO: el spec turn-orchestration (289 líneas), openapi/contract-b.yaml + components.yaml, api/README-ml2.md, api/decision/{models,engine,context_io,say_map}.py, api/pin/pin.py, api/voice/{intents,contacts,amounts,replies,phrases}.py y api/app/*. Para el Contrato A, tu propio api/payments_client.

QUÉ SE CONSTRUYE (por rebanadas; un commit por rebanada; pruebas primero y vistas fallar)
 R1) Puertos y ensamblado. Definí en api/app/ (módulo propio, p. ej. ports.py) protocolos para lo que NO existe todavía en el repo: Transcriber (audio → texto), SpeakerVerifier (audio → puntaje de similitud y estado de enrolamiento) y Clock. NO implementes reconocimiento de voz ni verificación de hablante reales: son de otros roles. Las pruebas usan dobles. Sin adaptador configurado, el servidor arranca igual y un turno de audio responde con el error del contrato que corresponda o REASK; decidilo con el spec, anótalo en el reporte y, si el spec no alcanza, D-n.
 R2) Contexto del motor. Armá el `context` exactamente como lo espera api/decision (parse_context; las formas reales están en tests/decision/fixtures). Citá en el reporte de dónde sale cada campo. Montos siempre {value:string de dígitos, assetCode, assetScale}, ASSET_CODE/ASSET_SCALE solo del entorno (api/app/config.py hoy los fija a COP/2: pasalos a variables de entorno con ese default solo para el arranque local; sin float, CONV-1).
 R3) Turno de comando por texto y por audio hasta ASK_CONFIRM/PAY/REJECT/REQUIRE_AUTH/ASK_RECIPIENT/ASK_PIN/REASK, con la tabla de transiciones del spec. La quote se pide antes del motor (excepto sin grant de presupuesto: quote=null). Mapeo Decision → TurnState → `say` por situación del catálogo de Voz (api/voice/phrases.say con el nombre que da say_map.say_situation); NINGUNA frase generada por un LLM.
 R4) PIN. AWAITING_PIN: el texto es el PIN; se valida localmente con api/pin (verify_pin con el sessionId; el hash viene del entorno EZPAY_PIN_HASH, nunca del repo); el PIN nunca se guarda en la sesión, ni se escribe en logs ni en excepciones; la respuesta lleva transcript null; el audio en AWAITING_PIN se descarta sin transcribir; PIN incorrecto e intentos agotados según el spec; dígitos fuera de AWAITING_PIN no van a ninguna extracción de intención.
 R5) Presupuesto y callback. POST /api/budget llama al cliente: create_grant (con el finishUri que corresponda; el origen del frontend es http://localhost:5173) y devuelve interactUrl; el grantId queda en la sesión (NO tokens). POST /api/grant-callback busca la sesión pendiente POR grantId/estado (no "la primera"), llama a continue_grant y pasa a AWAITING_COMMAND; sin interactRef/hash → REJECTED sin llamar a /continue (B-1); errores de Node (INVALID_HASH, GRANT_NOT_PENDING) según el spec o D-n. D-2 (aprobado a): sin sesión pendiente, sessionId "unknown" se mantiene. GET /api/budget lee de GET /v1/grants/{id}.
 R6) Pago. PAY / AWAITING_AUTHORIZATION: grant puntual con `one_off_interval(now)` (R1/<ahora>/P1W) cuando el pago excede el tope; Idempotency-Key = UUID por quote creado UNA vez y reutilizado en reintentos; PaymentPending nunca se muestra como rechazo (estado PAYMENT_PENDING y say de pago en camino); FAILED/COMPLETED de wait_for_payment; kind=verify_pending consulta el pago pendiente de la sesión (B-3..B-9 según el contrato). Tras un pago puntual, cancelar el grant con cancel_grant.
 R7) Historial de pagos por destinatario (previouslyPaid, D9), elección de destinatario ambiguo (resolve_choice) y decisión sobre el pago pendiente, según los requisitos del spec.

PRUEBAS (unittest, api/tests/app/; Node simulado con httpx.MockTransport o un doble de PaymentsClient con las respuestas del Contrato A; todas las respuestas de las rutas validadas contra contract-b.yaml)
 - Un escenario del spec por prueba, nombrada con el escenario. Los 34 tests actuales de tests/app deben seguir pasando, salvo los que dependían de la lógica mínima: si cambiás uno, explicá por qué en el reporte ("esperaba X, pasó Y, cambio Z").
 - Obligatorias: turno de pago completo en el orden del spec (un registro de llamadas lo demuestra); sin grant → quote null y REQUIRE_AUTH sin llamada de quote; PIN nunca en logs ni en la sesión ni en excepciones (capturá el logger con un PIN inventado); audio en AWAITING_PIN descartado; mismo Idempotency-Key en reintentos; PaymentPending ≠ rechazo; sin interactRef/hash no se llama a /continue.
 - No pongas contenido real: textos, nombres y montos inventados; nada de audio ni embeddings.

SEGURIDAD
 - Repo público: nada de .env, tokens, llaves, audio, embeddings ni transcripciones de voces reales. EZPAY_PIN_HASH solo del entorno; en pruebas, generá un hash con build_hash_spec de un PIN inventado.
 - Logs del turno: solo requestId, ruta, estado, duración (como hoy). Cero cuerpos, cero PIN, cero texto del usuario.
 - Revisá `git diff --cached` antes de commitear. CORS sigue solo http://localhost:5173.

ARCHIVOS PERMITIDOS
api/app/** (modificar y agregar), api/tests/app/**, api/requirements.txt (solo AGREGAR líneas con versiones exactas, si hiciera falta) y una o dos líneas en api/README.md sobre variables de entorno. NO toques api/voice, api/decision, api/pin, api/payments_client (si hay un bug ahí, reportalo; yo decido), api/scripts, web/, payments/, openapi/, openspec/, docs/, AI_USAGE.md ni prompts/. Sin push.

CRITERIO DE TERMINADO (yo lo verifico)
 - Todas las pruebas de tests/app existen, vistas fallar primero (por rebanada) y pasan; las previas de decision, pin, payments_client y voice siguen con los mismos números que anotaste.
 - uvicorn arranca (en segundo plano con timeout; NUNCA en primer plano: el builder 1 quedó bloqueado horas así) y una ronda de /api/budget + /api/turns de texto responde cuerpos válidos contra el contrato.
 - git status limpio; commits convencionales por rebanada (feat(api): ...).
 - Reporte: 1) resumen de 5 líneas; 2) commits y git diff --stat; 3) cada escenario del spec → la prueba que lo cubre (tabla); 4) pruebas vistas fallar; 5) qué NO comprobaste (todo lo que depende de voz real, STT, wallet real); 6) hallazgos "esperaba X, pasó Y, cambio Z" contra el spec y el contrato; 7) preguntas D-n (máximo 3, solo si el spec y el contrato no las resuelven).
Si una rebanada te lleva a un conflicto con el contrato o con otro rol (voz/motor), PARÁ y preguntame antes de inventar: no cambies contratos.
````
