# Diseño — add-decision-engine

Material de referencia de las capabilities `decision-engine`, `pin-validation`, `speaker-verification`, `voice-enrollment`: trazabilidad, tablas y tipos que los requisitos citan, y puntos abiertos. Los requisitos y escenarios normativos están en `specs/`.

## Trazabilidad

### pin-validation
| Requisito | Origen |
| --- | --- |
| Alta por configuración, hash con sal, sin endpoint | D5 |
| Formato 4–6 dígitos, comparación en tiempo constante | D5 |
| Contadores de intentos (los lleva el componente de PIN) | SEG-6 ("PIN incorrecto tres veces" → `REJECTED`); D5; `turn-orchestration` "PIN incorrecto" |
| Privacidad del PIN | PRIV-4; `turn-orchestration` ("Audio en `AWAITING_PIN`", "Logs del turno…", "Respuesta de un turno de PIN", "Errores sin datos…", "El PIN nunca sale de Python") |
| `transcript: null` y `say` sin dígitos; `AWAITING_PIN` con intentos restantes | B-7, B-8 **[RATIFICADOS 2026-10-16]** (`docs/decisiones.md`, contratos v1.1); `turn-orchestration` |
| Entrada por campo `text` hasta H3 | Decisión #2 del 16 oct (`docs/decisiones.md`); B-8 |
| Interfaz `verify_pin` / `reset_pin_lock` | D5; decidida 2026-10-16 con ML 2, ML 1 y Pagos **[DECIDIDO]** |
| Persistencia del estado global (`EZPAY_PIN_DATA_DIR`, defecto `api/.data/pin/`, junto a la huella de voz) | Decisión de Daniel (2026-10-17) **[DECIDIDO]**; PRIV-1/PRIV-4 (nunca el PIN ni el hash en el archivo) |
| El motor recibe el resultado y no valida el PIN | D1, D5; `turn-orchestration` "Motor como función pura" |

## Detalle de `decision-engine`

#### El motor es una función pura y determinística

El motor SHALL exponerse como función pura `decide(context) -> Decision`, con `Decision = {decision, reason}`, sin HTTP, sin Node y sin reloj ni aleatoriedad propios (la hora llega en `context.now`). El mismo `context` MUST producir siempre la misma `Decision`. El mapeo a `TurnState` lo hace el orquestador, no el motor.

#### El contexto de entrada

El motor SHALL recibir todo lo que necesita en un único objeto `context` que arma el orquestador; el motor MUST NOT calcular nada del contexto. Los tipos y campos están en `design.md` (Contexto de entrada) y quedaron decididos el 2026-10-16 con ML 2, ML 1 y Pagos.

#### La Decision incluye un reason

Además del `decision`, el motor SHALL devolver un `reason`: un código estable en inglés de un enum cerrado (uno por regla o rama) que el orquestador usa como clave de la plantilla de `say`. El motor MUST NOT generar texto libre, usar el LLM ni incluir datos del request (PIN, montos, transcripciones, nombres) en el `reason`. La tabla regla → reason está en `design.md`.

#### Cada reason se asocia a una situación del catálogo único de Voz

Cada `reason` (salvo `CONFIRMED`) SHALL traducirse a una situación del catálogo único de `say` de Voz (`api/voice/phrases.py`, enum `Situation`); el orquestador inserta los valores y llama a `say` de Voz, y el motor MUST NOT generar texto. Un `reason` sin situación es un error de contrato. La tabla `reason` → situación y los textos de las 13 situaciones nuevas están en `design.md`.

#### Tabla de la fase COMMAND

En fase `COMMAND` el motor SHALL evaluar en orden las reglas 1, 2, 2b, 3, 4, 5, 6, 7, 8 y 9, y devolver la primera que aplique. Condiciones, decisiones y `reason` de cada regla están en `design.md` (Tabla de la fase COMMAND).

#### Tabla de la fase PIN

En fase `PIN` el motor SHALL decidir en orden: PIN bloqueado → `REJECT`; PIN correcto → `ASK_CONFIRM` (el PIN se suma al "sí", no lo reemplaza); incorrecto con menos de 3 fallos → `ASK_PIN`; con 3 fallos o más → `REJECT`; formato inválido o resultado nulo → `ASK_PIN`. El motor MUST NOT volver a evaluar la tabla de `COMMAND`. Detalle en `design.md`.

#### Tabla de la fase CONFIRMATION

En fase `CONFIRMATION` el motor SHALL decidir: "sí" → `REQUIRE_AUTH` si la quote excede el presupuesto, si no `PAY`; "no" → `REJECT`; respuesta poco clara o ausente → `ASK_CONFIRM` la primera vez y `REJECT` desde la segunda. El motor MUST NOT verificar la voz del "sí" (D4). Detalle en `design.md`.

#### El motor no obedece al LLM

La única regla que emite `PAY` SHALL exigir la fase `CONFIRMATION` y `reply == "YES"`. Ningún contenido del comando o de la respuesta MUST producir `PAY` por sí mismo (SEG-3).

#### El mapeo a TurnState no es del motor

El motor SHALL devolver solo el `{decision, reason}`. El orquestador MUST mapear `decision` a `TurnState`, ejecutar las llamadas a Node y usar el `reason` para elegir la plantilla de `say`; el texto nunca lo genera el motor ni el LLM. El mapeo está en `design.md`.

## Puntos abiertos

### speaker-verification y voice-enrollment (H2)
| Punto | Dueño / estado |
| --- | --- |
| Recalibración del umbral de verificación y del corte de consistencia (ambos 0.45) | H3 (sala de demostración) |
| Repetir el experimento con más personas (muestra actual: 3; margen del umbral pequeño, +0.104) | Siguiente batería |
| Actualizar el guion de demo de `docs/spec-general.md` §3 con la frase nueva ("Envíale veinte mil pesos a mi hija") | **[PARA EL EQUIPO]** — documento del equipo, necesita el OK de los cuatro |
