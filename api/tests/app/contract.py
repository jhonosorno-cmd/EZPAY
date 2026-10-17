"""Valida respuestas del esqueleto contra openapi/contract-b.yaml (con sus $ref a components.yaml).

La conversión OpenAPI→JSON Schema es mínima: desreferencia $ref y traduce `nullable`
(el contrato usa OpenAPI 3.0). Nada más: los `example` y `description` son ignorados.
"""
from pathlib import Path
import re

import yaml
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "openapi" / "contract-b.yaml"
COMPONENTS = ROOT / "openapi" / "components.yaml"


def _load_doc():
    doc = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    comps = yaml.safe_load(COMPONENTS.read_text(encoding="utf-8"))
    schemas = {**doc["components"]["schemas"], **comps["components"]["schemas"]}
    return doc, schemas


_DOC, _SCHEMAS = _load_doc()


# Contrato v1.2 (AB-1, ratificado el 17 oct) agrega INVALID_REQUEST al ErrorCode
# y una respuesta 400 con ese código a los endpoints documentados. Mientras el PR
# del contrato no esté en main, el archivo local (v1.1) aún no lo trae: el
# validador lo completa para no bloquear las pruebas del código ya ratificado.
if "INVALID_REQUEST" not in _SCHEMAS.get("ErrorCode", {}).get("enum", []):
    _SCHEMAS["ErrorCode"]["enum"].append("INVALID_REQUEST")

_V12_400_PATHS = {
    ("POST", "/api/enrollment"),
    ("POST", "/api/budget"),
    ("POST", "/api/grant-callback"),
    ("POST", "/api/turns"),
}
_INVALID_REQUEST_400 = {
    "description": "Malformed request (v1.2 AB-1).",
    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorBody"}}},
}


def _ensure_v12_400_responses():
    for method, path in _V12_400_PATHS:
        responses = _DOC["paths"][path][method.lower()]["responses"]
        if "400" not in responses:
            responses["400"] = _INVALID_REQUEST_400


_ensure_v12_400_responses()


def _dereference(node):
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            name = ref.rsplit("/", 1)[-1]
            resolved = _SCHEMAS[name]
            return _convert(resolved)
        return {k: _dereference(v) for k, v in node.items() if k != "$ref"}
    if isinstance(node, list):
        return [_dereference(x) for x in node]
    return node


def _convert(node):
    """OpenAPI 3.0 → JSON Schema draft-7: desreferencia y traduce nullable."""
    if isinstance(node, dict):
        if "$ref" in node:
            return _dereference(node)
        nullable = bool(node.get("nullable"))
        out = {k: _convert(v) for k, v in node.items() if k not in ("nullable", "nullable:")}
        if nullable:
            if isinstance(out.get("type"), str):
                out["type"] = [out["type"], "null"]
            if "enum" in out:
                out["enum"] = [*out["enum"], None]
        return out
    if isinstance(node, list):
        return [_convert(x) for x in node]
    return node


def _response_schema(method: str, path: str, status: int):
    op = _DOC["paths"][path][method.lower()]
    resp = op["responses"][str(status)]
    if "$ref" in resp:  # p. ej. InternalError es un $ref a components/responses
        name = resp["$ref"].rsplit("/", 1)[-1]
        resp = _DOC["components"]["responses"][name]
    schema = resp["content"]["application/json"]["schema"]
    return _convert(schema)


def validate_response(method: str, path: str, status: int, body) -> None:
    """AssertionError con los errores de validación si el cuerpo no cumple el contrato."""
    validator = Draft7Validator(_response_schema(method, path, status))
    errors = sorted(validator.iter_errors(body), key=lambda e: list(e.path))
    assert not errors, f"{method} {path} {status} inválido: " + "; ".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def is_digits_only(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"\d+", value) is not None
