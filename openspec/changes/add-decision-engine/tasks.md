## 1. Cierre de decisiones abiertas

- [ ] 1.1 Fijar `highAmountThreshold` con los experimentos X-2 y X-4 (por defecto `null`, desactivado)
- [ ] 1.2 Voz propone `minIntentConfidence` y `minTranscriptConfidence` tras su batería (por defecto `null`)
- [ ] 1.3 Pagos decide el aviso de la regla 6 pasada la ventana de `pendingWindowSeconds`
- [ ] 1.4 Persistir el contador global de fallos del PIN (hoy en memoria del proceso; limitación de H1)

## 2. H1 (viernes 14:00)

- [ ] 2.1 Pruebas de los escenarios de `decision-engine` y `pin-validation`, escritas antes del código
- [ ] 2.2 Implementar `decide(context)` en `api/` como función pura
- [ ] 2.3 Implementar `verify_pin`, `reset_pin_lock` y el script que genera el hash con sal
- [ ] 2.4 `api/.env.example` con los nombres de las variables del PIN, sin valores

## 3. Validación

- [ ] 3.1 `openspec validate add-decision-engine --strict`
