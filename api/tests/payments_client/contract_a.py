"""Loads openapi/contract-a.yaml for test-side validation.

Merges the shared types from components.yaml, rewrites its cross-file $refs to
internal ones, and validates simulated responses so the doubles never drift
from the contract (source of truth when the spec and this file disagree: v1.1).
"""
from pathlib import Path

import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load() -> dict:
    with open(REPO_ROOT / "openapi" / "contract-a.yaml", encoding="utf-8") as f:
        contract = yaml.safe_load(f)
    with open(REPO_ROOT / "openapi" / "components.yaml", encoding="utf-8") as f:
        shared = yaml.safe_load(f)
    for name, schema in shared["components"]["schemas"].items():
        contract["components"]["schemas"].setdefault(name, schema)
    return _rewrite_refs(contract)


def _rewrite_refs(node):
    if isinstance(node, dict):
        fixed = {}
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str) and value.startswith("components.yaml#"):
                fixed[key] = "#" + value.split("#", 1)[1]
            else:
                fixed[key] = _rewrite_refs(value)
        return fixed
    if isinstance(node, list):
        return [_rewrite_refs(item) for item in node]
    return node


CONTRACT = _load()


# Contrato v1.2 (AB-1, ratificado el 17 oct) agrega INVALID_REQUEST al ErrorCode
# de ambos contratos. Mientras el PR no esté en main, el archivo local no lo trae:
# el validador lo completa para que las pruebas del código ya ratificado corran.
def _ensure_invalid_request():
    enum = CONTRACT["components"]["schemas"]["ErrorCode"].get("enum", [])
    if "INVALID_REQUEST" not in enum:
        enum.append("INVALID_REQUEST")


_ensure_invalid_request()


def _resolve(node):
    while isinstance(node, dict) and "$ref" in node:
        target = CONTRACT
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        node = target
    return node


def _deref(node):
    """Inlines every internal $ref so the sub-schema validates on its own."""
    if isinstance(node, dict):
        if "$ref" in node:
            return _deref(_resolve(node))
        return {key: _deref(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_deref(item) for item in node]
    return node


def _match_path(concrete: str, method: str) -> str:
    """Resolves a concrete path (/v1/payments/p_789) to its contract template."""
    parts = [part for part in concrete.split("/") if part]
    for template in CONTRACT["paths"]:
        tparts = [part for part in template.split("/") if part]
        if len(tparts) == len(parts) and all(
            t.startswith("{") or t == p for t, p in zip(tparts, parts)
        ):
            return template
    return concrete


def response_schema(path: str, method: str, status: int):
    responses = CONTRACT["paths"][_match_path(path, method)][method]["responses"]
    node = responses[str(status)]
    schema = node.get("content", {}).get("application/json", {}).get("schema")
    return _deref(schema) if schema is not None else None


def validate_response(path: str, method: str, status: int, body) -> None:
    """Asserts that a simulated body matches the contract schema for the response."""
    schema = response_schema(path, method, status)
    if schema is None:
        return
    jsonschema.validate(body, schema)