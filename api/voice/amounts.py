"""amount-parsing: texto es-CO -> Amount y Amount -> texto. Sin float (CONV-1).

Aceptado aunque el spec no lo pide (decisión de Sebastián, 2026-10-16): "$", "COP", "peso(s)" y "de" como
ruido; "un millón y medio"; "20 mil 500"; tope de 1.000.000.000 pesos y de 200 caracteres de entrada.
`Amount.to_dict()` entrega la forma del contrato HTTP (camelCase); el resto del módulo usa snake_case.
"""
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class AmountError(str, Enum):
    TOO_MANY_DECIMALS = "TOO_MANY_DECIMALS"
    AMBIGUOUS_AMOUNT = "AMBIGUOUS_AMOUNT"
    INVALID_AMOUNT = "INVALID_AMOUNT"


_ASCII_DIGITS = re.compile(r"[0-9]+")


def _is_ascii_digits(s: str) -> bool:
    return _ASCII_DIGITS.fullmatch(s) is not None


def _check_scale(scale) -> None:
    if type(scale) is not int or scale < 0:
        raise ValueError(f"asset_scale must be an int >= 0, got {scale!r}")


@dataclass(frozen=True)
class AssetConfig:
    asset_code: str
    asset_scale: int

    def __post_init__(self):
        _check_scale(self.asset_scale)


@dataclass(frozen=True)
class Amount:
    value: str
    asset_code: str
    asset_scale: int

    def __post_init__(self):
        v = self.value
        if not isinstance(v, str) or not _is_ascii_digits(v) or (len(v) > 1 and v[0] == "0"):
            raise ValueError(f"Amount.value must be ASCII digits without leading zeros, got {v!r}")
        _check_scale(self.asset_scale)

    def to_dict(self) -> dict:
        """Forma del contrato HTTP (camelCase): {value, assetCode, assetScale}."""
        return {"value": self.value, "assetCode": self.asset_code, "assetScale": self.asset_scale}


@dataclass(frozen=True)
class AmountResult:
    ok: bool
    amount: Amount | None = None
    code: AmountError | None = None


def _fail(code: AmountError) -> AmountResult:
    return AmountResult(False, None, code)


UNITS = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
    "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
    "veintiun": 21, "veintiuno": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
    "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400,
    "quinientos": 500, "quinientas": 500, "seiscientos": 600, "seiscientas": 600,
    "setecientos": 700, "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
    "novecientos": 900, "novecientas": 900,
}
UNIT_WORDS = {w for w, v in UNITS.items() if 1 <= v <= 9}
NOISE = {"peso", "pesos", "cop", "de", "$", "colombiano", "colombianos"}
# Jerga conocida: sin valor validado todavía (X-5), así que es ambigua. Con tabla -> multiplicador.
SLANG_WORDS = {"luca", "lucas", "luka", "lukas", "barra", "barras", "palo", "palos", "k"}
THOUSANDS = re.compile(r"[1-9][0-9]{0,2}(\.[0-9]{3})+")
MAX_INPUT_CHARS = 200
MAX_PESOS = 1_000_000_000
MAX_PESOS_DIGITS = len(str(MAX_PESOS))
MAX_TOKEN_DIGITS = 12


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").strip()


def _level(value: int) -> int:
    """Orden de un componente: 1 unidades, 2 decenas (10 a 99), 3 centenas."""
    return 1 if value < 10 else 2 if value < 100 else 3


def _validated_slang(slang) -> dict[str, int]:
    """Tabla de jerga validada: error de configuración (ValueError), no de usuario."""
    table: dict[str, int] = {}
    for key, mult in (slang or {}).items():
        if type(mult) is not int or mult <= 0:
            raise ValueError(f"slang[{key!r}] must be a positive int (not bool), got {mult!r}")
        table[_norm(key)] = mult
    return table


def _numeric_token(tok: str, scale: int) -> tuple[str, str] | AmountError:
    """Token solo con dígitos, puntos y comas -> (enteros, decimales) o error. Regla es-CO."""
    if tok.count(",") > 1:
        return AmountError.AMBIGUOUS_AMOUNT
    int_part, _, frac = tok.partition(",")
    if "," in tok and not _is_ascii_digits(frac):
        return AmountError.AMBIGUOUS_AMOUNT
    if len(frac) == 3 and frac[2] == "0" and _is_ascii_digits(int_part) and len(int_part) <= 3 and int(int_part) > 0:
        return AmountError.AMBIGUOUS_AMOUNT        # "150,000": la transcripción suele usar la coma para miles
    if "." in int_part:
        if not THOUSANDS.fullmatch(int_part):
            return AmountError.AMBIGUOUS_AMOUNT
        int_part = int_part.replace(".", "")
    if not _is_ascii_digits(int_part):
        return AmountError.AMBIGUOUS_AMOUNT
    if len(int_part) > MAX_PESOS_DIGITS:
        return AmountError.INVALID_AMOUNT
    if len(frac) > scale and frac[scale:].strip("0"):
        return AmountError.TOO_MANY_DECIMALS
    whole = int(int_part)
    if whole > MAX_PESOS or (whole == MAX_PESOS and frac.strip("0")):
        return AmountError.INVALID_AMOUNT
    return int_part, frac[:scale].ljust(scale, "0")


def _words_to_int(tokens: list[str], slang: dict[str, int]) -> int | AmountError:
    """Monto en palabras (o dígitos sueltos) -> pesos enteros. Cada componente debe ser de orden
    estrictamente menor que el anterior: millones > miles > centenas > decenas > unidades."""
    ambiguous, invalid = AmountError.AMBIGUOUS_AMOUNT, AmountError.INVALID_AMOUNT
    total = 0
    scales = 2                 # 2: aún cabe "millones"; 1: solo "mil"; 0: ninguna escala más
    group: int | None = None   # grupo en curso (centenas, decenas, unidades) o un token de dígitos
    level = 4                  # orden del último componente del grupo
    last = 0                   # valor del último componente
    digits = False             # el grupo en curso es un token de dígitos
    y_unit = y_medio = medio_used = False
    closed_million = False     # el token anterior cerró "millón(es)"
    i = 0
    while i < len(tokens):
        t = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        prev_closed, closed_million = closed_million, False
        if t == "y":
            if (group is not None and not digits and level == 2 and 20 <= last < 100
                    and last % 10 == 0 and nxt in UNIT_WORDS):
                y_unit = True
            elif prev_closed and nxt == "medio" and not medio_used:
                y_medio = True
            else:
                return ambiguous
        elif _is_ascii_digits(t):
            if len(t) > MAX_TOKEN_DIGITS:
                return invalid
            if group is not None:
                return ambiguous
            n = int(t)
            if scales < 2 and n >= 1000:
                return ambiguous
            group, level, digits = n, 0, True
        elif re.fullmatch(r"[0-9.,]+", t):
            return ambiguous
        elif t in UNITS:
            value = UNITS[t]
            lv = _level(value)
            if digits:
                return ambiguous
            if group is not None:
                if lv >= level or (level == 2 and lv == 1 and not y_unit):
                    return ambiguous
            group = (group or 0) + value
            level, last, y_unit = lv, value, False
        elif t == "mil":
            if scales < 1:
                return ambiguous
            total += (1 if group is None else group) * 1000
            group, level, digits, scales = None, 4, False, 0
        elif t in ("millon", "millones"):
            if scales < 2:
                return ambiguous
            total += (1 if group is None else group) * 1_000_000
            group, level, digits, scales = None, 4, False, 1
            closed_million = True
        elif t == "medio":
            if y_medio and not medio_used:
                total += 500_000
                y_medio, medio_used = False, True
            elif group is None and scales == 2 and not medio_used and nxt in ("millon", "millones"):
                total += 500_000
                medio_used, scales, closed_million = True, 1, True
                i += 1
            else:
                return ambiguous
        elif t in slang:
            if group is None or total != 0 or i != len(tokens) - 1:
                return ambiguous
            total += group * slang[t]
            group = None
        elif t in SLANG_WORDS:
            return ambiguous
        else:
            return invalid
        i += 1
    if y_unit or y_medio:
        return ambiguous
    return total + (0 if group is None else group)


def parse_amount(text: str | None, cfg: AssetConfig, slang: dict[str, int] | None = None) -> AmountResult:
    """Convierte un monto dicho o escrito en es-CO a Amount. `slang` es la tabla validada (vacía por defecto).

    Nunca lanza por el texto: toda entrada produce un AmountResult. Solo una tabla de jerga mal
    configurada lanza ValueError.
    """
    table = _validated_slang(slang)
    if not isinstance(text, str) or len(text) > MAX_INPUT_CHARS or not text.strip():
        return _fail(AmountError.INVALID_AMOUNT)
    t = _norm(text)
    if any(ord(c) > 127 and unicodedata.category(c).startswith("N") for c in t):
        return _fail(AmountError.INVALID_AMOUNT)
    if t.startswith("-"):
        return _fail(AmountError.INVALID_AMOUNT)
    tokens = [w for w in re.split(r"\s+", t.replace("$", " ")) if w and w not in NOISE]
    # "20.000 pesos" suele venir de la transcripción: un número formateado junto a palabras
    # (los tokens sueltos formateados ya se resuelven arriba).
    tokens = [w.replace(".", "") if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", w) else w for w in tokens]
    if not tokens:
        return _fail(AmountError.INVALID_AMOUNT)
    scale = cfg.asset_scale
    if len(tokens) == 1 and re.fullmatch(r"[0-9.,]+", tokens[0]):
        r = _numeric_token(tokens[0], scale)
        if isinstance(r, AmountError):
            return _fail(r)
        digits = r[0] + r[1]
    else:
        n = _words_to_int(tokens, table)
        if isinstance(n, AmountError):
            return _fail(n)
        if n > MAX_PESOS:
            return _fail(AmountError.INVALID_AMOUNT)
        digits = str(n * 10**scale)
    digits = digits.lstrip("0")
    if not digits:
        return _fail(AmountError.INVALID_AMOUNT)
    return AmountResult(True, Amount(digits, cfg.asset_code, scale))


def format_amount(amount: Amount) -> str:
    """Amount -> '20.000' o '10,50', operando sobre el string `value`."""
    scale = amount.asset_scale
    digits = amount.value.lstrip("0").rjust(scale + 1, "0")
    int_part, frac = (digits[:-scale], digits[-scale:]) if scale else (digits, "")
    groups = []
    while len(int_part) > 3:
        groups.insert(0, int_part[-3:])
        int_part = int_part[:-3]
    groups.insert(0, int_part)
    out = ".".join(groups)
    if frac.strip("0"):
        out += "," + frac
    return out
