"""Genera el hash con sal del PIN para copiar a `.env` (spec pin-validation).

El PIN se lee con getpass (nunca por argumento, nunca en claro en archivos).
Escribe en stdout la línea `EZPAY_PIN_HASH=scrypt$N$r$p$sal_b64$hash_b64`;
cópiala a `api/.env`. El PIN en claro no aparece en ningún archivo del repo.
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pin.pin import PIN_HASH_ENV, build_hash_spec, is_valid_pin


def _read_pin() -> str:
    pin = getpass.getpass("PIN nuevo (4 a 6 dígitos): ")
    confirm = getpass.getpass("Repite el PIN: ")
    if pin != confirm:
        print("Los PIN no coinciden. No se generó ningún hash.")
        raise SystemExit(1)
    if not is_valid_pin(pin):
        print("El PIN debe tener entre 4 y 6 dígitos (0-9). No se generó ningún hash.")
        raise SystemExit(1)
    return pin


def main() -> None:
    pin = _read_pin()
    spec = build_hash_spec(pin)
    print("Copia esta línea a api/.env (el PIN en claro no se guarda ni se imprime):")
    print(f"{PIN_HASH_ENV}={spec}")


if __name__ == "__main__":
    main()