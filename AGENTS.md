# Instrucciones para agentes

Repo **público** del Hackathon Open Payments 2026. Antes de crear o editar archivos, identificá
con la persona qué rol tiene (ver `README.md` § Team members y `docs/roles.md`).

## Dónde escribir

| Rol | Código | Specs |
|---|---|---|
| Pagos (Node + Open Payments) | `payments/` y el cliente de Node + esqueleto FastAPI en `api/` | `add-payments-service`, `add-payments-client` |
| Frontend | `web/` | `add-voice-web-client` |
| Voz | módulo de voz en `api/` | `add-voice-understanding` |
| Verificación y calidad | motor, verificación de hablante y PIN en `api/`; pruebas de aceptación | (por crear) |

- `docs/`, `openspec/config.yaml` y `add-team-baseline` son del equipo: cambiarlos requiere el OK
  de los cuatro. Los contratos vigentes son v1; los cambios de
  `docs/contratos-cambios-propuestos-v1.1.md` no se implementan hasta que se ratifiquen.
- Cada persona registra sus prompts en `prompts/<usuario-github>/` (ver `prompts/README.md`).

## Reglas

- El código se escribe a partir del spec: primero las pruebas de los escenarios, después el código.
- Si un requisito resulta incorrecto, se anota "esperaba X, pasó Y, cambio Z" y se corrige el spec.
- **Repo público:** nunca escribas ni leas secretos (`.env`, `*.key`, `*.pem`, tokens), ni audio,
  embeddings o transcripciones de voces reales. Revisá `git diff --cached` antes de cada push.
- Código, identificadores y códigos de error en inglés; textos de la interfaz y de la voz en español.
- Ramas cortas, conventional commits, PR a `main`. Congelamiento del código: sábado 10:45.
