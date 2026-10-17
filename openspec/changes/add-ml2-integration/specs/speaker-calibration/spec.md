# Spec Delta — speaker-calibration

## Purpose

Protocolo de recalibración en la sala de demostración (tarea 4.6) con el micrófono de la demo, y
las reglas para decidir con evidencia si se mueven los cuatro parámetros del sistema de voz:
`threshold` (0.45), el corte de consistencia del enrolamiento (0.45), `minVerifySeconds` (2.0 s) y
`challengePhraseMatchMin` (0.80). El código se congela a las 10:45: sin evidencia suficiente, los
valores actuales se quedan y el resultado se registra en `docs/decisiones.md`. Solo números
agregados salen de la sala: nunca audio ni embeddings en el repo.


## ADDED Requirements

### Requirement: Protocolo en la sala

La sesión de calibración SHALL correr el sábado antes del congelamiento con el micrófono de la
demo (solapa, o el que se use ese día) y el ruido real de la sala. SHALL enrolar a las **4 personas**
**del equipo** y SHALL grabar, por cada una, al menos **6 intentos genuinos y 6 de impostor**, con
las **10 frases del banco** del desafío y los comandos de la demo **[DECIDIDO 2026-10-17, Daniel]**
(vamos justos de tiempo). Los scripts y audios viven FUERA del repo, en `Pruebas ML2`.

#### Scenario: Sesión de calibración

- **GIVEN** la sala de demo con su micrófono y su ruido de fondo
- **WHEN** se corre el protocolo [**DECIDIDO 2026-10-17, Daniel**: 4 personas del equipo, 6 genuinos + 6 impostor por persona, 10 frases del banco y comandos de la demo**]**
- **THEN** quedan medidos los números del requisito "Métricas" con ese micrófono y ese ruido
- **AND** nada de audio ni embeddings sale de `Pruebas ML2` hacia el repo

### Requirement: Métricas que se miden

La corrida SHALL producir estos números agregados con el micrófono de la sala: falsos aceptados y
falsos rechazados al umbral actual (0.45), mínimo genuino, máximo impostor, peor par de
consistencia del enrolamiento, y la distribución de `phrase_match` de las frases del banco dichas
en la sala (para `challengePhraseMatchMin`). Esta última se coordina con la batería con ruido de
Sebastián (Voz) para no medir dos veces. Nada de datos por persona en el registro final.

#### Scenario: Tabla de métricas de la sala

- **GIVEN** los intentos genuinos y de impostor grabados en la sala
- **WHEN** se corren los scripts de `Pruebas ML2`
- **THEN** se obtienen FA/FR a 0.45, mínimo genuino, máximo impostor, peor par de consistencia y los puntajes de `phrase_match` en la sala
- **AND** los números se anotan agregados, sin audio ni embeddings, listos para `docs/decisiones.md`

### Requirement: Regla de decisión para mover

Cada parámetro SHALL moverse solo con evidencia clara **[DECIDIDO 2026-10-17, Daniel]**:
`threshold` 0.45, si el orden se invierte (impostor ≥ genuino) o FR > 10 % con 0 FA;
corte de consistencia 0.45, si un enrolamiento real da peor par bajo el corte;
`minVerifySeconds` 2,0 s, si frases normales de la sala caen en `NOT_AVAILABLE` (> 10 %);
`challengePhraseMatchMin` 0.80, si frases bien dichas quedan bajo el corte (> 10 %) o mal dichas
lo pasan. Mover uno recalibra los que dependen de él.

#### Scenario: Evidencia para mover el umbral

- **GIVEN** las métricas de la sala con el micrófono de la demo
- **WHEN** se evalúa la regla del umbral [**DECIDIDO 2026-10-17, Daniel**]
- **THEN** solo se mueve si la evidencia lo exige (inversión del margen o FR > 10 % con 0 FA) y el nuevo valor queda registrado con sus números
- **AND** cambiar `trim_silence` o la medida de duración sigue exigiendo recalibrar todo (H2)

### Requirement: Sin tiempo: valores actuales

Si la sesión de la sala no alcanza (congelamiento 10:45), los cuatro parámetros SHALL quedarse
como están (0.45 / 0.45 / 2,0 s / 0.80) y el resultado SHALL registrarse en `docs/decisiones.md`:
números medidos, decisión de no mover y pendiente para H4. La demo no depende de recalibrar: el
sistema ya funciona con los valores de H2 [DECIDIDO en la práctica: la opción `confirmationChallenge`
está apagada por defecto y sin recalibración nada se rompe].

#### Scenario: La sesión no alcanza

- **GIVEN** las 09:30 de la sala y evidencia parcial a las 10:30
- **WHEN** no hay números suficientes para mover un parámetro
- **THEN** se conserva el valor actual y se anota en `docs/decisiones.md` con lo medido
- **AND** la demo corre con los valores de H2 y el desafío como siguiente paso

### Requirement: Congelamiento en H4 y registro

Los valores que salgan de la sala SHALL congelarse para H4 (ya no se recalibran): la sesión del
sábado es la última del hackathon. El registro en `docs/decisiones.md` SHALL contener solo números
agregados (FA/FR, mínimos, máximos, peor par, puntajes de frase), nunca audio, embeddings,
transcripciones ni voces reales (repo público, AGENTS.md). Los scripts de medición y los audios
viven fuera del repo, en `Pruebas ML2` (carpeta ya existente para los pesos).

#### Scenario: Registro de la calibración

- **GIVEN** la sesión de la sala terminada (o abortada por tiempo)
- **WHEN** se registra el resultado
- **THEN** `docs/decisiones.md` queda con los números agregados y la decisión por parámetro
- **AND** ni `git status` ni el repo contienen audio, embeddings ni voces reales

### Requirement: Riesgo de la demo y plan B

Un enrolamiento que falle en vivo es el riesgo principal de la demo: la sala es ruidosa y
`INCONSISTENT_SAMPLES` puede rechazar a la persona que presenta. El plan SHALL prever [DECIDIDO 2026-10-17, Daniel]:
enrolar ANTES de la demo (con el micrófono de la sala) y, si en vivo algo falla, plan B en orden —
reintentar el enrolamiento una vez; si sigue fallando, correr la demo en modo texto/PIN
(`confirmationChallenge` apagada y comandos por `text`), que no depende de la voz y ya funciona.

#### Scenario: Enrolamiento que falla en vivo

- **GIVEN** la demo en curso y un enrolamiento que responde `INCONSISTENT_SAMPLES` en la sala
- **WHEN** el plan B se aplica
- **THEN** se reintenta una vez y, si vuelve a fallar, la demo sigue en modo texto/PIN (voz desactivada) sin bloquear la presentación
- **AND** el fallo no detiene el pago por texto: la demo no depende del enrolamiento en vivo
