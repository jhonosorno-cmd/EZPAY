"""B13 — Fachada de ML 2 para el orquestador (H3).

Spec: openspec/changes/add-ml2-integration/specs/voice-turn-integration/spec.md.
Pruebas primero: dobles sin modelo (verificador, decoder, enrolamiento), audio
sintético, nada de voces reales ni archivos de recordings/ o test_data/. Los
logs de la fachada son fijos: ninguna prueba espera ver transcript, frase o
puntaje en ellos (PRIV).
"""
import random
import sys
import threading
import time
import unittest
from pathlib import Path

import numpy as np

import integration
from integration import (choose_confirmation_mode, command_say_context,
                         build_confirmation, enroll_from_uploads,
                         enrollment_status, init, next_challenge_phrase,
                         voice_of, verify_and_transcribe)
from speaker.enrollment import EnrollmentError
from voice.transcribe import TranscribeErrorCode, TranscribeInputError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "decision"))
from decision_fixtures import (AMOUNT_DEBIT_EXCESS, AMOUNT_DEBIT_WITHIN,  # noqa: E402
                               AMOUNT_TWENTY_THOUSAND, INTENT_D, NOW,
                               RESOLUTION_RESOLVED_LADELA)
from decision import decide, parse_context, say_situation  # noqa: E402

FRASE = "El café colombiano huele muy rico."
TRANSCRIPT_OK = "el cafe colombiano huele muy rico"
TRANSCRIPT_MALA = "otra cosa completamente distinta"
PUNTAJE_DOBLE = 0.7001  # valor sintético inconfundible para la prueba de privacidad


class VerificadorDoble:
    """verify(pcm, user) como SpeakerVerifier, sin modelo."""

    def __init__(self, status="VERIFIED", score=PUNTAJE_DOBLE, retardo=0.0,
                 lanza=False, usuario_valido="usuario"):
        self.status = status
        self.score = score
        self.retardo = retardo
        self.lanza = lanza
        self.usuario_valido = usuario_valido
        self.llamadas = []

    def verify(self, pcm, user):
        self.llamadas.append(user)
        if self.retardo:
            time.sleep(self.retardo)
        if self.lanza:
            raise RuntimeError("fallo del doble")
        if user != self.usuario_valido:
            return {"status": "NOT_AVAILABLE", "score": None}
        return {"status": self.status, "score": self.score}


class DecodificadorDoble:
    """decode(bytes) como AvDecoder, sin ffmpeg: PCM sintético salvo audio marcado."""

    def __init__(self):
        self.llamadas = []

    def decode(self, audio):
        self.llamadas.append(audio)
        if audio == b"roto":
            raise TranscribeInputError(TranscribeErrorCode.INVALID_AUDIO, "audio not decodable")
        return np.zeros(int(16000 * 3.0), dtype="float32")


class EnrolamientoDoble:
    """enroll/status como SpeakerEnrollment, sin modelo ni disco."""

    def __init__(self, error=None, estado=True):
        self.error = error
        self.estado = estado
        self.llamadas = []

    def enroll(self, samples, consent):
        self.llamadas.append((samples, consent))
        if self.error:
            raise EnrollmentError(self.error)
        return {"enrolled": True}

    def status(self):
        return {"enrolled": self.estado}


def fachada(verificador=None, decoder=None, enrolamiento=None, banco=None, timeout=2.0):
    init(verifier=verificador if verificador is not None else VerificadorDoble(),
         enrollment=enrolamiento if enrolamiento is not None else EnrolamientoDoble(),
         decoder=decoder if decoder is not None else DecodificadorDoble(),
         bank=banco if banco is not None else [FRASE, "El gato duerme tranquilo junto a la ventana."],
         timeout_s=timeout)


def esperar_libre(test, limite=4.0):
    """Espera a que la verificación vencida (que NO se cancela) suelte la fachada."""
    t0 = time.perf_counter()
    while not integration._estados["candado"].acquire(timeout=0.05):
        if time.perf_counter() - t0 > limite:
            test.fail("la verificación vencida nunca soltó la fachada")
    integration._estados["candado"].release()


def contexto_dict(**overrides):
    """Context de COMMAND (camelCase, literales JSON de decision_fixtures) que da
    ASK_CONFIRM/ALL_CHECKS_PASSED con voz VERIFIED."""
    datos = {
        "phase": "COMMAND",
        "intent": dict(INTENT_D),
        "resolution": dict(RESOLUTION_RESOLVED_LADELA),
        "voice": {"status": "VERIFIED", "score": 0.8},
        "enrolled": True,
        "hasBudgetGrant": True,
        "quote": {"debitAmount": dict(AMOUNT_DEBIT_WITHIN),
                  "receiveAmount": dict(AMOUNT_TWENTY_THOUSAND),
                  "exceedsRemaining": False},
        "pendingPayment": None,
        "now": NOW,
        "reply": None,
        "unclearReplies": 0,
        "pin": {"result": None, "sessionFailures": 0, "locked": False},
        "transcriptConfidence": None,
        "intentConfidence": None,
        "config": {"highAmountThreshold": None, "pendingWindowSeconds": 120,
                   "minIntentConfidence": None, "minTranscriptConfidence": None,
                   "confirmationChallenge": True, "challengePhraseMatchMin": 0.8},
        "confirmation": None,
    }
    datos.update(overrides)
    return datos


def contexto_dict_exceso(**overrides):
    """El mismo context, con la quote que excede el presupuesto (AUTH_OVERRUN)."""
    datos = contexto_dict(**overrides)
    datos["quote"] = {"debitAmount": dict(AMOUNT_DEBIT_EXCESS),
                      "receiveAmount": dict(AMOUNT_TWENTY_THOUSAND),
                      "exceedsRemaining": True}
    return datos


def contexto_confirmation(confirmation, **overrides):
    datos = contexto_dict(**overrides)
    datos["phase"] = "CONFIRMATION"
    datos["reply"] = "YES"
    datos["confirmation"] = confirmation
    return datos


class BaseIntegration(unittest.TestCase):
    def tearDown(self):
        integration._reiniciar()
        self.addCleanup(esperar_libre, self)


class TestVoiceDelComando(BaseIntegration):
    def test_comando_verificado_da_status_y_score_exactos(self):
        verificador = VerificadorDoble()
        fachada(verificador=verificador)
        voz = voice_of(b"audio del comando", user="usuario")
        self.assertEqual({"status", "score"}, set(voz))
        self.assertEqual("VERIFIED", voz["status"])
        self.assertAlmostEqual(PUNTAJE_DOBLE, voz["score"])
        self.assertEqual(["usuario"], verificador.llamadas)

    def test_below_threshold_y_not_available_con_el_doble(self):
        fachada(verificador=VerificadorDoble(status="BELOW_THRESHOLD", score=0.2))
        self.assertEqual("BELOW_THRESHOLD", voice_of(b"audio")["status"])
        fachada(verificador=VerificadorDoble(usuario_valido="otro"))
        self.assertEqual({"status": "NOT_AVAILABLE", "score": None}, voice_of(b"audio", user="nadie"))

    def test_excepcion_del_doble_y_del_decoder_dan_not_available(self):
        fachada(verificador=VerificadorDoble(lanza=True))
        self.assertEqual({"status": "NOT_AVAILABLE", "score": None}, voice_of(b"audio"))
        fachada()
        self.assertEqual({"status": "NOT_AVAILABLE", "score": None}, voice_of(b"roto"))

    def test_fachada_sin_cargar_da_not_available(self):
        integration._reiniciar()
        self.assertEqual({"status": "NOT_AVAILABLE", "score": None}, voice_of(b"audio"))
        self.assertEqual((500, {"error": {"code": "INTERNAL_ERROR", "message": "INTERNAL_ERROR"}}),
                         enroll_from_uploads([b"a", b"b", b"c"], True))
        self.assertFalse(integration.is_enrolled())

    def test_timeout_y_fachada_ocupada(self):
        fachada(verificador=VerificadorDoble(retardo=0.6), timeout=0.2)
        t0 = time.perf_counter()
        self.assertEqual({"status": "NOT_AVAILABLE", "score": None}, voice_of(b"audio"))
        self.assertLess(time.perf_counter() - t0, 0.5)
        t1 = time.perf_counter()
        self.assertEqual({"status": "NOT_AVAILABLE", "score": None}, voice_of(b"audio"))
        self.assertLess(time.perf_counter() - t1, 0.15)
        esperar_libre(self)

    def test_paralelo_tarda_lo_que_la_mas_lenta(self):
        fachada(verificador=VerificadorDoble(retardo=0.3))
        def transcribir():
            time.sleep(0.5)
            return "texto"
        t0 = time.perf_counter()
        voz, texto = verify_and_transcribe(b"audio", transcribir)
        total = time.perf_counter() - t0
        self.assertEqual("VERIFIED", voz["status"])
        self.assertEqual("texto", texto)
        self.assertGreater(total, 0.4)
        self.assertLess(total, 0.8)

    def test_la_transcripcion_propaga_su_excepcion(self):
        fachada()
        def transcribir():
            raise RuntimeError("error del contrato de Voz")
        with self.assertRaises(RuntimeError):
            verify_and_transcribe(b"audio", transcribir)


class TestEleccionModoYFrase(unittest.TestCase):
    def test_solo_la_combinacion_completa_da_challenge(self):
        for activa, fase, decision, voz, esperado in [
            (True, "COMMAND", "ASK_CONFIRM", "VERIFIED", "CHALLENGE"),
            (True, "COMMAND", "ASK_CONFIRM", "NOT_AVAILABLE", "REPLY"),
            (True, "COMMAND", "ASK_CONFIRM", "BELOW_THRESHOLD", "REPLY"),
            (True, "COMMAND", "ASK_CONFIRM", None, "REPLY"),
            (True, "COMMAND", "PAY", "VERIFIED", "REPLY"),
            (True, "PIN", "ASK_CONFIRM", "VERIFIED", "REPLY"),
            (False, "COMMAND", "ASK_CONFIRM", "VERIFIED", "REPLY"),
        ]:
            self.assertEqual(esperado, choose_confirmation_mode(activa, fase, decision, voz))

    def test_next_challenge_phrase_sin_repetir_y_sin_mutar(self):
        fachada(banco=[FRASE, "El gato duerme tranquilo junto a la ventana.", "La luna brilla sobre el techo."])
        usadas = [FRASE]
        frase, usadas_nuevas = next_challenge_phrase(usadas, last=FRASE)
        self.assertIn(frase, ["El gato duerme tranquilo junto a la ventana.", "La luna brilla sobre el techo."])
        self.assertEqual([FRASE], usadas)
        self.assertEqual([FRASE, frase], usadas_nuevas)

    def test_next_challenge_phrase_es_determinista_con_semilla(self):
        banco = [f"frase numero {i} de prueba" for i in range(8)]
        fachada(banco=banco)
        a, _ = next_challenge_phrase([], rng=random.Random(7))
        b, _ = next_challenge_phrase([], rng=random.Random(7))
        self.assertEqual(a, b)


class TestBuildConfirmation(unittest.TestCase):
    def test_claves_camelcase_exactas(self):
        datos = build_confirmation("CHALLENGE", transcript=TRANSCRIPT_OK, expected_phrase=FRASE,
                                   voice={"status": "VERIFIED", "score": 0.7}, challenge_attempts=1)
        self.assertEqual({"mode", "phraseScore", "voice", "challengeAttempts"}, set(datos))
        self.assertEqual("CHALLENGE", datos["mode"])
        self.assertEqual(1.0, datos["phraseScore"])
        self.assertEqual({"status": "VERIFIED", "score": 0.7}, datos["voice"])
        self.assertEqual(1, datos["challengeAttempts"])

    def test_phrase_score_un_error_en_ocho_palabras(self):
        datos = build_confirmation("CHALLENGE", transcript="mi casa tiene una puerta verde y",
                                   expected_phrase="Mi casa tiene una puerta verde y grande.", voice=None,
                                   challenge_attempts=0)
        self.assertEqual(0.875, datos["phraseScore"])

    def test_transcript_vacio_da_cero_y_none_da_null(self):
        vacio = build_confirmation("CHALLENGE", transcript="", expected_phrase=FRASE, voice=None,
                                   challenge_attempts=0)
        self.assertEqual(0.0, vacio["phraseScore"])
        sin_voz = build_confirmation("CHALLENGE", transcript=None, expected_phrase=FRASE, voice=None,
                                     challenge_attempts=0)
        self.assertIsNone(sin_voz["phraseScore"])

    def test_reply_no_verifica_nada(self):
        datos = build_confirmation("REPLY", transcript=TRANSCRIPT_OK, expected_phrase=FRASE,
                                   voice={"status": "VERIFIED", "score": 0.7}, challenge_attempts=2)
        self.assertEqual({"mode": "REPLY", "phraseScore": None, "voice": None, "challengeAttempts": 2}, datos)

    def test_entradas_invalidas_lanzan_valueerror_con_mensaje_fijo(self):
        for kwargs in [
            {"mode": "OTRO", "transcript": None, "expected_phrase": None, "voice": None, "challenge_attempts": 0},
            {"mode": "CHALLENGE", "transcript": 5, "expected_phrase": FRASE, "voice": None, "challenge_attempts": 0},
            {"mode": "CHALLENGE", "transcript": TRANSCRIPT_OK, "expected_phrase": None, "voice": None,
             "challenge_attempts": 0},
            {"mode": "CHALLENGE", "transcript": None, "expected_phrase": None, "voice": "VERIFIED",
             "challenge_attempts": 0},
            {"mode": "CHALLENGE", "transcript": None, "expected_phrase": None, "voice": None,
             "challenge_attempts": -1},
        ]:
            with self.assertRaises(ValueError) as cm:
                build_confirmation(**kwargs)
            self.assertNotIn(str(kwargs.get("mode", "")), str(cm.exception))


class TestIdaYVueltaConElMotor(unittest.TestCase):
    def test_frase_y_voz_buenas_dan_pay(self):
        confirmation = build_confirmation("CHALLENGE", transcript=TRANSCRIPT_OK, expected_phrase=FRASE,
                                          voice={"status": "VERIFIED", "score": 0.7}, challenge_attempts=0)
        contexto = parse_context(contexto_confirmation(confirmation))
        resultado = decide(contexto).to_dict()
        self.assertEqual({"decision": "PAY", "reason": "CONFIRMED"}, resultado)

    def test_frase_buena_y_voz_baja_dan_ask_pin(self):
        confirmation = build_confirmation("CHALLENGE", transcript=TRANSCRIPT_OK, expected_phrase=FRASE,
                                          voice={"status": "BELOW_THRESHOLD", "score": 0.3},
                                          challenge_attempts=0)
        resultado = decide(parse_context(contexto_confirmation(confirmation))).to_dict()
        self.assertEqual({"decision": "ASK_PIN", "reason": "CHALLENGE_VOICE_NOT_VERIFIED"}, resultado)

    def test_frase_mala_primer_intento_da_retry(self):
        confirmation = build_confirmation("CHALLENGE", transcript=TRANSCRIPT_MALA, expected_phrase=FRASE,
                                          voice=None, challenge_attempts=0)
        resultado = decide(parse_context(contexto_confirmation(confirmation))).to_dict()
        self.assertEqual({"decision": "ASK_CONFIRM", "reason": "CHALLENGE_RETRY"}, resultado)

    def test_frase_mala_segundo_intento_da_reject(self):
        confirmation = build_confirmation("CHALLENGE", transcript=TRANSCRIPT_MALA, expected_phrase=FRASE,
                                          voice=None, challenge_attempts=1)
        resultado = decide(parse_context(contexto_confirmation(confirmation))).to_dict()
        self.assertEqual({"decision": "REJECT", "reason": "CHALLENGE_FAILED"}, resultado)


class TestCommandSayContext(BaseIntegration):
    def test_challenge_agrega_confirmation_y_reply_no(self):
        original = contexto_dict()
        con_challenge = command_say_context(original, "CHALLENGE")
        self.assertEqual({"mode": "CHALLENGE", "phraseScore": None, "voice": None, "challengeAttempts": 0},
                         con_challenge["confirmation"])
        self.assertIsNone(original["confirmation"])  # copia: el dict recibido no cambia
        con_reply = command_say_context(original, "REPLY")
        self.assertIsNone(con_reply["confirmation"])

    def test_integracion_con_decision_y_say_reales(self):
        original = contexto_dict()
        decision = decide(parse_context(original))
        self.assertEqual("ALL_CHECKS_PASSED", decision.reason.value)
        self.assertEqual("CONFIRM_CHALLENGE",
                         say_situation(decision, parse_context(command_say_context(original, "CHALLENGE"))))
        self.assertEqual("CONFIRM", say_situation(decision, parse_context(command_say_context(original, "REPLY"))))
        con_exceso = contexto_dict_exceso()
        decision_exceso = decide(parse_context(con_exceso))
        self.assertEqual("CONFIRM_CHALLENGE_OVERRUN",
                         say_situation(decision_exceso, parse_context(command_say_context(con_exceso, "CHALLENGE"))))
        self.assertEqual("AUTH_OVERRUN",
                         say_situation(decision_exceso, parse_context(command_say_context(con_exceso, "REPLY"))))


class TestEnrolamientoWeb(BaseIntegration):
    def test_aceptado_guarda_y_devuelve_201(self):
        enrolamiento = EnrolamientoDoble()
        decoder = DecodificadorDoble()
        fachada(enrolamiento=enrolamiento, decoder=decoder)
        self.assertEqual((201, {"enrolled": True}), enroll_from_uploads([b"a", b"b", b"c"], True))
        self.assertEqual(1, len(enrolamiento.llamadas))
        self.assertEqual(3, len(enrolamiento.llamadas[0][0]))
        self.assertIs(True, enrolamiento.llamadas[0][1])

    def test_consent_y_muestras_se_revisan_antes_de_decodificar(self):
        enrolamiento = EnrolamientoDoble()
        decoder = DecodificadorDoble()
        fachada(enrolamiento=enrolamiento, decoder=decoder)
        sin_consent = enroll_from_uploads([b"roto", b"roto", b"roto"], False)
        self.assertEqual((400, {"error": {"code": "CONSENT_REQUIRED", "message": "CONSENT_REQUIRED"}}),
                         sin_consent)
        pocas = enroll_from_uploads([b"a", b"b"], True)
        self.assertEqual((400, {"error": {"code": "SAMPLES_REQUIRED", "message": "SAMPLES_REQUIRED"}}), pocas)
        self.assertEqual([], decoder.llamadas)
        self.assertEqual([], enrolamiento.llamadas)

    def test_audio_ilegible_da_invalid_audio_y_no_llama_a_enroll(self):
        enrolamiento = EnrolamientoDoble()
        fachada(enrolamiento=enrolamiento)
        self.assertEqual((400, {"error": {"code": "INVALID_AUDIO", "message": "INVALID_AUDIO"}}),
                         enroll_from_uploads([b"a", b"roto", b"c"], True))
        self.assertEqual([], enrolamiento.llamadas)

    def test_errores_del_enrolamiento_se_mapean_uno_a_uno(self):
        for codigo in ["INVALID_AUDIO", "INCONSISTENT_SAMPLES"]:
            fachada(enrolamiento=EnrolamientoDoble(error=codigo))
            self.assertEqual((400, {"error": {"code": codigo, "message": codigo}}),
                             enroll_from_uploads([b"a", b"b", b"c"], True))

    def test_status_y_estado_sin_cargar(self):
        fachada(enrolamiento=EnrolamientoDoble(estado=True))
        self.assertEqual((200, {"enrolled": True}), enrollment_status())
        self.assertTrue(integration.is_enrolled())
        integration._reiniciar()
        self.assertEqual((500, {"error": {"code": "INTERNAL_ERROR", "message": "INTERNAL_ERROR"}}),
                         enrollment_status())
        self.assertFalse(integration.is_enrolled())

    def test_fallo_inesperado_del_enrolamiento_es_500(self):
        class EnrolamientoQueFalla:
            def enroll(self, muestras, consent):
                raise RuntimeError("model crashed")

            def status(self):
                raise RuntimeError("disk")

        fachada(enrolamiento=EnrolamientoQueFalla())
        self.assertEqual((500, {"error": {"code": "INTERNAL_ERROR", "message": "INTERNAL_ERROR"}}),
                         enroll_from_uploads([b"a", b"b", b"c"], True))
        self.assertFalse(integration.is_enrolled())


class TestPrivacidad(BaseIntegration):
    def test_los_logs_son_fijos_y_sin_datos(self):
        with self.assertLogs("integration", level="INFO") as logs:
            fachada(verificador=VerificadorDoble(retardo=0.3), timeout=0.05)
            voice_of(b"audio")  # timeout
            integration._reiniciar()
            voice_of(b"audio")  # fachada sin cargar
            fachada(enrolamiento=EnrolamientoDoble(error="INVALID_AUDIO"))
            enroll_from_uploads([b"a", b"roto", b"c"], True)
            esperar_libre(self)
        salida = "\n".join(logs.output)
        self.assertNotIn(FRASE, salida)
        self.assertNotIn(TRANSCRIPT_OK, salida)
        self.assertNotIn(TRANSCRIPT_MALA, salida)
        self.assertNotIn("0.7001", salida)
        self.assertNotIn("0.3001", salida)


if __name__ == "__main__":
    unittest.main()