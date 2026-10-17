# Spec Delta — contact-resolution

## Purpose

Resolver el destinatario dicho por la usuaria a un contacto de su agenda, sin adivinar. Origen: Spec
general §4 (SEG-4, SEG-6) y la revisión del rol Voz del 13 de octubre (espacio de trabajo previo)
(V-05, V-06, V-18). Ratificado el 16 de octubre: la elección vuelve como `text` con el `alias` (B-4) y
"destinatario nuevo" es el que no tiene un pago `COMPLETED` previo, con Laura sembrada como conocida
(decisión #4, `docs/decisiones.md`). La agenda del MVP tiene un solo usuario (Contratos § Decisiones,
"Usuarios").

## ADDED Requirements

### Requirement: El destinatario sale solo de la agenda
La wallet address de un pago SHALL salir únicamente de la agenda del usuario. Ningún texto hablado, ni lo que devuelva un LLM, MUST aportar una wallet address. Un texto que parece una wallet, un payment pointer, una URL o un correo MUST NOT buscarse en la agenda.

#### Scenario: Wallet dicha en voz
- **WHEN** el usuario dice una dirección de wallet en lugar de un nombre
- **THEN** el sistema no la usa
- **AND** responde `AWAITING_COMMAND` pidiendo un contacto de la agenda

### Requirement: Coincidencia exacta normalizada
El sistema SHALL comparar el destinatario dicho con los alias y nombres de la agenda ignorando mayúsculas y tildes. Una coincidencia única MUST resolver al contacto.

#### Scenario: Alias de parentesco
- **WHEN** la agenda tiene el contacto "Laura" con alias "mi hija" y el usuario dice "Mi Hija"
- **THEN** se resuelve al contacto Laura

#### Scenario: Diferencia de tildes
- **WHEN** el contacto se llama "José" y el usuario dice "jose"
- **THEN** se resuelve al contacto José

### Requirement: Coincidencia ambigua obliga a preguntar
Si el destinatario coincide con más de un contacto, el sistema MUST responder `AWAITING_RECIPIENT_CHOICE` con una opción por contacto (`alias` y `name`, sin wallet address) y MUST NOT elegir uno. De haber más de tres coincidencias, el sistema SHALL ofrecer como máximo tres: en el orden de la agenda para las coincidencias exactas y parciales, y por distancia de edición y luego por nombre para las aproximadas (`api/voice/contacts.py`).

#### Scenario: Dos Lauras
- **WHEN** la agenda tiene "Laura hija" y "Laura vecina" y el usuario dice "envíale a Laura"
- **THEN** el estado es `AWAITING_RECIPIENT_CHOICE`
- **AND** `options` tiene las dos opciones
- **AND** ninguna `option` contiene una wallet address

### Requirement: Sin coincidencia no hay pago
Si el destinatario no coincide con ningún contacto ni se parece a uno, el sistema MUST NOT pagar y MUST responder `AWAITING_COMMAND` explicando que no encontró al contacto.

#### Scenario: Destinatario desconocido
- **WHEN** el usuario dice "envíale veinte mil a Pedro" y no hay ningún contacto parecido
- **THEN** el estado es `AWAITING_COMMAND`
- **AND** no se hace ninguna cotización

### Requirement: Una coincidencia aproximada única se confirma, no se asume
Si el destinatario no coincide exactamente pero se parece a un único contacto (por ejemplo, un error de transcripción), el sistema SHALL responder `AWAITING_RECIPIENT_CHOICE` con esa única opción y MUST NOT usar el contacto hasta que el usuario lo confirme.

#### Scenario: Error de transcripción
- **WHEN** Whisper entrega "Lara" y la agenda solo tiene "Laura"
- **THEN** el estado es `AWAITING_RECIPIENT_CHOICE` con la opción Laura
- **AND** no se cotiza hasta que el usuario elija

### Requirement: La elección solo vale entre las opciones ofrecidas
La elección del usuario SHALL volver en el siguiente turno como `text` con el `alias` de la opción (B-4, ratificado), o por voz; en ambos casos MUST resolverse únicamente contra las `options` que la sesión ofreció. Cualquier otra respuesta MUST resultar en `UNCLEAR` y MUST NOT elegir ningún contacto; el orquestador vuelve a ofrecer las opciones.

#### Scenario: Elección por alias
- **WHEN** la sesión ofreció "Laura hija" y "Laura vecina" y llega `text` igual al alias "laura-hija"
- **THEN** se resuelve al contacto Laura hija

#### Scenario: Afirmación con una sola opción
- **WHEN** la sesión ofreció una única opción (aproximada) y la respuesta de voz es un "sí" claro
- **THEN** se resuelve al contacto de esa única opción
- **AND** el pago sigue esperando su confirmación normal (no se paga con este "sí")

#### Scenario: Elección fuera de las opciones
- **WHEN** la sesión ofreció dos opciones y el usuario dice el nombre de un tercer contacto
- **THEN** el resultado es `UNCLEAR`
- **AND** se vuelven a ofrecer las dos opciones

### Requirement: Destinatario conocido
Cada contacto SHALL tener un indicador `previouslyPaid`, verdadero solo si hay al menos un pago `COMPLETED` a ese contacto. Los contactos sembrados para la demo pueden iniciar en verdadero (decisión #4 del 16 oct). Un pago `FAILED` o en curso MUST NOT cambiarlo. Quien actualiza el indicador es el orquestador con el historial de pagos (`turn-orchestration`, "Historial de pagos por destinatario"); este capability solo lo lee. El motor de ML 2 usa el indicador para SEG-6.

#### Scenario: Primer pago completado
- **WHEN** un contacto con `previouslyPaid` en falso recibe un pago `COMPLETED`
- **THEN** `previouslyPaid` pasa a verdadero

#### Scenario: Pago fallido
- **WHEN** un pago a un contacto con `previouslyPaid` en falso termina `FAILED`
- **THEN** `previouslyPaid` sigue en falso

### Requirement: La agenda no contiene secretos
La agenda SHALL cargarse desde un archivo de configuración con alias, nombre y wallet address públicas. MUST NOT contener llaves, tokens ni datos personales no necesarios.

#### Scenario: Revisión de la agenda
- **WHEN** se revisa el archivo de la agenda
- **THEN** solo contiene alias, nombre, wallet address y `previouslyPaid`
