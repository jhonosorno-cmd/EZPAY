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

_Pendiente: se completa durante el evento._

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
