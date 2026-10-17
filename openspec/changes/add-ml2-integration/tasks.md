## 1. Contratos y coordinación

- [ ] 1.1 Pagos y Frontend dan el OK al campo `challengePhrase` de `TurnResponse` (P3)
- [ ] 1.2 Pagos ratifica el cuerpo `{enrolled}` de `GET /api/enrollment` (P4) y `kind=verify_pending`
- [ ] 1.3 Voz agrega `CONFIRM_CHALLENGE_OVERRUN` y `CHALLENGE_FAILED` a `Situation`

## 2. Fachada (H3)

- [ ] 2.1 Pruebas de los escenarios de `voice-turn-integration`, escritas antes del código
- [ ] 2.2 Implementar `api/integration.py` (sin HTTP y sin estado)
- [ ] 2.3 La unidad 7 de Pagos integra la fachada

## 3. Calibración en la sala (H3)

- [ ] 3.1 X-7: frases del banco del desafío contra `minVerifySeconds` y el umbral
- [ ] 3.2 Enrolar a las 4 personas en la sala y medir 6 intentos genuinos y 6 de impostor por persona
- [ ] 3.3 Decidir con la regla de P7 y anotar el resultado en `docs/decisiones.md`

## 4. H4

- [ ] 4.1 Congelar los parámetros antes de las 10:45

## 5. Validación

- [ ] 5.1 `openspec validate add-ml2-integration --strict`
