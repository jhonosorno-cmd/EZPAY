"""Registro local del experimento del banco de frases del desafío (solo desarrollo): puntaje y veredicto por frase.

Va a `~/ezpay-h3/desafio.csv`, fuera del repo, sin audio ni llaves.
"""
import csv
from dataclasses import dataclass
from pathlib import Path

from scripts.bateria import numeros_elegidos
from voice.challenge import challenge_matches, phrase_match

CAMPOS = ["quien", "ruido", "numero", "frase", "texto", "motor", "hubo_voz", "puntaje", "veredicto"]


@dataclass(frozen=True)
class Resultado:
    puntaje: float
    veredicto: str   # CUMPLE | NO_CUMPLE | FILTRO_CORTO


def evaluar(frase: str, texto: str, hubo_voz: bool) -> Resultado:
    if not hubo_voz:
        return Resultado(0.0, "FILTRO_CORTO")
    return Resultado(phrase_match(texto, frase), "CUMPLE" if challenge_matches(texto, frase) else "NO_CUMPLE")


def seleccionar(texto: str, banco: list[str]) -> list[tuple[int, str]]:
    return [(n, banco[n - 1]) for n in numeros_elegidos(texto, len(banco))]


def ruta_por_defecto() -> Path:
    return Path.home() / "ezpay-h3" / "desafio.csv"


def agregar_fila(ruta: Path, *, quien: str, ruido: str, numero: int, frase: str, texto: str, motor: str,
                 hubo_voz: bool, resultado: Resultado) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta.exists()
    with ruta.open("a", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        if nuevo:
            escritor.writerow(CAMPOS)
        celda = lambda v: ("'" + str(v)) if str(v)[:1] in ("=", "+", "-", "@") else str(v)  # noqa: E731
        escritor.writerow([celda(v) for v in (quien, ruido, numero, frase, texto.strip(), motor, hubo_voz,
                                              resultado.puntaje, resultado.veredicto)])
