"""Configura el PIN de demo (1234) sin teclearlo (spec pin-validation).

Sin argumentos imprime la línea `EZPAY_PIN_HASH=scrypt$...` para copiarla a
`api/.env`. Con `--write` la escribe tú mismo en `api/.env` (reemplaza solo esa
línea). El PIN de demo es público y solo sirve para el hackathon; para uno
propio usa `make_pin_hash.py`. Después reinicia uvicorn.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pin.pin import PIN_HASH_ENV, build_hash_spec

DEMO_PIN = "1234"
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def build_env_line() -> str:
    return f"{PIN_HASH_ENV}={build_hash_spec(DEMO_PIN)}"


def upsert_env(text: str, line: str) -> str:
    lines = text.splitlines()
    for i, current in enumerate(lines):
        if current.startswith(f"{PIN_HASH_ENV}="):
            lines[i] = line
            break
    else:
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> None:
    line = build_env_line()
    if "--write" not in sys.argv:
        print("Copia esta línea a api/.env (PIN de demo 1234):")
        print(line)
        return
    text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    ENV_PATH.write_text(upsert_env(text, line), encoding="utf-8")
    print(f"PIN de demo 1234 escrito en {ENV_PATH}. Reinicia uvicorn.")


if __name__ == "__main__":
    main()
