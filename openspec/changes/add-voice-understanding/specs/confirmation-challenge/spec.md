# Spec Delta — confirmation-challenge

## Purpose

Dar al orquestador lo que necesita para confirmar por voz con desafío: un banco de frases, una función que decide si la
respuesta coincide con la frase pedida y los textos que la piden. Origen: `verificacion-ml2/confirmacion-con-desafio.md`
y `docs/decisiones.md` (2026-10-17), [DECIDIDO] por los cuatro. La frase la elige el backend al azar, nunca el LLM, y la
voz de la respuesta la verifica ML 2.

## ADDED Requirements

### Requirement: Banco de frases del desafío
El banco SHALL tener al menos 30 frases de 6 a 9 palabras, sin números ni nombres propios, que no contengan afirmaciones, negaciones, verbos de pago ni palabras de monto, y distintas de las frases del registro de voz. Se carga de un archivo de datos sin cambiar código.

#### Scenario: Frase válida
- **WHEN** se carga el banco
- **THEN** cada frase tiene de 6 a 9 palabras
- **AND** ninguna palabra es una afirmación, negación, verbo de pago o palabra de monto

#### Scenario: Banco insuficiente
- **WHEN** el archivo tiene menos de 30 frases o una frase inválida
- **THEN** la carga lanza un error y no se pide ningún desafío

### Requirement: Elección de la frase sin repetir
La elección SHALL ser al azar entre las frases del banco que no se usaron todavía en la sesión; si ya se usaron todas, entre todas menos la última.

#### Scenario: Reintento con otra frase
- **WHEN** falla el primer desafío y se pide otro en la misma sesión
- **THEN** la nueva frase es distinta de la anterior

### Requirement: Coincidencia de la frase
`phrase_match` SHALL devolver `1 − errores/palabras` entre 0 y 1 (distancia de edición por palabra, sin tildes, mayúsculas ni signos), y el desafío MUST considerarse cumplido solo con al menos 0,80. Una transcripción vacía MUST dar 0.

#### Scenario: Frase dicha completa
- **WHEN** la transcripción es "Mi casa tiene una puerta verde y grande." y la frase es la misma
- **THEN** el puntaje es 1 y el desafío se cumple

#### Scenario: Un error de transcripción
- **WHEN** una palabra de 8 está mal
- **THEN** el puntaje es 0,875 y el desafío se cumple

#### Scenario: Dos errores
- **WHEN** dos palabras de 8 están mal
- **THEN** el puntaje es 0,75 y el desafío no se cumple

#### Scenario: Silencio
- **WHEN** la transcripción está vacía
- **THEN** el puntaje es 0 y el desafío no se cumple

### Requirement: Textos del desafío
`say` SHALL tener `CONFIRM_CHALLENGE` (monto, destinatario y frase) y `CHALLENGE_RETRY` (frase), con los mismos requisitos de parámetros que el resto del catálogo.

#### Scenario: Pedir el desafío
- **WHEN** se llama `say(CONFIRM_CHALLENGE, amount=20.000, name="Laura", phrase=…)`
- **THEN** el texto dice el monto y el destinatario y pide repetir la frase

#### Scenario: Frase faltante
- **WHEN** falta el parámetro `phrase`
- **THEN** `say` lanza `ValueError`
