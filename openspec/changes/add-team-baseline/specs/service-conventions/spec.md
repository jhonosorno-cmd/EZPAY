# Spec Delta — service-conventions

## Purpose

Convenciones comunes al frontend, al backend Python y al microservicio Node. Origen: Spec general
§6 (CONV-1 a CONV-6). Las interfaces concretas están en `docs/contratos-http-v1.md`, anexo del Spec general; un spec nunca las contradice.

## ADDED Requirements

### Requirement: Montos sin punto flotante (CONV-1)
Todo monto SHALL representarse como `{ value: string, assetCode, assetScale }` con `value` de solo dígitos. Ningún servicio MUST pasar un monto por `number` o `float`, tampoco al mostrarlo en el frontend. Convertir el texto hablado a monto es tarea de Python, que rechaza los decimales que sobran y nunca redondea.

#### Scenario: Monto con más decimales que la escala
- **WHEN** Python convierte "10.505" con `assetScale: 2`
- **THEN** rechaza el monto con `TOO_MANY_DECIMALS`
- **AND** no lo redondea

#### Scenario: Monto mostrado en pantalla
- **WHEN** el frontend muestra `{ value: "2000000", assetCode: "COP", assetScale: 2 }`
- **THEN** el texto mostrado sale de operar sobre el string, sin convertirlo a `number`

### Requirement: Formato uniforme de errores (CONV-2)
Todos los servicios SHALL responder los errores como `{ error: { code, message } }`, y todo cliente MUST decidir por `code`, nunca por el texto de `message`.

#### Scenario: Error entre servicios
- **WHEN** un servicio recibe un error de otro
- **THEN** su decisión depende solo de `error.code`

### Requirement: Trazabilidad por solicitud (CONV-3)
El frontend SHALL generar un `X-Request-Id` por acción del usuario; Python y Node MUST propagarlo y escribirlo en cada línea de log, en formato JSON.

#### Scenario: Seguir un pago de punta a punta
- **WHEN** el usuario confirma un pago
- **THEN** los logs del frontend, de Python y de Node de esa acción tienen el mismo `X-Request-Id`

### Requirement: Secretos fuera del repositorio (CONV-4)
Los secretos SHALL vivir solo en `.env`, que nunca se versiona; se versiona `.env.example`. Las llaves y los tokens MUST NOT aparecer en el chat, en los prompts ni en los logs.

#### Scenario: Revisión antes de un push
- **WHEN** se prepara un push
- **THEN** no hay `.env`, llaves ni tokens entre los archivos versionados

### Requirement: Puertos locales fijos (CONV-5)
En desarrollo local, el frontend SHALL escuchar en el puerto 5173, Python en el 8000 y Node en el 4000.

#### Scenario: Levantar los tres servicios
- **WHEN** se levantan los tres servicios en una máquina
- **THEN** cada uno responde en su puerto sin configuración adicional

### Requirement: Idioma del código y de la interfaz (CONV-6)
El código, los identificadores y los códigos de error SHALL escribirse en inglés; los textos de la interfaz y de la voz, en español.

#### Scenario: Nuevo código de error
- **WHEN** un servicio agrega un código de error
- **THEN** el código está en inglés y el mensaje que oye o lee el usuario está en español
