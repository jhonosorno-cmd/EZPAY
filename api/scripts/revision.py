"""Después de grabar: escuchar (E), grabar de nuevo (R) o usar la grabación (ESPACIO). Todo en memoria (solo desarrollo)."""

MENU = "  [ESPACIO] usar   [E] escuchar   [R] grabar de nuevo"


def revisar(grabar, leer_tecla, reproducir, avisar):
    """Graba con `grabar()` y deja revisar el resultado; devuelve el PCM elegido.

    `leer_tecla()` bloquea hasta una tecla, `reproducir(pcm)` la oye por los altavoces y `avisar(texto)` imprime.
    ESPACIO o Enter usan la grabación; E la escucha (cuantas veces quieras); R la descarta y graba otra. Nada va a disco.
    """
    pcm = grabar()
    avisar(MENU)
    while True:
        tecla = str(leer_tecla()).lower()
        if tecla in (" ", "\r", "\n"):
            return pcm
        if tecla == "r":
            pcm = grabar()
            avisar(MENU)
        elif tecla == "e":
            if len(pcm) == 0:
                avisar("  No se grabó nada, no hay qué escuchar.")
            else:
                reproducir(pcm)
