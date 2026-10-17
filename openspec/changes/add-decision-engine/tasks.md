## 1. Cierre de decisiones abiertas

- [x] 1.1 Fijar `highAmountThreshold` con los experimentos (100.000 COP, X-4 del 17 oct)
- [ ] 1.2 Voz propone `minIntentConfidence` y `minTranscriptConfidence` tras su batería (por defecto `null`)
- [ ] 1.3 Comunicar a Pagos la regla 6b (aviso de pago no confirmado pasada la ventana) y confirmar el texto de su plantilla
- [x] 1.4 Persistir el contador global de fallos del PIN (`EZPAY_PIN_DATA_DIR`, por defecto `api/.data/pin/`)

## 2. H1 (viernes 14:00)

- [x] 2.1 Pruebas de los escenarios de `decision-engine` y `pin-validation`, escritas antes del código
- [x] 2.2 Implementar `decide(context)` en `api/` como función pura
- [x] 2.3 Implementar `verify_pin`, `reset_pin_lock` y el script que genera el hash con sal
- [x] 2.4 `api/.env.example` con los nombres de las variables del PIN, sin valores

## 3. Validación

- [x] 3.1 `openspec validate add-decision-engine --strict`

## 4. H2 (verificación de hablante y enrolamiento)

- [x] 4.1 Experimento X-3: huella como promedio o como máximo por muestra
- [x] 4.2 Experimento X-2: medir `minVerifySeconds` y la duración de la frase de la demo
- [x] 4.3 Verificar que el modelo carga sin internet y que una verificación responde en menos de 1 s
- [x] 4.4 Pruebas de los escenarios de `speaker-verification` y `voice-enrollment`, escritas antes del código
- [x] 4.5 Implementar `embed`, `verify`, enrolamiento, persistencia y borrado de la huella en `api/`
- [ ] 4.6 H3: recalibrar el umbral y el corte de consistencia con el micrófono de solapa
