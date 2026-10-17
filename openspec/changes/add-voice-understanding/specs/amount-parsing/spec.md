# Spec Delta — amount-parsing

## Purpose

Convertir montos hablados o escritos en es-CO a `Amount`, y formatear montos para pantalla y voz, sin
usar nunca `number` o `float`. Origen: Spec general §6 (CONV-1) y Contratos § Tipos compartidos;
la revisión del rol Voz del 13 de octubre (espacio de trabajo previo) (V-01, V-15, V-16, V-17, V-26);
B-6 ratificado en `docs/contratos-cambios-propuestos-v1.1.md`. Los ejemplos usan `COP` con
`assetScale: 2`, que viene de configuración (no está fijo en el parser). Que la wallet emisora de la
Test Wallet opere en COP con escala 2 sigue **[VERIFICAR]** (E1): dueño equipo (Pagos entrega la
configuración de la wallet), experimento: una quote real en la Test Wallet (`docs/contratos-http-v1.md`
§ Pendientes); la receptora ya está confirmada.

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

#### Scenario: Millón y medio
- **WHEN** el parser convierte "un millón y medio"
- **THEN** el resultado es `{ value: "150000000" }` con escala 2

#### Scenario: Dígitos y palabras mezclados
- **WHEN** el parser convierte "20 mil 500"
- **THEN** el resultado es `{ value: "2050000" }` con escala 2

### Requirement: Ruido aceptado alrededor del monto
El parser SHALL ignorar como ruido los signos y palabras que no cambian el monto: "$", "peso", "pesos", "COP" y "de" (decisión de Sebastián, 2026-10-16, `api/voice/amounts.py`). El parser SHALL aceptar como entrada máximo 200 caracteres y producir como resultado máximo 1.000.000.000 pesos; lo que pase esos topes MUST resultar en `INVALID_AMOUNT`. El `value` resultante MUST NOT tener ceros a la izquierda.

#### Scenario: Signo de moneda
- **WHEN** el parser convierte "$20.000"
- **THEN** el resultado es `{ value: "2000000" }` con escala 2

#### Scenario: Entrada demasiado larga
- **WHEN** el parser recibe más de 200 caracteres
- **THEN** responde `INVALID_AMOUNT`

#### Scenario: Monto sobre el tope
- **WHEN** el parser convierte "2.000.000.000"
- **THEN** responde `INVALID_AMOUNT`
- **AND** no devuelve ningún monto

### Requirement: Jerga solo con valor validado
Las palabras de jerga ("luca", "barra", etc.) SHALL convertirse solo si están en la tabla de jerga validada por hablantes colombianos **[VERIFICAR]** (dueño: ML 1; experimento X-5 con hablantes colombianos, conjunto `frases-desarrollo.md` §A). Sin tabla validada, toda jerga conocida MUST resultar en `AMBIGUOUS_AMOUNT`, y cualquier palabra fuera de esa tabla MUST resultar en `AMBIGUOUS_AMOUNT`.

#### Scenario: Jerga sin validar
- **WHEN** el parser convierte "20 lucas" sin tabla validada
- **THEN** responde `AMBIGUOUS_AMOUNT`
- **AND** el sistema pregunta el monto otra vez

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

### Requirement: La confirmación hablada nombra monto y destinatario, nunca el costo
Antes de cada pago, el `say` de confirmación SHALL incluir el monto que recibe el destinatario (`receiveAmount`) y el nombre del contacto (SEG-2), y MUST NOT mencionar el costo ni el monto debitado (B-6, ratificado; `payments-client`, "El monto que se dice antes del sí"). El costo (`debitAmount − receiveAmount`, con aritmética entera) se dice solo después de `COMPLETED` (`payments-client`, "Monto que se dice en el recibo del pago").

#### Scenario: Confirmación de 20.000 a Laura
- **WHEN** hay una quote con `receiveAmount` de 20.000 para el contacto Laura
- **THEN** el `say` contiene "20.000" y "Laura"
- **AND** el `say` no menciona el débito ni el costo
- **AND** el estado es `AWAITING_CONFIRMATION`

#### Scenario: El costo se dice en el recibo
- **WHEN** un pago `COMPLETED` tiene `debitAmount` de 2015000 y `receiveAmount` de 2000000 (COP, escala 2)
- **THEN** el `say` del recibo menciona el costo "150" calculado como débito − recibido con enteros

### Requirement: La moneda, la escala y su palabra vienen de configuración
El parser SHALL recibir `assetCode` y `assetScale` como parámetros, nunca fijos en el código. Para el MVP, el valor es una constante de configuración. La palabra de la moneda que se dice en voz ("pesos") también SHALL salir de la configuración, no de la plantilla (`api/voice/config.py`, `CURRENCY_WORDS`).

#### Scenario: Escala distinta
- **WHEN** se convierte "20.000" con `assetScale: 0`
- **THEN** el resultado es `{ value: "20000", assetScale: 0 }`

#### Scenario: Palabra de la moneda
- **WHEN** se arma un `say` con un `Amount` en COP
- **THEN** la palabra dicha después del monto sale de la configuración ("pesos")
