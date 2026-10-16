## Why

Los requisitos que afectan a todo el equipo (seguridad del pago, privacidad de la voz y
convenciones entre servicios) viven solo en el markdown `docs/spec-general.md`. Sin una
base en `openspec/specs/`, los cambios de cada rol no pueden expresarse como deltas (`MODIFIED`)
sobre requisitos comunes, y cada servicio los repite a su manera (por ejemplo, `payments-service`
copia las convenciones).

## What Changes

- Se pasan a OpenSpec, sin cambiar su contenido, las secciones §4 (SEG-1 a SEG-6), §5 (PRIV-1 a
  PRIV-4) y §6 (CONV-1 a CONV-6) del Spec general.
- Los escenarios "Dado / cuando / entonces" se reescriben como WHEN / THEN.
- Se agregan escenarios donde el Spec general no tenía (PRIV-3, PRIV-4, CONV-1 a CONV-6) y unos
  pocos casos que se derivan del texto del requisito (silencio en SEG-2, destinatario desconocido
  en SEG-4). Ningún requisito cambia; el equipo revisa los escenarios nuevos.
- Quedan fuera, porque no son requisitos de comportamiento: problema y usuaria, guion de demo,
  roles, hitos, forma de trabajo y preguntas a la organización. Siguen en el Spec general.
- Quedan fuera los Contratos HTTP v1: son un anexo del Spec general y se referencian, no se copian.

Requisitos que en el Spec general están marcados **[PROPUESTA]** y necesitan el OK explícito del
equipo antes de archivar este cambio: la regla "todo lo que no sea un sí claro es un no" (SEG-2),
PRIV-3, PRIV-4 y CONV-1 a CONV-6.

## Capabilities

### New Capabilities

- `payment-safety`: reglas que impiden pagar sin autorización, sin confirmación o con un
  destinatario adivinado (SEG-1 a SEG-6).
- `voice-privacy`: tratamiento de la biometría de voz según la Ley 1581 de 2012 (PRIV-1 a PRIV-4).
- `service-conventions`: convenciones comunes a frontend, Python y Node (CONV-1 a CONV-6).

### Modified Capabilities

Ninguna: `openspec/specs/` está vacío.

## Impact

- Todos los roles: sus cambios de openspec referencian o modifican estas capabilities.
- `payments-service` (cambio `add-payments-service`): después de archivar este cambio, su spec se
  achica para remitir a `service-conventions` en vez de repetirla (Spec general §10).
- Sin código: es un cambio solo de specs.
