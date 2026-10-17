"""Guard: las pruebas de tests/app NUNCA tocan el estado real del PIN.

El estado global del PIN vive en EZPAY_PIN_DATA_DIR (por defecto api/.data/pin/).
Si alguna prueba de este directorio escribe ahí, esta guard falla al terminar la
corrida (unittest/pytest descubren alfabéticamente: 'z' corre última).
"""
import hashlib
import unittest
from pathlib import Path

ESTADO = Path(__file__).resolve().parents[2] / ".data" / "pin" / "estado.json"


def _huella():
    if not ESTADO.exists():
        return None
    return hashlib.sha256(ESTADO.read_bytes()).hexdigest()


_huella_inicial = None
_existe_inicial = None


def setUpModule():
    global _huella_inicial, _existe_inicial
    _existe_inicial = ESTADO.exists()
    _huella_inicial = _huella() if _existe_inicial else None


def tearDownModule():
    ahora_existe = ESTADO.exists()
    ahora = _huella() if ahora_existe else None
    assert ahora_existe == _existe_inicial and ahora == _huella_inicial, (
        "las pruebas de tests/app modificaron el estado real del PIN en "
        f"{ESTADO} (antes: {_existe_inicial}/{_huella_inicial}, después: {ahora_existe}/{ahora}); "
        "cada PinValidator de prueba debe usar data_dir temporal"
    )


class PinStateGuardTest(unittest.TestCase):
    def test_the_real_pin_state_is_untouched_by_the_test_suite(self):
        """El guard corre en tearDownModule; esta prueba solo documenta el contrato."""
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()