# Spec Delta — amount-parsing

## Purpose

Convertir montos hablados o escritos en es-CO a `Amount`, y formatear montos para pantalla y voz, sin
usar nunca `number` o `float`. Origen: Spec general §6 (CONV-1) y Contratos § Tipos compartidos;
la revisión del rol Voz del 13 de octubre (espacio de trabajo previo) (V-01, V-15, V-16, V-17, V-26). Depende de la decisión D3
propuesta al equipo; los ejemplos usan `COP` con `assetScale: 2`, que viene de configuración (no está
fijo en el parser) y está pendiente de confirmar en la wallet emisora **[VERIFICAR]** (E1).

## ADDED Requirements

### Requirement: Formato es-CO de montos escritos
El parser SHALL interpretar el punto como separador de miles solo si le siguen exactamente tres dígitos, y la coma como separador decimal. Cualquier otro uso del punto MUST resultar en `AMBIGUOUS_AMOUNT` y el sistema MUST repreguntar, sin adivinar.

#### Scenario: Punto de miles
- **WHEN** el parser convierte "20.000" con `assetScale: 2`
- **THEN** el resultado es `{ value: "2000000", assetCode: "COP", assetScale: 2 }`

#### Scenario: Coma decimal
- **WHEN** el parser convierte "10,50" con `assetScale: 2`
- **THEN** el resultado es `{ value: "1050", assetCode: "COP", assetScale: 2 }`

#### Scenario: Punto ambiguo
- **WHEN** el parser convierte "10.50"
- **THEN** responde `AMBIGUOUS_AMOUNT`
- **AND** el sistema pregunta el monto otra vez

#### Scenario: Miles con decimales
- **WHEN** el parser convierte "1.500,50" con `assetScale: 2`
- **THEN** el resultado es `{ value: "150050", assetCode: "COP", assetScale: 2 }`

### Requirement: Montos dichos con palabras
El parser SHALL convertir montos en palabras en español a su valor entero en pesos, de forma determinística.

#### Scenario: Con "mil"
- **WHEN** el parser convierte "veinte mil"
- **THEN** el resultado es `{ value: "2000000" }` con escala 2

#### Scenario: Con "mil" y centenas
- **WHEN** el parser convierte "veinte mil quinientos"
- **THEN** el resultado es `{ value: "2050000" }` con escala 2

#### Scenario: Con "millón"
- **WHEN** el parser convierte "medio millón"
- **THEN** el resultado es `{ value: "50000000" }` con escala 2

### Requirement: Jerga solo con valor validado
Las palabras de jerga ("luca", "barra", etc.) SHALL convertirse solo si están en la tabla de jerga validada por hablantes colombianos **[VERIFICAR]**. Cualquier palabra fuera de esa tabla MUST resultar en `AMBIGUOUS_AMOUNT`.

#### Scenario: Jerga fuera de la tabla
- **WHEN** el parser recibe una palabra de jerga que no está en la tabla
- **THEN** responde `AMBIGUOUS_AMOUNT`
- **AND** el sistema pregunta el monto otra vez

### Requirement: Decimales que sobran nunca se redondean
Si el monto tiene más decimales que `assetScale`, el parser MUST responder `TOO_MANY_DECIMALS` y MUST NOT redondear ni truncar. Un dígito sobrante igual a cero no cuenta como decimal que sobra.

#### Scenario: Más decimales que la escala
- **WHEN** el parser convierte "10,505" con `assetScale: 2`
- **THEN** responde `TOO_MANY_DECIMALS`
- **AND** no devuelve ningún monto

#### Scenario: Caso que un float redondearía
- **WHEN** el parser convierte "1,005" con `assetScale: 2`
- **THEN** responde `TOO_MANY_DECIMALS`

#### Scenario: Cero sobrante
- **WHEN** el parser convierte "10,500" con `assetScale: 2`
- **THEN** el resultado es `{ value: "1050" }`

#### Scenario: Escala cero
- **WHEN** el parser convierte "10,50" con `assetScale: 0`
- **THEN** responde `TOO_MANY_DECIMALS`

### Requirement: Montos no válidos como pago
El parser MUST rechazar con `INVALID_AMOUNT` un monto negativo, vacío, no numérico o igual a cero. `INVALID_AMOUNT` y `TOO_MANY_DECIMALS` son errores internos de conversión, no respuestas HTTP: el turno responde `AWAITING_COMMAND` con un `say` que explica el problema.

#### Scenario: Monto cero
- **WHEN** el parser convierte "cero pesos"
- **THEN** responde `INVALID_AMOUNT`

#### Scenario: Monto negativo
- **WHEN** el parser convierte "-3"
- **THEN** responde `INVALID_AMOUNT`

#### Scenario: Error de monto en un turno
- **WHEN** el usuario dice un monto con `TOO_MANY_DECIMALS`
- **THEN** `/turns` responde `TurnResponse` en `AWAITING_COMMAND`
- **AND** no responde un error HTTP

### Requirement: Ningún monto pasa por número de punto flotante
La conversión, la comparación y el formato de montos SHALL operar sobre el string `value` o sobre enteros exactos, nunca sobre `number` ni `float`.

#### Scenario: Suma que un float falla
- **WHEN** se convierten "0,10", "0,20" y "19,99" y se suman sus `value`
- **THEN** la suma es exactamente "2029"

### Requirement: Formato de montos para pantalla y voz
El sistema SHALL formatear un `Amount` para pantalla y voz usando el punto como separador de miles y la coma como decimal, a partir del string `value` y `assetScale`, sin conversión a número.

#### Scenario: Monto entero
- **WHEN** se formatea `{ value: "2000000", assetCode: "COP", assetScale: 2 }`
- **THEN** el texto es "20.000"

#### Scenario: Monto con centavos
- **WHEN** se formatea `{ value: "1050", assetCode: "COP", assetScale: 2 }`
- **THEN** el texto es "10,50"

#### Scenario: Ida y vuelta
- **WHEN** se formatea un monto y se vuelve a convertir con el parser
- **THEN** el `value` obtenido es el original

### Requirement: La confirmación hablada nombra monto y destinatario
Antes de cada pago, el `say` de confirmación SHALL incluir el monto que recibe el destinatario y el nombre del contacto (SEG-2). Si además dice el monto que se debita, la decisión sobre cuál cifra mostrar la toma el equipo **[PARA DECIDIR]**, ver revisión V-16.

#### Scenario: Confirmación de 20.000 a Laura
- **WHEN** hay una quote con `receiveAmount` de 20.000 para el contacto Laura
- **THEN** el `say` contiene "20.000" y "Laura"
- **AND** el estado es `AWAITING_CONFIRMATION`

### Requirement: La moneda y la escala vienen de configuración
El parser SHALL recibir `assetCode` y `assetScale` como parámetros, nunca fijos en el código. Para el MVP, el valor es una constante de configuración.

#### Scenario: Escala distinta
- **WHEN** se convierte "20.000" con `assetScale: 0`
- **THEN** el resultado es `{ value: "20000", assetScale: 0 }`
