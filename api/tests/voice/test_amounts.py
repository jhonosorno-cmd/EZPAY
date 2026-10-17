"""Pruebas de amount-parsing: una por escenario de
openspec/changes/add-voice-understanding/specs/amount-parsing/spec.md, más las frases de
docs/voz/frases-desarrollo.md (sección A)."""
import ast
import inspect
import re

import pytest

from voice import amounts as amounts_module
from voice.amounts import Amount, AmountError, AmountResult, AssetConfig, format_amount, parse_amount

COP = AssetConfig("COP", 2)
AMBIG = AmountError.AMBIGUOUS_AMOUNT
INVALID = AmountError.INVALID_AMOUNT


def ok(text, cfg=COP):
    r = parse_amount(text, cfg)
    assert r.ok, f"{text!r} -> {r.code}"
    return r.amount


def err(text, cfg=COP):
    r = parse_amount(text, cfg)
    assert not r.ok, f"{text!r} -> {r.amount}"
    assert r.amount is None
    return r.code


# --- Formato es-CO de montos escritos
def test_punto_de_miles():
    assert ok("20.000") == Amount("2000000", "COP", 2)


def test_coma_decimal():
    assert ok("10,50") == Amount("1050", "COP", 2)


def test_punto_ambiguo():
    assert err("10.50") == AmountError.AMBIGUOUS_AMOUNT


def test_miles_con_decimales():
    assert ok("1.500,50") == Amount("150050", "COP", 2)


@pytest.mark.parametrize("text,value", [
    ("1.000.000", "100000000"), ("0,10", "10"), ("50", "5000"),
])
def test_escritos_extra(text, value):
    assert ok(text).value == value


@pytest.mark.parametrize("text", ["1.5", "1.5000", "12.34.567", "1..000", ".500", "20.00"])
def test_punto_malo_es_ambiguo(text):
    assert err(text) == AmountError.AMBIGUOUS_AMOUNT


# --- Montos con palabras
@pytest.mark.parametrize("text,value", [
    ("veinte mil", "2000000"),
    ("20 mil", "2000000"),
    ("veinte mil quinientos", "2050000"),
    ("quince mil", "1500000"),
    ("cuarenta y cinco mil", "4500000"),
    ("doscientos cincuenta mil", "25000000"),
    ("trescientos mil", "30000000"),
    ("dieciocho mil", "1800000"),
    ("cien mil", "10000000"),
    ("100 mil pesos", "10000000"),
    ("50 mil", "5000000"),
    ("tres mil quinientos", "350000"),
    ("medio millón", "50000000"),
    ("medio millon", "50000000"),
    ("un millón", "100000000"),
    ("dos millones quinientos mil", "250000000"),
    ("mil", "100000"),
    ("veintiún mil", "2100000"),
    ("treinta y un mil", "3100000"),
    ("Veinte MIL pesos", "2000000"),
    ("veinte mil pesos", "2000000"),
])
def test_palabras(text, value):
    assert ok(text).value == value


# --- Jerga
@pytest.mark.parametrize("text", ["20 lucas", "una barra", "veinte lukas"])
def test_jerga_fuera_de_la_tabla(text):
    assert err(text) == AmountError.AMBIGUOUS_AMOUNT


def test_jerga_con_tabla_configurada():
    r = parse_amount("20 lucas", COP, slang={"lucas": 1000})
    assert r.ok and r.amount.value == "2000000"


# --- Decimales que sobran
def test_mas_decimales_que_la_escala():
    assert err("10,505") == AmountError.TOO_MANY_DECIMALS


def test_caso_que_un_float_redondea():
    assert err("1,005") == AmountError.TOO_MANY_DECIMALS


def test_cero_sobrante():
    assert err("10,500") == AMBIG  # antes 10,50; cambio: puede ser 10.500 con coma de miles (ver "Coma con tres dígitos")


def test_escala_cero_con_decimales():
    assert err("10,50", AssetConfig("COP", 0)) == AmountError.TOO_MANY_DECIMALS


# --- No válidos
@pytest.mark.parametrize("text", ["cero pesos", "cero", "0", "0,00", "-3", "", "   ", "hola"])
def test_invalidos(text):
    assert err(text) == AmountError.INVALID_AMOUNT


def test_none_es_invalido():
    assert err(None) == AmountError.INVALID_AMOUNT


# --- Sin float
def test_suma_que_un_float_falla():
    total = sum(int(ok(t).value) for t in ("0,10", "0,20", "19,99"))
    assert str(total) == "2029"


def test_value_es_siempre_str_de_digitos():
    for t in ("20.000", "veinte mil", "10,50"):
        v = ok(t).value
        assert isinstance(v, str) and v.isascii() and v.isdigit() and not v.startswith("0")


# --- Formato
def test_formato_entero():
    assert format_amount(Amount("2000000", "COP", 2)) == "20.000"


def test_formato_centavos():
    assert format_amount(Amount("1050", "COP", 2)) == "10,50"


@pytest.mark.parametrize("value,scale,text", [
    ("10", 2, "0,10"), ("100000000", 2, "1.000.000"), ("150050", 2, "1.500,50"),
    ("20000", 0, "20.000"), ("5", 0, "5"), ("0", 2, "0"),
])
def test_formato_casos(value, scale, text):
    assert format_amount(Amount(value, "COP", scale)) == text


@pytest.mark.parametrize("value,scale", [("2000000", 2), ("1050", 2), ("10", 2), ("150050", 2), ("20000", 0)])
def test_ida_y_vuelta(value, scale):
    a = Amount(value, "COP", scale)
    assert ok(format_amount(a), AssetConfig("COP", scale)) == a


# --- Moneda y escala por configuración
def test_escala_distinta():
    a = ok("20.000", AssetConfig("COP", 0))
    assert a == Amount("20000", "COP", 0)


def test_moneda_viene_de_la_configuracion():
    assert ok("20.000", AssetConfig("USD", 2)).asset_code == "USD"


# --- H-1: gramática mínima de montos en palabras
@pytest.mark.parametrize("text", [
    "veinte veinte", "20 000", "20 000", "20 000", "1 000 000", "20.000 30.000",
    "diez mil mil", "veinte mil y treinta mil",
    "veinte cinco",
])
def test_h1_mismo_orden_o_espacio_de_miles_es_ambiguo(text):
    assert err(text) == AMBIG


@pytest.mark.parametrize("text", ["mil millones", "dos mil millones", "mil doscientos millones"])
def test_h1_mil_millones_es_ambiguo(text):
    assert err(text) == AMBIG


@pytest.mark.parametrize("text,value", [
    ("treinta y cinco", "3500"),
    ("veinte y cinco", "2500"),
    ("treinta y cinco mil", "3500000"),
    ("treinta y un mil", "3100000"),
    ("un millón y medio", "150000000"),
    ("dos millones y medio", "250000000"),
])
def test_h1_y_valida(text, value):
    assert ok(text).value == value


@pytest.mark.parametrize("text", [
    "veinte y treinta", "quince y cinco", "cien y cinco", "y veinte mil", "veinte mil y",
    "veinte mil y quinientos", "mil y medio", "tres y medio",
    "un millón medio",
])
def test_h1_y_invalida_es_ambigua(text):
    assert err(text) == AMBIG


@pytest.mark.parametrize("text,value", [      # la gramática no puede rechazar lo válido
    ("20 mil 500", "2050000"), ("20 mil 5", "2000500"), ("veinte mil cinco", "2000500"),
    ("mil quinientos", "150000"), ("ciento veinte mil", "12000000"), ("ciento cinco", "10500"),
    ("novecientos noventa y nueve millones novecientos noventa y nueve mil novecientos noventa y nueve",
     "99999999900"),
])
def test_h1_lo_valido_sigue_valido(text, value):
    assert ok(text).value == value


def test_h1_tope_exacto_es_valido():
    assert ok("1.000.000.000").value == "100000000000"


@pytest.mark.parametrize("text", [
    "1.000.000.001", "20.000.000.000", "1.000.000.000,50", "2000 millones",
    "99999999999999999999 mil",
])
def test_h1_sobre_el_tope_es_invalido(text):
    assert err(text) == INVALID


def test_h1_tope_no_depende_de_la_escala():
    cfg0 = AssetConfig("COP", 0)
    assert ok("1.000.000.000", cfg0).value == "1000000000"
    assert err("1.000.000.001", cfg0) == INVALID


# --- H-2: solo dígitos ASCII; ninguna entrada lanza
@pytest.mark.parametrize("text", [
    "٣", "٣ mil", "٢٠.٠٠٠", "２０", "２０ mil",
    "²", "² mil", "①", "① mil", "10,٥٠", "20．000",
])
def test_h2_digitos_no_ascii_son_invalidos(text):
    assert err(text) == INVALID


@pytest.mark.parametrize("bad", [20, b"20", ["20"], {"a": 1}, 2.5])
def test_h2_entrada_que_no_es_texto_es_invalida(bad):
    assert err(bad) == INVALID


HOSTILE = [
    "٣", "２０", "² mil", "① mil", "10,٥٠", "veinte​mil",
    "−3", "20 000", "1 000 000", "dos mil millones", "veinte mil y treinta mil",
    "1" * 5000 + " mil", "1" + ".000" * 2000, "9" * 300, "99999999999999999999 mil",
    "", "   ", "\x00", "$", "y", "de", "20,000", "1,000", "10.505", "20 gambas", "20lucas",
]


@pytest.mark.parametrize("text", HOSTILE, ids=[f"hostil{i}" for i in range(len(HOSTILE))])
def test_h2_nunca_lanza_y_value_es_ascii(text):
    r = parse_amount(text, COP)
    assert isinstance(r, AmountResult)
    if r.ok:
        assert re.fullmatch(r"[0-9]+", r.amount.value)
        assert r.amount.value == "0" or not r.amount.value.startswith("0")
    else:
        assert r.amount is None and isinstance(r.code, AmountError)


# --- H-3: topes
def test_h3_entrada_enorme_no_lanza():
    assert err("1" * 5000 + " mil") == INVALID


def test_h3_tope_de_digitos_por_token_antes_de_int():
    assert err("1" * 100 + " mil") == INVALID          # 104 caracteres: solo lo frena el tope por token


def test_h3_limite_de_200_caracteres():
    assert ok("veinte mil" + " " * 190).value == "2000000"       # exactamente 200
    assert err("veinte mil" + " " * 191) == INVALID              # 201
    assert err("veinte mil " * 30) == INVALID


# --- H-5: tabla de jerga (error de configuración -> ValueError)
@pytest.mark.parametrize("bad", [1000.5, -1, 0, True, "1000", None])
def test_h5_jerga_con_multiplicador_invalido(bad):
    with pytest.raises(ValueError, match="lucas"):
        parse_amount("20 lucas", COP, slang={"lucas": bad})


def test_h5_la_tabla_se_valida_aunque_el_texto_sea_invalido():
    with pytest.raises(ValueError, match="lucas"):
        parse_amount("", COP, slang={"lucas": -1})


# --- H-6: validación de Amount y AssetConfig
@pytest.mark.parametrize("value", ["abc", "", "-5", "05", "2.5", "٣", " 5", 20000, None])
def test_h6_amount_value_invalido(value):
    with pytest.raises(ValueError):
        Amount(value, "COP", 2)


@pytest.mark.parametrize("scale", [-1, 2.0, True, "2", None])
def test_h6_escala_invalida(scale):
    with pytest.raises(ValueError):
        Amount("100", "COP", scale)
    with pytest.raises(ValueError):
        AssetConfig("COP", scale)


def test_h6_amount_valido_y_cero():
    assert Amount("0", "COP", 2).value == "0"
    assert Amount("2000000", "COP", 2).to_dict() == {
        "value": "2000000", "assetCode": "COP", "assetScale": 2}


# --- Femeninos
@pytest.mark.parametrize("text,pesos", [
    ("doscientas mil pesos", 200_000), ("trescientas mil", 300_000), ("cuatrocientas mil", 400_000),
    ("quinientas mil", 500_000), ("seiscientas mil", 600_000), ("setecientas mil", 700_000),
    ("ochocientas mil", 800_000), ("novecientas mil", 900_000),
    ("quinientas veinte mil", 520_000), ("veintiuna mil", 21_000), ("treinta y una mil", 31_000),
])
def test_femeninos(text, pesos):
    assert ok(text).value == str(pesos * 100)


def test_una_sola_es_un_peso():
    assert ok("una").value == "100"


# --- H-8: sin float, round ni Decimal en el módulo (recorrido con ast)
def _forbidden(source):
    found = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Name) and n.id in {"float", "round", "Decimal"}:
            found.append(n.id)
        elif isinstance(n, ast.Attribute) and n.attr == "Decimal":
            found.append(n.attr)
        elif isinstance(n, (ast.Import, ast.ImportFrom)) and "decimal" in ast.dump(n):
            found.append("decimal")
        elif isinstance(n, ast.Constant) and isinstance(n.value, float):
            found.append("float literal")
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            found.append("true division")
    return found


def test_h8_el_detector_funciona():
    assert _forbidden("x = float(1)") == ["float"]
    assert _forbidden("y = round(2)") == ["round"]
    assert _forbidden("from decimal import Decimal") == ["decimal"]
    assert _forbidden("a = 1 / 2") == ["true division"]
    assert _forbidden("b = 1.5") == ["float literal"]


def test_h8_amounts_no_usa_float_round_ni_decimal():
    assert _forbidden(inspect.getsource(amounts_module)) == []


# --- Coma con tres dígitos: Groq la escribe como separador de miles ("$150,000"). Esperaba 150.000; pasaba 150 pesos.
# Cambio z: es ambigua y se vuelve a preguntar (antes "20,000" se leía como 20 pesos, H-4).
@pytest.mark.parametrize("text", ["20,000", "1,000", "150,000", "$150,000", "999,990", "10,500", "50,000 pesos"])
def test_coma_seguida_de_tres_digitos_es_ambigua(text):
    assert err(text) == AMBIG


@pytest.mark.parametrize("text,value", [("10,50", "1050"), ("10,5", "1050"), ("1,5", "150"), ("0,500", "50"),
                                         ("1.150,50", "115050"), ("20.000", "2000000"), ("150.000", "15000000")])
def test_otras_comas_y_los_puntos_de_miles_siguen_igual(text, value):
    assert ok(text).value == value
