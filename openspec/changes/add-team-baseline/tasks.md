## 1. Aprobación del equipo

- [ ] 1.1 Cada rol revisa este cambio en su rama `revision/<rol>` y deja sus propuestas en su revisión
- [ ] 1.2 El equipo ratifica los requisitos marcados [PROPUESTA] en el Spec general (SEG-2, PRIV-3, PRIV-4, CONV-1 a CONV-6)
- [ ] 1.3 Se incorporan los cambios acordados y se valida con `openspec validate add-team-baseline --strict`

## 2. Cierre

- [ ] 2.1 Se archiva el cambio con `openspec archive add-team-baseline` (crea `openspec/specs/`)
- [ ] 2.2 El Spec general §4–§6 pasa a remitir a `openspec/specs/` en vez de repetir los requisitos
- [ ] 2.3 El spec de `payments-service` se achica para remitir a `service-conventions`
