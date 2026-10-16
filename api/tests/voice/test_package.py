"""Pruebas de todo el paquete `voice`: sin LLM, sin red, sin efectos laterales y sin float.
Cubre "Sin llamada al LLM" (reply-classification) y "La extracción no tiene efectos laterales"
(intent-extraction)."""
import ast
import importlib
from pathlib import Path

import pytest

import voice

MODULES = sorted(p.stem for p in Path(voice.__file__).parent.glob("*.py") if p.stem != "__init__")
ALLOWED_IMPORTS = {"re", "unicodedata", "dataclasses", "enum", "json", "pathlib", "collections.abc", "voice"}


def _tree(name):
    return ast.parse(Path(importlib.import_module(f"voice.{name}").__file__).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", MODULES)
def test_solo_importa_la_libreria_estandar_minima(name):
    for node in ast.walk(_tree(name)):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""]
        else:
            continue
        for mod in mods:
            assert mod in ALLOWED_IMPORTS or mod.startswith("voice."), f"{name} importa {mod}"


@pytest.mark.parametrize("name", MODULES)
def test_sin_float_round_ni_decimal(name):
    for node in ast.walk(_tree(name)):
        assert not (isinstance(node, ast.Name) and node.id in {"float", "round", "Decimal"}), name
        assert not (isinstance(node, ast.Constant) and isinstance(node.value, float)), name
        assert not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)), name


@pytest.mark.parametrize("name", MODULES)
def test_sin_red_ni_escritura_a_disco(name):
    calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
             for n in ast.walk(_tree(name)) if isinstance(n, ast.Call)}
    assert not calls & {"open", "write_text", "write_bytes", "urlopen", "socket", "post", "get_ilp"}, name


def test_cubre_los_modulos_esperados():
    assert {"amounts", "replies", "phrases", "contacts", "intents", "text", "config"} <= set(MODULES)
