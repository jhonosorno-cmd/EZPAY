# 02 — Instalación y pruebas de SpeechBrain

- Fecha: 14 al 15 de octubre de 2026 (antes del evento)
- Autor: Valdex328 (Daniel, rol Verificación y calidad, ML 2)
- Herramienta: Claude Code en Traycer

Sesión "Instalación y configuración SpeechBrain": experimentos descartables de verificación de hablante hechos fuera de este repo (no se trajeron, ver `AI_USAGE.md`). El adjunto del Prompt 6 era una captura de pantalla del plan de precios de un proveedor; no se incluye.

Texto literal de los prompts de Daniel, en orden (sin las respuestas de la IA):

---

## Prompt 1

````text
instala SpeechBrain en mi equipo para utilizarlo en la hackathon. Dime qué tengo que configurar
````

## Prompt 2

````text
para que estamos instalando CUDA? no podemos utilizarlo sin?
````

## Prompt 3

````text
para la hackaton voy a hacer reconocimiento de hablantes. Dame el paso a paso de configuración y un script de prueba
````

## Prompt 4

````text
la idea es que el modelo corra haciendo llamados API, no que corra local. Reacomoda la respuesta de acuerdo a esto
````

## Prompt 5

````text
y hay alguna herramienta pública con llamadas API que no tenga que hospedar yo que podamos usar para este proyecto?
````

## Prompt 6

````text
mira el billing y dime si puede ser suficiente para esta hackathon.
Attachments: msg_d321587a-f95c-46f0-a3ff-e6aa5ce66759\image.png
````

## Prompt 7

````text
ten en cuenta que la idea es que se haga una autenticación con 3 audios de prueba predeterminados que tiene que grabar cada usuario. Luego, cada petición que se haga por voz, debe compararse con lo determinado por esos audios y decidir coincide lo suficiente.

En cada usuario cuandos voiceprints gastaría? y las peticiones gastarían vioceprints o no?

Compara esto con la opción de construir nosotros mismos el apartado de grabación de audios, extracción de características y comparación para decidir la coincidencia.
````

## Prompt 8

````text
pero no hablo de hospedar como segunda opción, sino de crear nosotros una función, con métodos de extracción de características y de comparación para los audios, que funcione en el backend. Esa es la idea que quiero comparar con el pyannote
````

## Prompt 9

````text
organiza entonces las 3 ideas, el speechbrain hospedado en mi equipo como al principio, el pyannote y la última opción. Haz una tabla comparativa y define cual es la mejor opción. Con esto, decidimos qué pruebas hacer
````

## Prompt 10

````text
el backend es con Node, entonces hagamos el plan de pruebas para la opción A. Mide el gasto de memoria,
````

## Prompt 11

````text
mueve los archivos de código a C:\Users\danie\Desktop\Hackatons\Interledger\Pruebas ML2
````

## Prompt 12

````text
Mueve también test_data y pretrained_models a Pruebas ML2, recrea el entorno virtual allí y comprueba que bench_memory.py funciona
````

## Prompt 13

````text
Continúa con la prueba 1: añade el tope de 30 s por audio en server.py y repite bench_memory.py con 30 s en paralelo
````

## Prompt 14

````text
Escribe el cliente de prueba en Node 24 y ejecuta la prueba 2 contra el servidor
````

## Prompt 15

````text
tengo ahora dos personas para grabar. Prepara un script que sea interactivo, que tenga frases predeterminadas que se deban leer para así reconocer las voces. Como la idea es realizar una primera autenticación con 3 audios para luego compararlos con los audios de las peticiones, prepara 3 frases. Todo es en español. Luego, el script debe permitirme grabar un audio de una petición, la cual tendrá textos predefinidos como "haz una transacción" y decirme quién es el hablante. Dame indicadores de similitud en caso de que sea posible. Prepara todo en la carpeta que te dije y me dices qué correr en VSCode
````

## Prompt 16

````text
Ya grabamos con las dos personas: analiza recordings/peticiones.csv y dime qué umbral recomiendas
````

## Prompt 17

````text
para mañana para la implementación, qué debemos tener en cuenta? arma la spec
````

## Prompt 18

````text
haz un resumen de las novedades encontradas con estas pruebas y súbelo a la rama del repo de revisión ml2
````

## Prompt 19

````text
está en github
````

## Prompt 20

````text
ya está pusheado?
````

---
