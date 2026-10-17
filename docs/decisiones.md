# Registro de decisiones del equipo

Decisiones tomadas por los cuatro. Formato: qué se decidió, por qué y qué cambia. Las decisiones
de un solo rol viven en el spec de ese rol.

## 2026-10-16 — Contratos v1.1 ratificados

Los cambios A-1 a A-3 y B-1 a B-9 de `contratos-cambios-propuestos-v1.1.md` quedan ratificados por
los cuatro. Contrato vigente: v1 más v1.1. Las novedades que surjan se deciden en equipo.

## 2026-10-16 — Decisiones de Verificación y calidad (ML 2)

| # | Tema | Decisión | Qué cambia |
|---|---|---|---|
| 1 | Vencimiento del grant puntual del exceso de límite | **Vence por semana** | La decisión de equipo no cambia. Cómo se implementa, **cerrado el 17 oct**: `limits.interval = R1/<momento de la solicitud en UTC>/P1W` (siempre `R1`) y se sigue cancelando con `DELETE /v1/grants/{id}` (A-1), que Node implementa con `grant.cancel`. Evidencia: `payments/experiments/weekly-interval-and-token.md` y `cancel-grant.md`. Ver "Pendientes" |
| 2 | Comando por texto (D3) | **Siempre pide PIN**, sin modo de desarrollo | El PIN mínimo pasa de H3 a H1. Hasta que exista el teclado, el PIN se escribe en el campo de texto (`AWAITING_PIN` → `text`) |
| 3 | Verificación del "sí" (D4) | **Solo se verifica el comando**, no el "sí" | El "sí" (~0,5 s) no alcanza para verificar: con 1,5 s los puntajes ya se solapan |
| 3b | Puntaje de confianza por pipeline | **Cada pipeline entrega un puntaje de confianza.** Riguroso en la extracción de intención; más flexible en la transcripción | Requisito nuevo para `add-voice-understanding` (`intent-extraction` y `speech-transcription`) y campo nuevo en el contexto del motor. **[PARA DECIDIR]** los valores de corte (rol Voz) |
| 4 | Destinatario nuevo (D9) | **Sin un pago `COMPLETED` previo**, con Laura sembrada como conocida | El esqueleto FastAPI guarda la lista de destinatarios con pagos completados y se la pasa al motor (`previouslyPaid`) |
| 5 | Errores de `/enrollment` (D8, cambio B-5) | Revisados por el equipo | Ver `contratos-cambios-propuestos-v1.1.md` |
| 6 | Reparto de carga (D7) | Respaldo del esqueleto FastAPI: **Frontend**. Consolida `AI_USAGE.md`: **Voz (ML 1)**. Ejecuta las pruebas de aceptación: **Frontend** (no las corre quien escribe el motor) | ML 2: motor y PIN en H1; enrolamiento, verificación y calibración en H2–H3. Ver `roles.md` y `spec-general.md` §7 |

Decisiones del rol ML 2 que el equipo escuchó (las toma ML 2): tabla de reglas del motor (D2: el
PIN se suma al "sí"; un pago que excede el presupuesto no pide PIN por monto), diseño del PIN (D5)
y umbral de voz 0.45 provisional (D6), que se fija en la sala con el micrófono de solapa.

### Pendientes de estas decisiones

- ~~**Grant puntual semanal**~~ **(cerrado el 17 oct).** Se pide con `limits.interval =
  R1/<momento de la solicitud en UTC>/P1W` (siempre `R1`; `R` o `Rn` renovarían el tope) y se
  sigue cancelando al usarlo, al descartarlo o al reemplazarlo con `DELETE /v1/grants/{id}`
  (A-1), que Node implementa con `grant.cancel`. El final de la semana no se prueba contra la
  Test Wallet: Node marca el grant `EXPIRED` cuando termina su intervalo. Evidencia:
  `payments/experiments/weekly-interval-and-token.md` y `cancel-grant.md`. La decisión de equipo
  #1 no cambia, solo se define cómo se implementa; no hay cambio de contrato (`limit.interval` ya
  es opcional en el Contrato A y A-1 está ratificado).
- **ML 2 crea `openspec/changes/add-decision-engine/`** con `decision-engine`,
  `speaker-verification`, `voice-enrollment` y `pin-validation`. Sin ese cambio no hay spec para
  el motor de H1.
- **Rol Voz** agrega el puntaje de confianza a `intent-extraction` y `speech-transcription`.
