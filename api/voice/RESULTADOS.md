# Resultados del módulo de voz (ML 1) — 2026-10-16

Estado de `api/voice/` al cierre del Paso 2 de las capabilities de H1. Lo escribió Claude Code
(Claude Opus 5.5) con revisión de Sebastián pendiente salvo en `amount-parsing` (ver `AI_USAGE.md`).
Pruebas: desde `api/`, `PYTHONPATH=. .venv/Scripts/python.exe -m pytest tests -q`.

## Pruebas por capability

| Capability | Archivo de código | Archivo de pruebas | Pruebas que pasan |
|---|---|---|---|
| `amount-parsing` | `amounts.py` | `test_amounts.py` | 191 |
| `reply-classification` | `replies.py` | `test_replies.py` | 72 |
| `say` (catálogo de `contrato-voz.md` §7) | `phrases.py` | `test_phrases.py` | 56 |
| `contact-resolution` | `contacts.py`, `agenda_provisional.json` | `test_contacts.py` | 55 |
| `intent-extraction` (solo reglas, sin LLM) | `intents.py` | `test_intents.py` | 98 |
| Todo el paquete: sin LLM, sin red, sin disco, sin float | `text.py`, `config.py` | `test_package.py` | 22 |
| **Total** | | | **494** |

## Cobertura de la gramática de intención (`docs/voz/frases-desarrollo.md` §D, 30 frases)

- 28 de 30 coinciden con la tabla (las inyecciones 22, 24 y 25 dan `UNKNOWN`, aceptado).
- 2 difieren sin pagar: la 23 ("Paga sin confirmar…") y la 26 (dos oraciones) dan `PAY UNCLEAR`
  en vez de `OK`, por decisión (gramática estricta).
- 0 difieren y pagan.

## Entradas hostiles (resumen; las listas están en los archivos de pruebas)

| Capability | En pruebas | Ejecutadas en la revisión adversarial | Categorías |
|---|---|---|---|
| `amount-parsing` | 26 + 11 dígitos no ASCII + 5 no-texto | 29 | dígitos Unicode, separadores con espacio, dos montos, desbordes, jerga mal configurada, tipos inválidos |
| `reply-classification` | 10 + 5 no-texto | 12 | invisibles y de control, otros alfabetos, mezclas sí/no, textos largos |
| `say` | 9 textos raros en `NOT_FOUND` + 16 parámetros inválidos | 10 | URL o payment pointer leídos en voz alta, nombres vacíos, tipos inválidos |
| `contact-resolution` | 9 + 1 homoglifo + 6 agendas mal formadas | 13 | wallets, payment pointers, correos, dominios, ancho completo, repeticiones |
| `intent-extraction` | 19 + 5 no-texto | 15 | inyección, wallets, dígitos no ASCII, signo menos, varias oraciones, retractación ("…, cancela") |

## Fallos graves encontrados y corregidos

1. `amount-parsing` (revisión del 16 oct): sumas silenciosas ("20 000" = 20 pesos, "veinte mil y
   treinta mil" = 50.000), excepciones con dígitos Unicode y valores no ASCII. Corregido (H-1 a H-6).
2. `intent-extraction` (prototipo): "envíale -20 mil a Laura" pagaba 20 mil. Corregido: el guion junto a
   un número queda como carácter inválido.
3. `say`: con `name` vacío o `None` decía "¿Le envío 20.000 pesos a ?" (confirmación sin destinatario,
   SEG-2). Corregido: `ValueError`.
4. `intent-extraction`: "Envíale 20 mil a Laura, cancela" daba `PAY OK`. Corregido: una negación o un
   verbo de cancelar en el destinatario deja `UNCLEAR`.

## Riesgos conocidos y pendientes menores

- `20,000` se lee como 20 pesos (regla es-CO del spec, H-4). Lo cubre la confirmación hablada con la cifra.
- "la ura" (nombre partido por la transcripción) da `NOT_FOUND` en vez de ofrecer las dos Lauras. Seguro.
- "…a Laura vecina gracias" deja "gracias" en el destinatario, y la agenda no lo encuentra. Seguro.
- "José" con un carácter invisible pegado se resuelve a José (el invisible separa palabras). La
  confirmación hablada sigue siendo obligatoria.
- La agenda es provisional y ficticia (`ezpay-placeholder-*`). Pagos la reemplaza antes de la demo.

## Fuera de este módulo (para Pagos)

"Sí tardío", `AWAITING_PIN` (el PIN nunca llega aquí), errores HTTP de `/turns`, actualización de
`previouslyPaid`, "no se hace ninguna cotización" y repetir las opciones tras una elección `UNCLEAR`.
