# Resultados del módulo de voz (ML 1) — 2026-10-17

Estado de `api/voice/` al cierre del Paso 2 de las capabilities de H1, más el catálogo único de `say`
(ver "Cambios posteriores"). Lo escribió Claude Code (Claude Opus 5.5; Claude Sonnet 5.5 en los cambios
posteriores) con revisión de Sebastián pendiente salvo en `amount-parsing` (ver `AI_USAGE.md`).
Pruebas del módulo: desde `api/`, `PYTHONPATH=. .venv/Scripts/python.exe -m pytest tests/voice -q`.
Con el motor y el PIN de ML 2 (`tests/decision`, `tests/pin`) la suite completa de `api/` suma 771.

## Pruebas por capability

| Capability | Archivo de código | Archivo de pruebas | Pruebas que pasan |
|---|---|---|---|
| `amount-parsing` | `amounts.py` | `test_amounts.py` | 191 |
| `reply-classification` | `replies.py` | `test_replies.py` | 72 |
| `say` (catálogo de `contrato-voz.md` §7 con `PAYMENT_PENDING` de v1.1, más las 13 situaciones del motor: 34 en total) | `phrases.py` | `test_phrases.py` | 89 |
| `speech-transcription` (H2: `transcribe` y motores) | `transcribe.py`, `engines.py` | `test_transcribe.py`, `test_engines.py` | 55 |
| `contact-resolution` | `contacts.py`, `agenda_provisional.json` | `test_contacts.py` | 55 |
| `intent-extraction` (solo reglas, sin LLM; "o" = dos montos o destinatarios) | `intents.py` | `test_intents.py` | 105 |
| Forma para el motor: `to_dict()` con los nombres del `context` de ML 2 | `intents.py`, `contacts.py` | `test_context_shapes.py` | 19 |
| Todo el paquete: sin LLM, sin red, sin disco, sin float | `text.py`, `config.py` | `test_package.py` | 21 |
| **Total del módulo** | | | **607** |

## Cobertura de la gramática de intención (`docs/voz/frases-desarrollo.md` §D, 30 frases)

- 28 de 30 coinciden con la tabla (las inyecciones 22, 24 y 25 dan `UNKNOWN`, aceptado).
- 2 difieren sin pagar: la 23 ("Paga sin confirmar…") y la 26 (dos oraciones) dan `PAY UNCLEAR`
  en vez de `OK`, por decisión (gramática estricta).
- 0 difieren y pagan.

## Entradas hostiles (resumen; las listas están en los archivos de pruebas)

| Capability | En pruebas | Ejecutadas en la revisión adversarial | Categorías |
|---|---|---|---|
| `amount-parsing` | 26 + 11 dígitos no ASCII + 5 no-texto | 29 | dígitos Unicode, separadores con espacio, dos montos, desbordes, jerga mal configurada, tipos inválidos |
| `reply-classification` | 10 + 5 no-texto | 12 | invisibles y de control, otros alfabetos, mezclas sí/no, textos largos |
| `say` | 9 textos raros en `NOT_FOUND` + 16 parámetros inválidos (+ 16 de las situaciones nuevas, sin revisión adversarial aparte) | 10 | URL o payment pointer leídos en voz alta, nombres vacíos, tipos inválidos |
| `contact-resolution` | 9 + 1 homoglifo + 6 agendas mal formadas | 13 | wallets, payment pointers, correos, dominios, ancho completo, repeticiones |
| `intent-extraction` | 19 + 5 no-texto | 15 | inyección, wallets, dígitos no ASCII, signo menos, varias oraciones, retractación ("…, cancela") |

## Fallos graves encontrados y corregidos

1. `amount-parsing` (revisión del 16 oct): sumas silenciosas ("20 000" = 20 pesos, "veinte mil y
   treinta mil" = 50.000), excepciones con dígitos Unicode y valores no ASCII. Corregido (H-1 a H-6).
2. `intent-extraction` (prototipo): "envíale -20 mil a Laura" pagaba 20 mil. Corregido: el guion junto a
   un número queda como carácter inválido.
3. `say`: con `name` vacío o `None` decía "¿Le envío 20.000 pesos a ?" (confirmación sin destinatario,
   SEG-2). Corregido: `ValueError`.
4. `intent-extraction`: "Envíale 20 mil a Laura, cancela" daba `PAY OK`. Corregido: una negación o un
   verbo de cancelar en el destinatario deja `UNCLEAR`.

## Cambios posteriores (2026-10-16, tras fusionar `origin/main`)

- **Catálogo único de `say`** (decisión de ML 2, PR #5): `phrases.py` agrega 13 situaciones con el mismo
  nombre que el `reason` del motor: `INTENT_AMBIGUOUS`, `INTENT_LOW_CONFIDENCE`,
  `TRANSCRIPT_LOW_CONFIDENCE`, `PENDING_PAYMENT_SAME_RECIPIENT`, `PENDING_PAYMENT_UNCONFIRMED`,
  `PENDING_PAYMENT_UNCONFIRMED_OVERRUN`, `NEW_RECIPIENT`, `HIGH_AMOUNT`, `PIN_WRONG`,
  `PIN_ATTEMPTS_EXHAUSTED`, `PIN_LOCKED`, `PIN_INVALID_FORMAT` y `REPLY_UNCLEAR_REJECTED`. Los textos son
  los de `openspec/changes/add-decision-engine/design.md`. Con las 21 anteriores son 34, y coinciden
  exactamente con las que traduce `say_situation` de ML 2 (no falta ni sobra ninguna).
- **`PIN_KEYBOARD`** pasa a "Por seguridad, escribe tu PIN en el teclado." (no dice que la voz no coincide).
- **Parámetros nuevos de `say`:** `PIN_WRONG(remaining >= 1)`, `NEW_RECIPIENT(name)`,
  `PENDING_PAYMENT_SAME_RECIPIENT(name)`, `PENDING_PAYMENT_UNCONFIRMED(amount, name)` y
  `PENDING_PAYMENT_UNCONFIRMED_OVERRUN(name)`; las demás no llevan parámetros. La palabra de la moneda
  sigue saliendo de la configuración.
- **Costo del recibo:** `COMPLETED` dice el costo como débito − recibido, con enteros ("Te costó 150 pesos"),
  como pide `payments-client` y como muestran `contract-b.yaml` y la web. Antes decía el débito total.
  Un débito menor que lo recibido es `ValueError`.

## H2: transcripción (2026-10-17)

- **`transcribe`** (`transcribe.py`): valida el audio en memoria (WAV y WebM/Opus; más de 30 s es `AUDIO_TOO_LONG`, bytes
  ilegibles `INVALID_AUDIO`), descarta el no-habla con un filtro local, manda a Groq solo con `consentExterno` y cae al motor
  local si Groq falla, tarda o limita (429). Entrega `Transcript` con `transcriptConfidence = null`.
- **Motores reales** (`engines.py`): `av` decodifica a PCM float32 16 kHz mono; Groq `whisper-large-v3-turbo` por `urllib`; respaldo
  `faster-whisper base` en CPU. `GROQ_API_KEY` solo se lee del entorno; nada se escribe a disco. Dependencias en
  `api/requirements.txt`: `faster-whisper`, `av`, `numpy` y `ctranslate2`.
- **Escrito por el agente Builder** (OpenCode) y revisado por Claude Code: 771 pruebas de `api/` pasan, y al invertir la regla del
  consentimiento fallan 7. Las pruebas no llaman a Groq ni descargan modelos.
- **Prueba a mano con voz real** (Sebastián, `scripts/grabar_y_transcribir.py`, 10 frases, micrófono Conexant del portátil):

| Prueba | Local (`base`) | Groq |
|---|---|---|
| "Envíale veinte mil a Laura hija" | "envíale 20.000 a la hora ya" (destinatario mal oído) | "Envíale 20.000 a Laura Hija" (pago de 20.000 a `laura hija`) |
| "Mándale cincuenta mil pesos a mi mamá" | correcto | correcto |
| "Sí" / "Confirmo" | "C" / "¡Pero no!" (`UNCLEAR`) | "Sí" (`YES`) / "Confirma." (`UNCLEAR`) |
| "No" / "Cancela" | "No." (`NO`) / "Cancella" (`UNCLEAR`) | `NO` / `NO` |
| Silencio | texto vacío, sin voz | "Gracias." con voz (alucinación sobre el ruido del cuarto; `UNCLEAR`) |
| Con ruido de fondo | texto sin sentido (`UNKNOWN`) | "Pero igual eso también. Envíale 20 mil a Laura, hija." (`UNCLEAR`: no paga y vuelve a preguntar) |

- **Conclusión:** Groq acierta nombres y respuestas cortas; el local es solo respaldo y falla en nombres. Ninguna frase mal oída
  produjo un pago equivocado. Una sola grabación de 8,9 s dio "por pagar ciento" (`UNKNOWN`); probablemente la frase se cortó al grabar; no se investigó.
- **Pendiente de H2:** integración al esqueleto FastAPI (sin código todavía), prueba del navegador real (X-4: muestra de audio de
  la web) y la prueba con el ruido real de la sala.
- **Pendiente para H3:** subir el umbral del filtro de no-habla (el ruido del cuarto pasa y Whisper inventa "Gracias."), añadir
  "confirma" y "confirmo" a los afirmativos (necesita el OK del equipo, P-11) y aceptar la última oración cuando la frase trae
  relleno antes del pedido.

## Riesgos conocidos y pendientes menores

- `20,000` se lee como 20 pesos (regla es-CO del spec, H-4). Lo cubre la confirmación hablada con la cifra.
- "la ura" (nombre partido por la transcripción) da `NOT_FOUND` en vez de ofrecer las dos Lauras. Seguro.
- "…a Laura vecina gracias" deja "gracias" en el destinatario, y la agenda no lo encuentra. Seguro.
- "José" con un carácter invisible pegado se resuelve a José (el invisible separa palabras). La
  confirmación hablada sigue siendo obligatoria.
- La agenda es provisional y ficticia (`ezpay-placeholder-*`). Pagos la reemplaza antes de la demo.
- Los ejemplos de `say` de `contract-b.yaml` ("¿Le envío 20 mil a Laura?") difieren del catálogo
  ("20.000 pesos"); es un ejemplo del mock y lo corrige Pagos.
- Los puntajes de confianza (3b) siguen sin implementar: `minIntentConfidence` y `minTranscriptConfidence`
  quedan en `null` en H1.

## Fuera de este módulo (para Pagos y ML 2)

"Sí tardío", `AWAITING_PIN` (el PIN nunca llega aquí), errores HTTP de `/turns`, actualización de
`previouslyPaid`, "no se hace ninguna cotización" y repetir las opciones tras una elección `UNCLEAR`.
La traducción `reason` → situación es `say_situation` (ML 2); el orquestador pone los parámetros
(`remaining`, `amount`, `name`, `scale`, `spoken`, `names`) y llama a `say`.
