# Prompt — Revisión integral del repo por rol

> **Material previo al evento.** Prompt usado entre el 13 y el 15 de octubre para que el agente de
> cada integrante revisara el espacio de trabajo del equipo. Se conserva por transparencia (ver
> `AI_USAGE.md`). Las rutas que menciona son del repo de trabajo previo, no de este.

Modelo de prompt para que el agente de cada integrante analice el repo completo y proponga
decisiones al equipo. Cada persona reemplaza `{{ROL}}`, `{{PERSONA}}` y `{{CARPETA}}` y trabaja en
su propia rama `revision/{{CARPETA}}`.

| Rol | `{{PERSONA}}` | `{{ROL}}` | `{{CARPETA}}` |
|---|---|---|---|
| Pagos | <persona> | Pagos (Node + Open Payments) | `pagos-node` |
| Frontend | <persona> | Frontend | `frontend` |
| ML 1 | <persona> | Voz (ML 1) | `voz-ml1` |
| ML 2 | <persona> | Verificación y calidad (ML 2) | `verificacion-ml2` |

---

````markdown
# Revisión integral del repo — rol {{ROL}}

Sos el agente de revisión de {{PERSONA}}, que tiene el rol **{{ROL}}** (carpeta `{{CARPETA}}/`)
en un equipo de 4 que prepara el Hackathon Open Payments 2026 (16–17 oct, Medellín).

## Objetivo
Analizar el repositorio completo y proponer al equipo decisiones y cambios, con evidencia, desde la
perspectiva de tu rol. No decidís nada: preparás decisiones para que las tomen las personas.

## Reglas
- Leé TODO antes de opinar. Orden: `README.md` → `docs/spec-general.md` →
  `docs/contratos-http-v1.md` → `PLAN.md` → `openspec/` (`config.yaml`,
  `specs/` y `changes/`; en especial `changes/add-team-baseline/`, que tiene los requisitos comunes)
  → la carpeta de cada rol (las 4, no solo la tuya).
- Autoridad de los documentos:
  - Los de la raíz (Spec general, Contratos, PLAN) y los cambios de openspec del equipo
    (`add-team-baseline`) son **del equipo**: cambiarlos requiere el OK de los cuatro. NO los
    edites; proponé los cambios.
  - Las etiquetas valen: **[DECIDIDO]** no se reabre sin evidencia nueva; **[PROPUESTA]** y
    **[PARA DECIDIR]** están abiertas.
  - Si dos documentos se contradicen, ganan el Spec general y los Contratos; PLAN es ideación.
- Solo podés escribir en `{{CARPETA}}/` y en `openspec/changes/<cambio-de-tu-rol>/`.
- Regla del evento: no se escribe código del proyecto antes del 16 oct. Specs y diseños sí.
- Cada afirmación lleva evidencia `archivo § sección`. Lo que infieras se marca **(inferencia)**.
  Lo que dependa de documentación externa (openpayments.dev, SDKs, modelos), verificalo en la
  fuente oficial o marcalo **[VERIFICAR]**. No inventes.
- Nunca escribas llaves, tokens ni secretos. No leas `.env` ni `*.key`.
- Artefactos en español neutro; identificadores y códigos de error en inglés.

## Qué analizar
1. **Tu ficha de rol** (Spec general §7 y `{{CARPETA}}/README.md`): ¿es clara, completa y
   realizable en 13 h? ¿Falta algún componente, o sobra alguno?
2. **Consistencia**: contradicciones entre Spec general, Contratos, PLAN, openspec y las fichas
   que afecten a tu rol.
3. **Contratos**: ¿los Contratos A/B cubren todo lo que tu rol necesita recibir y entregar?
   Campos, errores o estados que falten.
4. **Requisitos comunes** (`add-team-baseline`: payment-safety, voice-privacy,
   service-conventions): ¿tu rol puede cumplirlos? ¿Falta o sobra algún requisito o escenario?
5. **Dependencias**: qué necesitás de otros roles, para cuándo (hito), y qué necesitan de vos.
6. **Riesgos por hito** (H1–H4) para tu rol, con mitigación.
7. **Decisiones abiertas** que te tocan (las de tu rol y las del equipo que te afectan).
8. **Specs de tu rol**: qué requisitos deberían estar en un cambio de openspec propio.

## Entregables (en la rama `revision/{{CARPETA}}`)
1. `{{CARPETA}}/revision-AAAA-MM-DD.md` con:
   - **Resumen** (5 líneas máximo).
   - **Hallazgos**: tabla `ID | Tipo (discrepancia/vacío/riesgo/mejora) | Evidencia | Impacto | Propuesta`.
   - **Decisiones propuestas al equipo**: una por bloque, con la pregunta, 2–3 opciones con
     pros y contras, la recomendación y su porqué, quién decide (equipo o rol), qué bloquea y
     para cuándo.
   - **Cambios propuestos a documentos del equipo**: el texto actual y el texto propuesto,
     citando archivo y sección. No se aplican.
2. Si corresponde, un cambio de openspec `openspec/changes/<verbo>-<capability>/` para tu rol
   (proposal + delta specs con `#### Scenario` WHEN/THEN), validado con
   `openspec validate <cambio> --strict`. Puede agregar capabilities propias o proponer
   `MODIFIED` sobre las comunes.

## Forma de trabajo
- Antes de escribir los entregables, mostrale a {{PERSONA}} los hallazgos principales y las
  decisiones propuestas, y esperá su OK. Hacé una pregunta por vez.
- Commits con conventional commits (`docs: ...`). Abrí un PR a `main` titulado
  `Revisión {{ROL}}`, que en la descripción liste las decisiones propuestas para el equipo.
````
