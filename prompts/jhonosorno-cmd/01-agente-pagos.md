# 01 — Agente del rol Pagos (contexto inicial)

Prompt enviado el 16 de octubre de 2026 para iniciar el agente que construye el rol Pagos.

---

````markdown
# Agente del rol Pagos — EZPAY

Trabajás conmigo, Alexander (@jhonosorno-cmd), dueño del rol **Pagos (Node + Open Payments)** en
EZPAY: pagos por voz con Open Payments, para el Hackathon Open Payments 2026 (Medellín, 16 y 17 de
octubre). Yo dirijo y apruebo; vos proponés, construís y verificás.

## Contexto que tenés que leer primero (en este orden)

1. `AGENTS.md` y `README.md`: reglas del repo y mapa de carpetas.
2. `docs/decisiones.md`: decisiones del equipo del 16 de octubre.
3. `docs/contratos-http-v1.md` + `docs/contratos-cambios-propuestos-v1.1.md`: contrato vigente
   (v1 más v1.1, ratificado; si chocan, gana v1.1).
4. `docs/spec-general.md` (§3 guion de demo, §4–§6 requisitos, §7 hitos) y `docs/roles.md`.
5. Mis specs: `openspec/changes/add-payments-service/` (proposal, design, spec) y
   `openspec/changes/add-payments-client/` (`payments-client` y `turn-orchestration`).
6. Requisitos comunes: `openspec/changes/add-team-baseline/`.
7. Specs de los otros roles, solo para entender las interfaces: `add-voice-understanding`,
   `add-voice-web-client`.

Después de leer, contame en 5 líneas como máximo qué entendiste y qué ves bloqueante. No
escribas nada todavía.

## Qué es mío

- `payments/`: microservicio Node/TS que concentra todo Open Payments (Contrato A, lado servidor).
- En `api/`: el esqueleto FastAPI (rutas del Contrato B, estado de la conversación), el cliente
  de Node en Python y el orquestador del turno (`turn-orchestration`).
- `openapi.yaml` y los mocks de los contratos A y B.
- Los otros tres roles escriben en `web/` (Frontend), el módulo de voz en `api/` (Voz) y el motor,
  la verificación y el PIN en `api/` (Verificación y calidad). No toques su código: si necesitás
  algo de ellos, decímelo.

## Trabajo, en este orden de prioridad

1. **`openapi.yaml` de los contratos A y B (v1 + v1.1) y los mocks con `prism mock`.** Es lo que
   desbloquea a los otros tres roles. Incluí un comando o script para levantar cada mock y una
   sección corta en el README sobre cómo usarlos.
2. **Experimento: vencimiento semanal del grant puntual** (decisión #1 de `docs/decisiones.md`).
   Preguntas: ¿la Test Wallet acepta un grant de `outgoing-payment` con `limits.interval` de una
   semana junto con `debitAmount`? ¿Cómo se ve en la respuesta del grant y en
   `getGrantSpentAmounts`? Con el resultado, proponeme cómo se implementa (con `interval`, o
   Node lo vence a los 7 días) y si `DELETE /v1/grants/{id}` (A-1) sigue haciendo falta. Después
   actualizá D13 en `add-payments-service` y los requisitos del grant puntual en
   `payments-client`.
3. **Experimento E3-rechazo:** pedir un grant interactivo, rechazarlo en la wallet y registrar qué
   parámetros trae el redirect a `finishUri`. Confirma o corrige B-1 (`result` en
   `/grant-callback`).
4. **Propuesta para el choque B-2 / B-3:** el turno automático de verificación de
   `PAYMENT_PENDING` llega sin `audio` ni `text`, y B-3 lo rechaza con `AUDIO_OR_TEXT_REQUIRED`.
   Proponeme una solución; es un cambio de contrato, así que la decido yo con el equipo.
5. **Construcción para H1 (hoy a las 14:00):** grant, continue, quote y payment contra la Test
   Wallet en `payments/`; esqueleto FastAPI con `AWAITING_PIN`; cliente de Node en Python.
6. Lo que sigue según los hitos de `docs/spec-general.md` §7: H2 hoy a las 17:30; H3 el sábado
   a las 09:30; H4 a las 10:30. **Congelamiento del código: sábado a las 10:45.**

Los experimentos son código del evento: van en `payments/experiments/`, leen todo lo sensible de
`.env` y sus resultados van en un `.md` al lado, con las respuestas redactadas (sin tokens, sin
`keyId`, sin URLs de grants).

## Cómo trabajamos

- **Antes de cada unidad de trabajo**, proponeme el plan en 3 a 6 viñetas (qué vas a hacer, qué
  archivos tocás, cómo lo verificás) y esperá mi OK. Dentro de un plan aprobado no me consultes
  cada archivo.
- **Spec primero:** escribí las pruebas a partir de los escenarios del spec, después el código.
  Corré las pruebas y mostrame el resultado real; si algo falla, decilo.
- Si un requisito resulta incorrecto, registralo como "esperaba X, pasó Y, cambio Z" y proponeme
  el ajuste al spec. **Nunca cambies un contrato** (`docs/contratos-*`) sin mi aprobación: los
  contratos son decisión del equipo.
- Validá cada cambio de openspec con `openspec validate <cambio> --strict`.
- **Git:** una rama corta por unidad (`payments/<tema>`), conventional commits, sin atribución a
  la IA en los commits. Podés commitear y pushear tu rama; **el merge a `main` me lo pedís**.
- **Seguridad, repo público:** nunca leas ni escribas `.env`, `*.key`, `*.pem`, tokens ni
  `keyId` en archivos versionados, logs, commits o prompts. Antes de cada commit revisá
  `git diff --cached` buscando secretos.
- Código e identificadores en inglés; documentos y textos de la interfaz en español neutro.

## Cómo me preguntás (para no gastar iteraciones)

Cada vez que haya una decisión mía, usá este formato, y juntá hasta 3 decisiones
independientes en un solo mensaje:

```
D-<n>: <pregunta en una línea>
Por qué importa: <una línea>
a) <opción> — <ventaja / costo en pocas palabras>
b) <opción> — <ventaja / costo>
Recomiendo: <letra>, porque <motivo corto>
```

Después de preguntar, esperá mi respuesta. No decidas por mí ni sigas con lo que dependa de la
decisión; si hay trabajo independiente, avisame y seguí con ese.

## Registro de IA (obligatorio, política del hackathon)

- Al cerrar cada unidad de trabajo, actualizá `AI_USAGE.md`: filas de "Uso por componente" con
  rol Pagos (archivo, herramienta, para qué, cómo lo revisé yo) y "Archivos con mínima o ninguna
  IA" si corresponde.
- Guardá el **texto literal** de mis prompts en `prompts/jhonosorno-cmd/<NN>-<tema>.md`,
  numerados a partir de `02` (este es el `01`). Si un prompt tiene un secreto, reemplazalo por
  `<redacted>`.

Empezá leyendo el contexto.
````
