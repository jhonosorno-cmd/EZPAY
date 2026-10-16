## 1. Aprobación del equipo

- [x] 1.1 El equipo decide los cambios de contrato que este spec adopta (Pagos D-1 y D-2, ML 1 C-6, ML 2 C-3) y la contradicción F-1
- [ ] 1.2 ML 2 entrega el texto del consentimiento y las tres frases del enrolamiento
- [ ] 1.3 Se validan los specs con `openspec validate add-voice-web-client --strict`

## 2. Antes de escribir código (viernes 16 oct, temprano)

- [ ] 2.1 Grabar con `MediaRecorder` una muestra real del navegador y dársela a ML 1 fuera del repo (X-4)
- [ ] 2.2 En la laptop de la demo: voces `es-*` disponibles, lectura de "20.000" y micrófono de solapa
- [x] 2.3 Acordar con Pagos el mock del Contrato B; si no está a las 10:30, mock propio con una respuesta fija por estado

## 3. Implementación

- [x] 3.1 H1 (vie 14:00): pantalla de conversación con texto, teclado de PIN, botón de presupuesto, ida a la wallet y `/grant-callback`
- [ ] 3.2 H2 (vie 17:30): grabación push-to-talk, TTS con desbloqueo, recibo, elección de destinatario y `PAYMENT_PENDING`
- [ ] 3.3 H3 (sáb 09:30): registro de voz con consentimiento
- [ ] 3.4 H4 (sáb 10:30): pulido de la demo y ensayo del momento clave

## 4. Cierre

- [ ] 4.1 Se archiva el cambio con `openspec archive add-voice-web-client`
