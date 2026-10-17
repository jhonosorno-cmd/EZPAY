"""Registro local de la batería de H3 (solo desarrollo): frases, veredicto y CSV.

El CSV guarda la frase pedida, el texto transcrito y el veredicto; NUNCA audio ni llaves. Por defecto vive en
`~/ezpay-h3/resultados.csv`, fuera del repo. Cada fila es de una persona y una condición de ruido.
"""
import csv
from dataclasses import dataclass
from pathlib import Path

from voice.config import ASSET
from voice.intents import extract_intent
from voice.replies import Reply, classify_reply

CAMPOS = ["quien", "ruido", "numero", "frase", "tipo", "texto", "motor", "hubo_voz", "interpretado", "veredicto"]
_ESPERADA = {"afirmativo": Reply.YES, "negativo": Reply.NO, "poco_clara": Reply.UNCLEAR}


@dataclass(frozen=True)
class Frase:
    decir: str
    tipo: str                   # pago | afirmativo | negativo | poco_clara | silencio
    monto: str = ""             # pago: valor en unidades mínimas (escala 2)
    destinatario: str = ""      # pago: destinatario ya normalizado


FRASES = [
    Frase("Envíale veinte mil a Laura hija", "pago", "2000000", "laura hija"),
    Frase("Mándale cincuenta mil pesos a mi mamá", "pago", "5000000", "mi mama"),
    Frase("Paga ciento cincuenta mil a Laura hija", "pago", "15000000", "laura hija"),
    Frase("Sí", "afirmativo"),
    Frase("No", "negativo"),
    Frase("Confirmo", "afirmativo"),
    Frase("Cancela", "negativo"),
    Frase("Mmm... no sé", "poco_clara"),
    Frase("(silencio, no digas nada)", "silencio"),
    Frase("Dilo con ruido: pon música o habla una tele y di 'envíale veinte mil a Laura hija'", "pago",
          "2000000", "laura hija"),
]


@dataclass(frozen=True)
class Resultado:
    interpretado: str
    veredicto: str   # OK | SEGURO | NOMBRE_MAL | GRAVE | FALSA_VOZ | FILTRO_CORTO


def evaluar(frase: Frase, texto: str, hubo_voz: bool) -> Resultado:
    """Qué hizo el sistema con el texto. GRAVE = habría entendido algo distinto de lo dicho."""
    if frase.tipo == "silencio":
        return Resultado("sin voz", "OK") if not hubo_voz else Resultado(texto.strip(), "FALSA_VOZ")
    if not hubo_voz:
        return Resultado("sin voz", "FILTRO_CORTO")
    if frase.tipo == "pago":
        d = extract_intent(texto, ASSET).to_dict()
        monto = d["amount"]["value"] if d["amount"] else None
        interpretado = f"{d['action']}/{d['status']} {monto or '-'} {d['recipient'] or '-'}"
        if d["action"] != "PAY" or d["status"] != "OK" or monto is None:
            return Resultado(interpretado, "SEGURO")
        if monto != frase.monto:
            return Resultado(interpretado, "GRAVE")
        return Resultado(interpretado, "OK" if d["recipient"] == frase.destinatario else "NOMBRE_MAL")
    respuesta = classify_reply(texto)
    esperada = _ESPERADA[frase.tipo]
    if respuesta == esperada:
        return Resultado(respuesta.name, "OK")
    if respuesta in (Reply.YES, Reply.NO):
        return Resultado(respuesta.name, "GRAVE")
    return Resultado(respuesta.name, "SEGURO")


def ruta_por_defecto() -> Path:
    return Path.home() / "ezpay-h3" / "resultados.csv"


def _celda(valor) -> str:
    texto = str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto  # evita fórmulas al abrir en Excel


def agregar_fila(ruta: Path, *, quien: str, ruido: str, numero: int, frase: Frase, texto: str, motor: str,
                 hubo_voz: bool, resultado: Resultado) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta.exists()
    with ruta.open("a", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        if nuevo:
            escritor.writerow(CAMPOS)
        escritor.writerow([_celda(v) for v in (quien, ruido, numero, frase.decir,
                                                frase.tipo, texto.strip(), motor, hubo_voz, resultado.interpretado,
                                                resultado.veredicto)])


def seleccionar_frases(texto: str) -> list[tuple[int, Frase]]:
    """`"1,3,5-7"` -> [(1, f1), (3, f3), (5, f5), ...]; vacío = todas. El número es el de la lista completa."""
    if not texto.strip():
        return list(enumerate(FRASES, 1))
    numeros: list[int] = []
    for parte in texto.split(","):
        parte = parte.strip()
        try:
            if "-" in parte:
                desde, hasta = (int(x) for x in parte.split("-"))
                rango = list(range(desde, hasta + 1))
                if desde > hasta:
                    raise ValueError
            else:
                rango = [int(parte)]
        except ValueError:
            raise ValueError(f"frases inválidas: {parte!r}; usa números del 1 al {len(FRASES)}, como 1,3,5-7") from None
        for n in rango:
            if not 1 <= n <= len(FRASES):
                raise ValueError(f"la frase {n} no existe; hay de 1 a {len(FRASES)}")
            if n not in numeros:
                numeros.append(n)
    return [(n, FRASES[n - 1]) for n in numeros]
