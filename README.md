# EZPAY

Pagos por voz con Open Payments. Pagar hablando, dentro de un presupuesto que la usuaria autorizó una sola vez en su wallet.
Proyecto del Hackathon Open Payments 2026 (Medellín, 16 y 17 de octubre).

## Links

* Presentation: _pendiente_
* Demo: _pendiente_

## How it works

Las apps de pago asumen que la persona lee, escribe y navega interfaces complejas. Para adultos
mayores, personas con baja alfabetización o con discapacidad visual, eso las deja afuera. Acá la
usuaria dice "envíale veinte mil a mi hija", el sistema repite el monto y el destinatario, y paga
solo después de un "sí" explícito.

La voz **nunca** autoriza un pago. La usuaria aprueba una vez, en su wallet, un grant GNAP de
Open Payments con un tope de monto. Los comandos de voz pagan solo dentro de ese tope; si un pago
lo supera, se vuelve a pedir la aprobación en la wallet. Decide un motor de reglas determinístico,
no el LLM, que solo extrae la intención. La verificación de hablante agrega un factor extra
(PIN) cuando la voz no coincide.

Arquitectura: web app (`web/`) → backend Python con FastAPI (`api/`: transcripción, intención,
verificación de hablante, motor de decisión) → microservicio Node (`payments/`) que concentra
todo Open Payments → Test Wallet de Interledger. Los contratos entre servicios están en
[`docs/contratos-http-v1.md`](docs/contratos-http-v1.md) y los specs en [`openspec/`](openspec/).

## How to run

Tres procesos: Node (Open Payments) en 4000, Python (FastAPI) en 8000 y la web en 5173.

```bash
# 1. Node: wallet de Marta (la que paga) con su llave de desarrollador de la Test Wallet
cd payments && npm install && cp .env.example .env   # WALLET_ADDRESS, KEY_ID, PRIVATE_KEY_PATH, DB_ENCRYPTION_KEY
npm start
# 2. Python: orquestador, voz (Groq), motor, PIN y verificación de hablante
cd api && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env   # GROQ_API_KEY, EZPAY_PIN_HASH (scripts/make_pin_hash.py), EZPAY_SPEAKER_MODEL_DIR
.venv/bin/uvicorn app.main:app --port 8000
# 3. Web
cd web && npm install && npm run dev   # http://localhost:5173
```

En la web: **Mis contactos** → agregar a Laura con `https://ilp.interledger-test.dev/laura` (la
wallet se valida contra Open Payments), autorizar el presupuesto en la wallet de Marta y decir
"envíale veinte mil a Laura". Sin Node real, `npm run mock:a` en la raíz simula el Contrato A.

### Mocks de los contratos

Mientras un servicio no exista, se trabaja contra su mock (Prism, generado desde
[`openapi/`](openapi/)). Requiere Node 24.

```bash
npm install
npm run mock:a   # Contrato A (Node) en 127.0.0.1:4000, para Python
npm run mock:b   # Contrato B (Python) en 127.0.0.1:8000, para el frontend
```

Para pedir otra respuesta, un estado o un error concreto (`Prefer: code=…, example=…`) y los
límites del mock, ver [`openapi/README.md`](openapi/README.md).

## Team members

* [jhonosorno-cmd](https://github.com/jhonosorno-cmd) — Pagos (Node + Open Payments)
* [rualesjuan-ui](https://github.com/rualesjuan-ui) — Frontend
* [Sebasruiz00](https://github.com/Sebasruiz00) — Voz
* [Valdex328](https://github.com/Valdex328) — Verificación y calidad

## Learnings

_Pendiente._

## Achievements

_Pendiente._

## What comes next?

_Pendiente._

---

## Para el equipo

| Ruta | Qué hay |
|---|---|
| `web/`, `api/`, `payments/` | Código, escrito durante el evento |
| `docs/` | Spec general, roles, contratos y cambios propuestos (v1.1), diseño de voz |
| `openspec/` | Specs por capability (`openspec validate <cambio> --strict`) |
| `prompts/` | Texto real de los prompts del evento, por persona |
| `AI_USAGE.md` | Uso de IA, incluido el trabajo previo al evento |

Reglas de trabajo: [`AGENTS.md`](AGENTS.md).
