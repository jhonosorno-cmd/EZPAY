# 01 — Revisión del repo de pruebas y decisiones de ML 2

- Fecha: 14 al 15 de octubre de 2026 (antes del evento)
- Autor: Valdex328 (Daniel, rol Verificación y calidad, ML 2)
- Herramienta: Claude Code en Traycer

Sesión "Preparación Hackathon Interledger ML2". El primer prompt es la plantilla `prompts/pre-evento/revision-por-rol.md` con `{{PERSONA}}`=Daniel, `{{ROL}}`=ML2 y `{{CARPETA}}`=verificacion-ml2, más el pedido de un resumen. De esta sesión salieron las decisiones D1 a D9 de ML 2 (`docs/decisiones.md`).

Texto literal de los prompts de Daniel, en orden (sin las respuestas de la IA):

---

## Prompt 1

````text
```
Lee el siguiente repositorio. Cambia los siguientes atributos del resto del prompt:

- {{PERSONA}} por Daniel o @Valdex328
- {{ROL}} por ML2
- {{CARPETA}}/ por verificacion-ml2

Dame un resumen de lo que debo llevar preparado para la hackaton, pruebas que puedo realizar antes y puntos importantes a considerar.

Explícame de qué me debo encargar según mi rol

https://github.com/jhonosorno-cmd/Repo-de-pruebas-Interledger

# Revisión integral del repo — rol {{ROL}}

Sos el agente de revisión de {{PERSONA}}, que tiene el rol **{{ROL}}** (carpeta `{{CARPETA}}/`)
en un equipo de 4 que prepara el Hackathon Open Payments 2026 (16–17 oct, Medellín).

## Objetivo
Analizar el repositorio completo y proponer al equipo decisiones y cambios, con evidencia, desde la
perspectiva de tu rol. No decidís nada: preparás decisiones para que las tomen las personas.

## Reglas
- Leé TODO antes de opinar. Orden: `README.md` → `Spec general — PROPUESTA.md` →
  `Contratos HTTP v1 — Frontend ↔ Python ↔ Node.md` → `PLAN.md` → `openspec/` (`config.yaml`,
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
```
````

## Prompt 2

````text
los hallazgos me sirven como base y por ahora no quiero agregar ni quitar nada. Pero de las decisiones aún no editemos nada de las specs. <
````

## Prompt 3

````text
yo ayudaría más que todo a la parte de calibración de la voz y del reeconocimiento. Siento que tengo más experiencia en esa parte
````

## Prompt 4

````text
haz el documento de revisión y comitealo
````

## Prompt 5

````text
haz el push hacia el repositorio
````

## Prompt 6

````text
qué habíamos decidido sobre cuando solicitar el PIN?
````

## Prompt 7

````text
qué decisiones quedaron pendientes de tomar con Alex?
````

## Prompt 8

````text
revisa la rama de Alex revision/pagos-node y analiza si contesta las decisiones que debemos tomar
````

## Prompt 9

````text
acepta tu propuesta de la regla 4 con D2 para arreglar el choque.

añade el reask a sus decisiones.

el grant puntual vencería por semana, es una decisión tomada por el equipo.

Añade estos cambios a mi rama de revisión y haz commit y push
````

## Prompt 10

````text
trae el contexto de la sesión Instalación y configuración SpeechBrain
````

## Prompt 11

````text
según la documentación de OP de Interledger, cuando se va a definir un presupuesto con un grant, este grant debe aprobarse de manera interactiva en la wallet del usuario?
````

---
