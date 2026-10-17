# Motor de decisión, PIN y parser de contextos (ML 2)

Piezas de ML 2 para el backend de EZPAY (Hackathon Open Payments 2026),
librería estándar de Python y pruebas con `unittest`. Fuente de verdad:
`openspec/changes/add-decision-engine/specs/{decision-engine,pin-validation}/spec.md`
y su `design.md`. La estructura de esta carpeta es idéntica a la de `api/`:
paquetes `decision/` y `pin/` en la raíz, pruebas en `tests/<módulo>/` **sin
`__init__.py`** (nombres de archivos de prueba únicos en todo el árbol, para
que `unittest` y `pytest` descubran sin colisiones con los paquetes).

```
decision/
  models.py        # Context, Decision (to_dict), Reason (enum cerrado, 28), Amount (CONV-1),
                   # InvalidContextError, parse_instant (ISO 8601 fail-closed)
  engine.py        # decide(context) -> Decision: función pura; tablas ordenadas de
                   # las fases COMMAND, PIN y CONFIRMATION (D1, D2)
  context_io.py    # parse_context(data: dict) -> Context (estricto, fail-closed) y
                   # decide_dict(data) -> {"decision", "reason"}
  say_map.py       # say_situation(decision, context): situación del catálogo de say de
                   # Voz (solo el NOMBRE; los textos viven en voice/phrases.py, ML 1)
pin/
  pin.py           # PinValidator (verify, reset_lock), verify_pin, reset_pin_lock,
                   # is_valid_pin, build_hash_spec
scripts/
  make_pin_hash.py     # alta del PIN: getpass -> EZPAY_PIN_HASH para .env
  reset_pin_lock.py    # reinicio del bloqueo (H1: contador en memoria del proceso)
tests/decision/        # motor y context_io (+ fixtures con las formas reales de Voz y de los mocks)
tests/pin/             # componente de PIN y script de alta
.env.example           # solo EZPAY_PIN_HASH= con comentario; sin valores reales
```

## Correr las pruebas

Desde `api/` (raíz de los paquetes):

```bash
PYTHONPATH=. python -m unittest discover -s tests/decision -v
PYTHONPATH=. python -m unittest discover -s tests/pin -v
```

Variante pytest (descubre ambos directorios con el mismo layout plano):

```bash
PYTHONPATH=. python -m pytest tests -q
```

Nota: con el layout plano (sin `__init__.py`), `unittest` descubre un
directorio de pruebas por corrida; `pytest` los toma todos de una vez.

## Cómo lo usa el orquestador

```python
from decision import decide_dict, parse_context, InvalidContextError, say_situation
from pin import verify_pin, reset_pin_lock

# 1. turno de comando: el orquestador arma el dict del context (design.md,
#    claves camelCase) con lo que le entregan Voz y Pagos
result = decide_dict(data)  # -> {"decision": "ASK_PIN", "reason": "VOICE_NOT_VERIFIED"}

# 2. turno de PIN: el resultado de verify_pin entra al context (context.pin)
result = verify_pin(pin, session_id)  # PinResult(result, sessionFailures, remaining, locked)
reset_pin_lock()                       # levanta el bloqueo global (script o ruta de admin)

# 3. qué dice el sistema: el único catálogo de textos es el de Voz
nombre = say_situation(decision, context)  # -> "PIN_KEYBOARD", "CONFIRM", None (CONFIRMED)...
voice.phrases.say(voice.phrases.Situation(nombre), **params_del_turno)
```

- **`decide_dict` / `parse_context`**: fail-closed. Cualquier desviación del
  contrato del `design.md` (clave faltante o desconocida, enum desconocido,
  `Amount.value` no ASCII-dígitos, `resolution.kind == "UNCLEAR"`, tipo
  incorrecto, fecha no ISO 8601) levanta `InvalidContextError` con mensaje
  fijo, sin datos del request. `decide(context)` levanta la misma excepción si
  el `Context` armado a mano es imposible (`quote` nula con grant activo,
  `quote` nula en CONFIRMATION con "sí", fecha mal formada). El orquestador
  trata `InvalidContextError` como **error interno: no se paga**.
- **`verify_pin`**: nunca devuelve `OK` sin `EZPAY_PIN_HASH` en `.env` (falla
  cerrado). El PIN no sale de Python: no va a logs, ni a `error.message`, ni
  fuera del backend.
- **`say_situation`**: función pura que traduce `(Decision, Context)` al
  NOMBRE de la situación del catálogo de Voz; los textos viven solo en
  `voice/phrases.py`. `VOICE_SITUATIONS_EXISTING` son las 21 situaciones que
  `Situation` ya tiene hoy; `VOICE_SITUATIONS_NEW` son las 13 que Voz agregará
  (once comparten nombre con su `reason`). Devuelve `None` solo para
  `CONFIRMED` (el `say` sale del resultado del pago). Una variante que necesita
  la `quote` (`CONFIRM`/`AUTH_OVERRUN`, `PENDING_PAYMENT_UNCONFIRMED*`), el
  `amountError` o las opciones de resolución y no los tiene levanta
  `InvalidContextError`: contexto imposible, no se paga.
- **Alta del PIN** (una vez, por configuración): `python scripts/make_pin_hash.py`
  lee el PIN con getpass y imprime `EZPAY_PIN_HASH=scrypt$N$r$p$sal_b64$hash_b64`
  para copiar a `.env` (ver `.env.example`). El PIN en claro no queda en ningún
  archivo del repo. En H1 el contador global vive en la memoria del proceso del
  backend: reiniciarlo lo resetea (persistencia diferida a H2).

## Formas de Voz que consume el motor

Voz (ML 1) entrega `intent` y `resolution` en camelCase, exactamente las
formas del `design.md`. Faltan datos ⇒ `status "UNCLEAR"` (nunca `OK` con
huecos): "Envíale plata a mi hija" ⇒ `{PAY, None, None, "mi hija", UNCLEAR}`;
"Hola" ⇒ `{UNKNOWN, None, None, None, OK}`; "Cancela" ⇒
`{CANCEL, None, None, None, OK}`; dos montos o dos destinatarios ⇒
`AMBIGUOUS`. `resolve_choice` puede devolver `{"kind": "UNCLEAR"}`, que **no**
llega al motor: `parse_context` lo rechaza como contexto inválido. Los
literales de prueba se copiaron de `api/tests/voice/test_context_shapes.py`
sin importar el paquete `voice`.

## Decisiones de implementación (registradas)

- **Un PIN correcto reinicia el contador global, no el de sesión** (decisión
  literal de D5/SEG-6: los fallos se cuentan por sesión). En una misma sesión,
  `fallo, fallo, OK, fallo` llega al 3.er fallo y el turno responde `REJECTED`.
  Además, una sesión con 3 fallos deja de validar intentos (defensa en
  profundidad, igual que el bloqueo global): ni siquiera el PIN correcto se
  valida en esa sesión hasta empezar otra sesión o reiniciar el backend.
- **Dígitos ASCII**: PIN y `Amount.value` se validan con ASCII estricto para
  que dígitos Unicode ("١٢٣٤", superíndices) no pasen por scrypt ni por el
  motor (CONV-1).
- **Concurrencia**: los contadores y el bloqueo van protegidos con
  `threading.Lock`; las sesiones memorizadas tienen tope de 1000 (se descarta
  la más antigua).
- **Fechas**: `now` y `pendingPayment.createdAt` aceptan ISO 8601 con `Z` o
  desplazamiento; sin zona se interpreta en UTC. Una fecha mal formada es
  contexto inválido (fail-closed, mensaje sin el valor recibido).

## Depurar con VSCode (opcional)

Si abres esta carpeta (`api/`) como workspace y hay un `.venv` disponible,
`.vscode/settings.json` deja el descubrimiento de unittest de `tests/decision`
y `launch.json` trae configuraciones para correr/depurar `tests/decision`,
`tests/pin`, un archivo suelto y los scripts del PIN (F5). Elegir el
intérprete con *Python: Select Interpreter*; para depurar una prueba concreta,
usar el icono de depuración del panel Testing.