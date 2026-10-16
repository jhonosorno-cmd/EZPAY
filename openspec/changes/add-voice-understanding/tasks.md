## 1. Aprobación del equipo

- [ ] 1.1 El equipo revisa la revisión del rol Voz del 13 de octubre (espacio de trabajo previo) y decide D3 a D8 (D1 y D2 son de ML 1)
- [ ] 1.2 Si se aprueba D6, se cambian los Contratos HTTP v1 (con el OK de los cuatro) antes de archivar este cambio
- [ ] 1.3 Si se aprueba D4 y C-1, se actualiza SEG-3 en el Spec general y se alinea `payment-safety`
- [ ] 1.4 Se validan los specs con `openspec validate add-voice-understanding --strict`

## 2. Experimentos descartables previos al evento (sin código en el repo)

- [ ] 2.1 X-1 a X-5 de la revisión, con el método "esperaba X, pasó Y, cambio Z"
- [ ] 2.2 Se fija el presupuesto de latencia por turno con las mediciones de X-1

## 3. Implementación (solo desde el viernes 16 oct)

- [ ] 3.1 H1: paquete Python sin HTTP con `amount-parsing`, `contact-resolution`, `intent-extraction` y `reply-classification`
- [ ] 3.2 H1: pruebas contra estos specs y conjunto de desarrollo de frases (solo texto)
- [ ] 3.3 H2: decodificación en memoria y `speech-transcription`, integrados al esqueleto FastAPI
- [ ] 3.4 H3 y H4: pruebas con ruido (audios fuera del repo) y pulido de frases

## 4. Cierre

- [ ] 4.1 Se archiva el cambio con `openspec archive add-voice-understanding`
