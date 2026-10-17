## 1. Aprobación del equipo

- [x] 1.1 Ratificados A-1 a A-3 y B-1 a B-9 (16 oct; `docs/decisiones.md`, `docs/contratos-cambios-propuestos-v1.1.md`)
- [ ] 1.2 El equipo ratifica el mecanismo `kind=verify_pending` del turno de verificación de `PAYMENT_PENDING` ([DECIDIDO por Voz, 2026-10-16]; hoy `x-proposed` en `openapi/contract-b.yaml`, ya enviado por `postVerifyPending` en `origin/feat/web-skeleton:web/src/api/client.ts`). Dueño de la propuesta: Sebastián; dueño del contrato: Pagos
- [ ] 1.3 El equipo revisa las propuestas a `docs/` de este cambio (catálogo de `say` §7, extracción solo con reglas, frases de desarrollo §D). Dueño: Sebastián
- [ ] 1.4 El equipo ratifica la lista cerrada de afirmativos ([DECIDIDO por Voz, 2026-10-16], tal como está implementada en `docs/voz/contrato-voz.md` §8 y `api/voice/replies.py`; P-11). Dueño de la propuesta: Sebastián
- [ ] 1.5 Se validan los specs con `openspec validate add-voice-understanding --strict`. Dueño: ML 1 (valida la sesión padre)

## 2. Experimentos descartables previos al evento (sin código en el repo)

- [ ] 2.1 X-1 a X-5 de la revisión, con el método "esperaba X, pasó Y, cambio Z". Dueño: ML 1
- [ ] 2.2 Presupuesto de latencia por turno con mediciones reales en H2 (sin LLM, la extracción de intención es local y no aporta latencia de red). Dueño: ML 1

## 3. Implementación (H1 hecha; H2 y H3/H4 pendientes)

- [x] 3.1 H1: paquete Python sin HTTP con `amount-parsing`, `contact-resolution`, `intent-extraction` (solo reglas) y `reply-classification` — evidencia: `api/voice/RESULTADOS.md` §"Pruebas por capability" (553 pruebas del módulo; paquete sin LLM, sin red, sin disco, sin float)
- [x] 3.2 H1: pruebas contra estos specs y la batería de frases de desarrollo (solo texto) — evidencia: `api/voice/RESULTADOS.md` §"Cobertura de la gramática de intención" (28/30 coinciden; 23 y 26 dan `PAY UNCLEAR` por gramática estricta, sin pagar)
- [x] 3.2b Forma de `Intent`, `Resolution` y `Contact` para el `context` del motor (`to_dict()`, camelCase) — evidencia: `api/voice/RESULTADOS.md` (`test_context_shapes.py`, 19 pruebas)
- [ ] 3.3 H2: decodificación en memoria (WebM/Opus a PCM float32 16 kHz mono) y `speech-transcription` (filtro local previo, Groq `whisper-large-v3-turbo` y respaldo local `base`), integrados al esqueleto FastAPI. Dueño: ML 1
- [ ] 3.4 H2: `transcribe` recibe `consentExterno: bool` y entrega `transcriptConfidence` (`null` en H1/H2); `extract_intent` entrega `intentConfidence` (`null` mientras la intención salga solo de reglas); el orquestador pasa ambos al `context`. Dueño: ML 1
- [ ] 3.5 H3 y H4: pruebas con ruido (audios fuera del repo) y pulido de frases y de `say`; con esa batería se proponen los cortes de confianza ([DECIDIDO, 2026-10-16]: si el sábado 17 antes de las 10:00 no hay evidencia, se ratifica `null` y se anota en `docs/decisiones.md`, P-10). Dueño: ML 1

- [ ] 3.6 Desafío de confirmación por voz (decidido el 17 oct): banco de 30 frases, `phrase_match` con corte 0,80, `CONFIRM_CHALLENGE` y `CHALLENGE_RETRY` en `say` (capability `confirmation-challenge`). Dueño: ML 1

## 4. Cierre

- [ ] 4.1 Archivar con `openspec archive add-voice-understanding` después de 1.2, 1.3 y 1.4. Dueño: Sebastián
