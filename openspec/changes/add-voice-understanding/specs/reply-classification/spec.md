# Spec Delta — reply-classification

## Purpose

Clasificar la respuesta del usuario a una pregunta del sistema como `YES`, `NO` o `UNCLEAR`, de forma
determinística, para que nada se ejecute sin un "sí" claro. Origen: Spec general §4 (SEG-2, SEG-3) y
la revisión del rol Voz del 13 de octubre (espacio de trabajo previo) (V-04, V-13, V-14, V-24). Depende de la decisión D5
propuesta al equipo; la lista cerrada de afirmativos la fija el equipo.

## ADDED Requirements

### Requirement: Clasificación determinística de la respuesta
La respuesta SHALL clasificarse como `YES`, `NO` o `UNCLEAR` mediante reglas determinísticas sobre la transcripción, sin invocar al LLM. `YES` MUST exigir una afirmación de la lista cerrada y ninguna otra señal en la respuesta.

#### Scenario: Afirmación clara
- **WHEN** el usuario responde "sí" a "¿Le envío 20.000 a Laura?"
- **THEN** la clasificación es `YES`

#### Scenario: Negación clara
- **WHEN** el usuario responde "no"
- **THEN** la clasificación es `NO`
- **AND** no se ejecuta el pago

#### Scenario: Sin llamada al LLM
- **WHEN** se clasifica cualquier respuesta
- **THEN** no se hace ninguna llamada al LLM

### Requirement: Todo lo que no sea un sí claro es no
Una respuesta vacía, dudosa, con ruido o que mezcle afirmación y negación MUST clasificarse `UNCLEAR`, y el sistema MUST NOT ejecutar el pago.

#### Scenario: Respuesta dudosa
- **WHEN** el usuario responde "eh… ¿cuánto?"
- **THEN** la clasificación es `UNCLEAR`
- **AND** no se ejecuta el pago

#### Scenario: Afirmación y negación
- **WHEN** el usuario responde "sí, no"
- **THEN** la clasificación es `UNCLEAR`

#### Scenario: Respuesta vacía
- **WHEN** la transcripción es vacía
- **THEN** la clasificación es `UNCLEAR`

### Requirement: Una respuesta con un monto o destinatario nuevo no confirma
Si la respuesta contiene un monto o un destinatario, MUST clasificarse `UNCLEAR`, aunque contenga un "sí". El sistema MUST NOT ejecutar ni modificar el pago pendiente, y SHALL atender el texto como un comando nuevo.

#### Scenario: Cambio de monto en la confirmación
- **WHEN** el usuario responde "sí, mejor 50 mil" a una confirmación de 20.000
- **THEN** la clasificación es `UNCLEAR`
- **AND** el pago de 20.000 no se ejecuta

#### Scenario: Eco de la pregunta del sistema
- **WHEN** la transcripción es "¿Le envío 20.000 a Laura?", por el eco del TTS en el micrófono
- **THEN** la clasificación es `UNCLEAR`
- **AND** no se ejecuta el pago

### Requirement: El PIN nunca se procesa como lenguaje
En el estado `AWAITING_PIN`, el `text` recibido SHALL entregarse solo a la validación del PIN. MUST NOT llegar al LLM, al parser de montos, al clasificador de respuestas ni a los logs.

#### Scenario: PIN con dígitos que parecen un monto
- **WHEN** el estado es `AWAITING_PIN` y llega `text` "1234"
- **THEN** no se intenta convertir en monto ni se clasifica
- **AND** el PIN no aparece en ningún log

### Requirement: La respuesta se evalúa solo contra el pago pendiente
La clasificación `YES` SHALL valer únicamente para la quote que el sistema acaba de confirmar en voz alta. MUST NOT reutilizarse para otra quote, ni después de que el estado cambie.

#### Scenario: Sí tardío
- **WHEN** el usuario dice "sí" cuando el estado ya no es `AWAITING_CONFIRMATION`
- **THEN** la respuesta no confirma ningún pago
