"""Escenarios del spec pin-validation: alta por configuración, formato,
contadores, privacidad e interfaz del componente. Incluye pruebas del script
make_pin_hash (el hash se genera dentro de la prueba con scrypt barato; nunca
hay un PIN ni un hash real en los archivos)."""
import base64
import hashlib
import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from pin import pin as pin_module
from pin.pin import (
    PIN_HASH_ENV,
    PinError,
    PinResult,
    PinValidator,
    build_hash_spec,
    reset_pin_lock,
    verify_pin,
)

CHEAP = {"n": 2, "r": 1, "p": 1}
TEST_PIN = "1234"


def cheap_provider(pin_str=TEST_PIN):
    spec = build_hash_spec(pin_str, **CHEAP)
    return lambda: spec


class TestMakePinHash(unittest.TestCase):
    def _load_script(self):
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "scripts" / "make_pin_hash.py"
        spec = importlib.util.spec_from_file_location("make_pin_hash", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_alta_del_pin(self):
        script = self._load_script()
        spec = build_hash_spec("2468", **CHEAP)
        parts = spec.split("$")
        self.assertEqual(len(parts), 6)
        self.assertEqual(parts[0], "scrypt")
        self.assertEqual(parts[1], "2")
        salt = base64.b64decode(parts[4])
        expected = hashlib.scrypt(b"2468", salt=salt, n=2, r=1, p=1, dklen=32)
        self.assertEqual(base64.b64decode(parts[5]), expected)

    def test_dos_ejecuciones_producen_sales_distintas(self):
        self.assertNotEqual(build_hash_spec("2468", **CHEAP), build_hash_spec("2468", **CHEAP))

    def test_main_imprime_para_env_y_no_el_pin(self):
        script = self._load_script()
        with mock.patch.object(script.getpass, "getpass", side_effect=["2468", "2468"]):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                script.main()
        out = buffer.getvalue()
        self.assertIn(f"{PIN_HASH_ENV}=", out)
        line = next(line for line in out.splitlines() if line.startswith(f"{PIN_HASH_ENV}="))
        self.assertEqual(len(line.split("$")), 6)
        self.assertNotIn("2468", out)

    def test_confirmacion_distinta_no_imprime_hash(self):
        script = self._load_script()
        with mock.patch.object(script.getpass, "getpass", side_effect=["2468", "8642"]):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                with self.assertRaises(SystemExit):
                    script.main()
        self.assertNotIn(f"{PIN_HASH_ENV}=", buffer.getvalue())

    def test_pin_fuera_de_formato_rechazado(self):
        script = self._load_script()
        with mock.patch.object(script.getpass, "getpass", side_effect=["12", "12"]):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                with self.assertRaises(SystemExit):
                    script.main()
        self.assertNotIn(f"{PIN_HASH_ENV}=", buffer.getvalue())


class AltaPorConfiguracionNuncaEnClaro(unittest.TestCase):
    def test_sin_pin_configurado_nunca_ok(self):
        validator = PinValidator(hash_provider=lambda: None)
        for attempt in ("1234", "0000", "123456"):
            result = validator.verify(attempt, "s1")
            self.assertEqual(result.result, "WRONG")
            self.assertNotEqual(result.result, "OK")

    def test_sin_pin_configurado_consum_intentos(self):
        validator = PinValidator(hash_provider=lambda: None)
        validator.verify("1234", "s1")
        validator.verify("1234", "s1")
        third = validator.verify("1234", "s1")
        self.assertEqual(third.sessionFailures, 3)

    def test_spec_malformado_falla_cerrado_sin_pin_en_el_error(self):
        validator = PinValidator(hash_provider=lambda: "no-es-un-hash")
        with self.assertRaises(PinError) as ctx:
            validator.verify(TEST_PIN, "s1")
        self.assertNotIn(TEST_PIN, str(ctx.exception))

    def test_variable_de_entorno_documentada(self):
        self.assertEqual(PIN_HASH_ENV, "EZPAY_PIN_HASH")


class FormatoYComparacionEnTiempoConstante(unittest.TestCase):
    def test_formato_invalido(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for bad in ("abcd", "12a4", "123", "1234567", "12 4", "", "12.4"):
            result = validator.verify(bad, "s1")
            self.assertEqual(result.result, "INVALID_FORMAT", repr(bad))
            self.assertEqual(result.sessionFailures, 0)

    def test_formato_invalido_no_altera_los_contadores(self):
        validator = PinValidator(hash_provider=cheap_provider())
        validator.verify("9999", "s1")
        validator.verify("9999", "s1")
        after_invalid = validator.verify("12a4", "s1")
        self.assertEqual(after_invalid.sessionFailures, 2)
        after_invalid_again = validator.verify("123", "s1")
        self.assertEqual(after_invalid_again.sessionFailures, 2)

    def test_formato_valido_acepta_4_a_6_digitos(self):
        validator = PinValidator(hash_provider=cheap_provider("12345"))
        for candidate in ("1234", "12345", "123456"):
            result = validator.verify(candidate, "s1")
            self.assertIn(result.result, ("OK", "WRONG"))

    def test_formato_invalido_no_invoca_el_kdf(self):
        calls = []
        original = hashlib.scrypt

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        validator = PinValidator(hash_provider=cheap_provider())
        with mock.patch.object(hashlib, "scrypt", counting):
            validator.verify("12a4", "s1")
        self.assertEqual(calls, [])

    def test_comparacion_usa_hmac_compare_digest(self):
        import hmac as hmac_module

        validator = PinValidator(hash_provider=cheap_provider())
        with mock.patch.object(pin_module.hmac, "compare_digest", wraps=hmac_module.compare_digest) as spy:
            validator.verify("9999", "s1")
        self.assertTrue(spy.called)


class ContadoresDeIntentos(unittest.TestCase):
    def test_tercer_fallo_de_la_sesion(self):
        validator = PinValidator(hash_provider=cheap_provider())
        first = validator.verify("9999", "s1")
        self.assertEqual((first.result, first.sessionFailures, first.remaining), ("WRONG", 1, 2))
        second = validator.verify("9999", "s1")
        self.assertEqual((second.result, second.sessionFailures, second.remaining), ("WRONG", 2, 1))
        third = validator.verify("9999", "s1")
        self.assertEqual((third.result, third.sessionFailures, third.remaining, third.locked), ("WRONG", 3, 0, False))

    def test_sesiones_aisladas(self):
        validator = PinValidator(hash_provider=cheap_provider())
        validator.verify("9999", "s1")
        validator.verify("9999", "s1")
        other = validator.verify("9999", "s2")
        self.assertEqual(other.sessionFailures, 1)

    def test_bloqueo_global_al_quinto_fallo(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for i in range(4):
            result = validator.verify("9999", f"s{i}")
            self.assertFalse(result.locked, i)
        fifth = validator.verify("9999", "s4")
        self.assertEqual(fifth.result, "WRONG")
        self.assertTrue(fifth.locked)

    def test_con_el_pin_bloqueado_no_se_validan_mas_intentos(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for i in range(5):
            validator.verify("9999", f"s{i}")
        with mock.patch.object(hashlib, "scrypt", side_effect=AssertionError("no debe invocar el KDF")):
            result = validator.verify(TEST_PIN, "s99")
        self.assertEqual(result.result, "WRONG")
        self.assertTrue(result.locked)
        self.assertEqual(result.remaining, 0)

    def test_bloqueo_global_acumulado_entre_sesiones(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for i in range(3):
            validator.verify("9999", "s1")
        for i in range(2):
            result = validator.verify("9999", "s2")
        self.assertTrue(result.locked)

    def test_pin_correcto_reinicia_el_contador_global(self):
        validator = PinValidator(hash_provider=cheap_provider())
        validator.verify("9999", "s1")
        validator.verify("9999", "s2")
        ok = validator.verify(TEST_PIN, "s3")
        self.assertEqual((ok.result, ok.locked), ("OK", False))
        for i in range(4):
            result = validator.verify("9999", f"s{i + 10}")
            self.assertFalse(result.locked, i)

    def test_pin_correcto_no_reinicia_el_contador_de_sesion(self):
        validator = PinValidator(hash_provider=cheap_provider())
        validator.verify("9999", "s1")
        validator.verify("9999", "s1")
        ok = validator.verify(TEST_PIN, "s1")
        self.assertEqual(ok.result, "OK")
        again = validator.verify("9999", "s1")
        self.assertEqual(again.sessionFailures, 3)

    def test_reinicio_del_backend_en_h1(self):
        validator = PinValidator(hash_provider=cheap_provider())
        validator.verify("9999", "s1")
        validator.verify("9999", "s1")
        fresh = PinValidator(hash_provider=cheap_provider())
        result = fresh.verify(TEST_PIN, "s1")
        self.assertEqual((result.result, result.sessionFailures, result.locked), ("OK", 0, False))

    def test_script_de_reinicio(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for i in range(5):
            validator.verify("9999", f"s{i}")
        self.assertTrue(validator.verify("9999", "s5").locked)
        validator.reset_lock()
        ok = validator.verify(TEST_PIN, "s6")
        self.assertEqual((ok.result, ok.locked, ok.sessionFailures), ("OK", False, 0))


class PrivacidadDelPin(unittest.TestCase):
    def test_el_pin_no_aparece_en_repr_del_resultado(self):
        validator = PinValidator(hash_provider=cheap_provider())
        result = validator.verify("9999", "s1")
        self.assertNotIn("9999", repr(result))
        ok = validator.verify(TEST_PIN, "s1")
        self.assertNotIn(TEST_PIN, repr(ok))

    def test_el_pin_no_aparece_en_excepciones(self):
        validator = PinValidator(hash_provider=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        with self.assertRaises(PinError) as ctx:
            validator.verify(TEST_PIN, "s1")
        self.assertNotIn(TEST_PIN, str(ctx.exception))
        self.assertNotIn(TEST_PIN, repr(ctx.exception))

    def test_el_pin_no_va_a_stdout_ni_a_logs(self):
        validator = PinValidator(hash_provider=cheap_provider())
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            validator.verify("9999", "s1")
            validator.verify(TEST_PIN, "s1")
        self.assertNotIn(TEST_PIN, buffer.getvalue())
        self.assertNotIn("9999", buffer.getvalue())


class SesionAgotadaDefensaEnProfundidad(unittest.TestCase):
    def test_sesion_con_tres_fallos_no_valida_mas(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for _ in range(3):
            validator.verify("9999", "s1")
        with mock.patch.object(hashlib, "scrypt", side_effect=AssertionError("no debe invocar el KDF")):
            fourth = validator.verify(TEST_PIN, "s1")
        self.assertEqual((fourth.result, fourth.sessionFailures, fourth.remaining, fourth.locked), ("WRONG", 3, 0, False))

    def test_sesion_agotada_no_mueve_contadores(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for _ in range(3):
            validator.verify("9999", "s1")
        global_before = validator._global_failures
        validator.verify(TEST_PIN, "s1")
        validator.verify("9999", "s1")
        self.assertEqual(validator._global_failures, global_before)
        self.assertEqual(validator._session_failures["s1"], 3)

    def test_otra_sesion_sigue_pudiendo_validar(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for _ in range(3):
            validator.verify("9999", "s1")
        ok = validator.verify(TEST_PIN, "s2")
        self.assertEqual(ok.result, "OK")


class Concurrencia(unittest.TestCase):
    def test_20_intentos_fallidos_en_paralelo(self):
        validator = PinValidator(hash_provider=cheap_provider())
        from concurrent.futures import ThreadPoolExecutor

        def attempt(i):
            return validator.verify("9999", f"s{i}")

        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(attempt, range(20)))
        self.assertTrue(all(r.result == "WRONG" for r in results))
        self.assertFalse(any(r.result == "OK" for r in results))
        self.assertEqual(validator._global_failures, 5)
        self.assertTrue(validator._locked)


class FormatoAscii(unittest.TestCase):
    def test_digitos_no_ascii_rechazados(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for bad in ("²³⁴⁵", "١٢٣٤", "１２３４"):
            result = validator.verify(bad, "s1")
            self.assertEqual(result.result, "INVALID_FORMAT", repr(bad))
            self.assertEqual(result.sessionFailures, 0)

    def test_espacios_y_saltos_de_linea_rechazados(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for bad in (" 1234", "1234\n", "1 234", "\t1234"):
            result = validator.verify(bad, "s1")
            self.assertEqual(result.result, "INVALID_FORMAT", repr(bad))


class LimiteDeSesionesEnMemoria(unittest.TestCase):
    def test_sesiones_descartan_la_mas_antigua(self):
        validator = PinValidator(hash_provider=cheap_provider())
        for i in range(1001):
            validator.verify("9999", f"s{i}")
            ok = validator.verify(TEST_PIN, f"aux{i}")
            self.assertEqual(ok.result, "OK")
            self.assertFalse(ok.locked)
        self.assertEqual(len(validator._session_failures), 1000)
        self.assertNotIn("s0", validator._session_failures)
        self.assertNotIn("aux0", validator._session_failures)
        self.assertIn("s1000", validator._session_failures)


class InterfazDelComponente(unittest.TestCase):
    def test_pin_result_tiene_los_cuatro_campos(self):
        result = PinResult(result="WRONG", sessionFailures=1, remaining=2, locked=False)
        self.assertEqual(list(result.__dict__.keys()), ["result", "sessionFailures", "remaining", "locked"])

    def test_verify_pin_y_reset_pin_lock_del_modulo(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop(PIN_HASH_ENV, None)
            try:
                result = verify_pin("1234", "module-test")
                self.assertNotEqual(result.result, "OK")
                reset_pin_lock()
            finally:
                os.environ.pop(PIN_HASH_ENV, None)