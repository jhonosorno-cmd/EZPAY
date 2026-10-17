"""Escenarios H2 de persistencia del estado global del PIN (tarea 1.4).

El contador global y el bloqueo viven en `EZPAY_PIN_DATA_DIR` (por defecto
`api/.data/pin/`) como `{"globalFailures": int, "locked": bool}`; un reinicio
del backend los conserva. Los contadores de sesión siguen en memoria. Archivo
corrupto ⇒ falla cerrado (locked). NUNCA el PIN, el hash ni ids de sesión en
el JSON. El estado es inyectable (data_dir temporal) para pruebas aisladas.
"""
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from pin.pin import PinValidator, build_hash_spec

CHEAP = {"n": 2, "r": 1, "p": 1}
TEST_PIN = "1234"


def cheap_provider(pin_str=TEST_PIN):
    spec = build_hash_spec(pin_str, **CHEAP)
    return lambda: spec


class PersistenciaBase(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temporal.cleanup()

    def validator(self):
        return PinValidator(hash_provider=cheap_provider(), data_dir=self.temporal.name)

    def contenido_estado(self):
        return (Path(self.temporal.name) / "estado.json").read_text(encoding="utf-8")


class ReinicioConservaLosFallos(PersistenciaBase):
    def test_cuatro_fallos_persisten_y_el_quinto_bloquea(self):
        primero = self.validator()
        for i in range(4):
            resultado = primero.verify("9999", f"s{i}")
            self.assertFalse(resultado.locked, i)
        # "reinicio del backend": instancia nueva sobre el MISMO directorio
        segundo = self.validator()
        self.assertEqual(segundo._global_failures, 4)  # el conteo sobrevive
        quinto = segundo.verify("9999", "s4")
        self.assertEqual(quinto.result, "WRONG")
        self.assertTrue(quinto.locked)  # el 5.º fallo acumulado bloquea
        self.assertEqual(json.loads(self.contenido_estado()), {"globalFailures": 5, "locked": True})


class ReinicioConservaElBloqueo(PersistenciaBase):
    def test_un_backend_reiniciado_sigue_bloqueado(self):
        primero = self.validator()
        for i in range(5):
            primero.verify("9999", f"s{i}")
        segundo = self.validator()
        resultado = segundo.verify(TEST_PIN, "s-nueva")  # ni el PIN correcto pasa
        self.assertEqual(resultado.result, "WRONG")
        self.assertTrue(resultado.locked)
        self.assertEqual(resultado.remaining, 0)


class PinCorrectoPersisteElReinicio(PersistenciaBase):
    def test_un_ok_guarda_global_failures_en_0(self):
        primero = self.validator()
        primero.verify("9999", "s1")
        primero.verify("9999", "s2")
        ok = primero.verify(TEST_PIN, "s3")
        self.assertEqual(ok.result, "OK")
        self.assertEqual(json.loads(self.contenido_estado()), {"globalFailures": 0, "locked": False})
        # tras reiniciar, 4 fallos nuevos NO bloquean (el global empezó en 0)
        segundo = self.validator()
        self.assertEqual(segundo._global_failures, 0)
        for i in range(4):
            resultado = segundo.verify("9999", f"s{i + 10}")
            self.assertFalse(resultado.locked, i)


class ArchivoCorruptoFallaCerrado(PersistenciaBase):
    def test_estado_ilegible_se_trata_como_bloqueado(self):
        primero = self.validator()
        primero.verify("9999", "s1")
        (Path(self.temporal.name) / "estado.json").write_text("no-es-json{{{", encoding="utf-8")
        with self.assertLogs("pin", level="WARNING") as captura:
            segundo = self.validator()  # el aviso sale AL CARGAR el estado corrupto
        self.assertTrue(segundo._locked)  # falla cerrado al iniciar
        resultado = segundo.verify(TEST_PIN, "s1")
        self.assertEqual(resultado.result, "WRONG")
        self.assertTrue(resultado.locked)
        for mensaje in captura.output:
            self.assertNotIn(TEST_PIN, mensaje)          # sin datos sensibles
            self.assertNotIn("no-es-json", mensaje)      # sin volcar el contenido
            self.assertLess(len(mensaje), 200)


class ResetPorScriptReparaElEstado(PersistenciaBase):
    def _correr_script(self):
        import subprocess
        import sys

        script = Path(__file__).resolve().parents[2] / "scripts" / "reset_pin_lock.py"
        proceso = subprocess.run(
            [sys.executable, str(script), "--data-dir", self.temporal.name],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(proceso.returncode, 0, proceso.stderr)

    def test_script_desbloquea_un_backend_reiniciado(self):
        primero = self.validator()
        for i in range(5):
            primero.verify("9999", f"s{i}")
        self.assertTrue(primero.verify("9999", "s5").locked)
        self._correr_script()
        segundo = self.validator()
        self.assertEqual(segundo._global_failures, 0)
        ok = segundo.verify(TEST_PIN, "s-nueva")
        self.assertEqual((ok.result, ok.locked), ("OK", False))

    def test_script_repara_un_archivo_corrupto(self):
        (Path(self.temporal.name) / "estado.json").write_text("corrupto]", encoding="utf-8")
        self._correr_script()
        segundo = self.validator()
        self.assertFalse(segundo._locked)
        self.assertEqual(segundo._global_failures, 0)


class ElJsonNuncaContieneDatosSensibles(PersistenciaBase):
    def test_solo_global_failures_y_locked(self):
        hash_spec = cheap_provider()()  # el hash que usa el validador
        validator = self.validator()
        validator.verify("9999", "sesion-x")
        ok = validator.verify(TEST_PIN, "sesion-x")  # un OK también persiste
        self.assertEqual(ok.result, "OK")
        contenido = self.contenido_estado()
        datos = json.loads(contenido)
        self.assertEqual(set(datos.keys()), {"globalFailures", "locked"})
        self.assertIsInstance(datos["globalFailures"], int)
        self.assertIsInstance(datos["locked"], bool)
        self.assertNotIn(TEST_PIN, contenido)   # nunca el PIN
        self.assertNotIn("9999", contenido)     # nunca un intento fallido
        self.assertNotIn("scrypt$", contenido)  # nunca el hash
        self.assertNotIn(hash_spec.split("$")[4], contenido)  # ni la sal
        self.assertNotIn("sesion-x", contenido)  # nunca ids de sesión


class ConcurrenciaConPersistencia(PersistenciaBase):
    def test_20_intentos_en_paralelo_cuentan_exacto_y_persisten(self):
        validator = self.validator()

        def attempt(i):
            return validator.verify("9999", f"s{i}")

        with ThreadPoolExecutor(max_workers=20) as pool:
            list(pool.map(attempt, range(20)))
        self.assertEqual(validator._global_failures, 5)  # sin rachas perdidas
        self.assertTrue(validator._locked)
        self.assertEqual(json.loads(self.contenido_estado()), {"globalFailures": 5, "locked": True})


if __name__ == "__main__":
    unittest.main()