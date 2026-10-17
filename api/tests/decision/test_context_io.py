"""`decision/context_io.py`: parse_context y decide_dict para el orquestador de Pagos.

Los literales JSON son idénticos a los to_dict() de Voz (rama origin/voz/h1-parser,
api/tests/voice/test_context_shapes.py). El paquete voice NO se importa.
Estricto y fail-closed: cualquier desviación del contrato ⇒ InvalidContextError.
"""
import unittest

from decision import InvalidContextError
from decision.context_io import decide_dict, parse_context
from decision.engine import decide
from decision.models import Decision, DecisionType, Reason
import decision_fixtures as f


def base_payload(**overrides):
    data = {
        "phase": "COMMAND",
        "intent": f.INTENT_D,
        "resolution": f.RESOLUTION_RESOLVED_LADELA,
        "voice": {"status": "NOT_AVAILABLE", "score": None},
        "enrolled": False,
        "hasBudgetGrant": True,
        "quote": {"debitAmount": f.AMOUNT_DEBIT_WITHIN, "receiveAmount": f.AMOUNT_TWENTY_THOUSAND, "exceedsRemaining": False},
        "pendingPayment": None,
        "now": f.NOW,
        "reply": None,
        "unclearReplies": 0,
        "pin": {"result": None, "sessionFailures": 0, "locked": False},
        "transcriptConfidence": None,
        "intentConfidence": None,
        "config": {"highAmountThreshold": None, "pendingWindowSeconds": 120,
                   "minIntentConfidence": None, "minTranscriptConfidence": None},
    }
    data.update(overrides)
    return data


def pin_payload(result="OK", sessionFailures=0, locked=False, **overrides):
    return base_payload(
        phase="PIN",
        pin={"result": result, "sessionFailures": sessionFailures, "locked": locked},
        **overrides,
    )


def confirmation_payload(reply, quote=None, **overrides):
    return base_payload(
        phase="CONFIRMATION",
        reply=reply,
        quote=quote if quote is not None else {"debitAmount": f.AMOUNT_DEBIT_WITHIN, "receiveAmount": f.AMOUNT_TWENTY_THOUSAND, "exceedsRemaining": False},
        **overrides,
    )


class ContextoDeLaDemoPorTexto(unittest.TestCase):
    def test_enviale_veinte_mil_a_mi_hija_pide_pin(self):
        result = decide_dict(base_payload())
        self.assertEqual(result, {"decision": "ASK_PIN", "reason": "VOICE_NOT_VERIFIED"})

    def test_pin_correcto_pide_confirmacion(self):
        result = decide_dict(pin_payload(result="OK"))
        self.assertEqual(result, {"decision": "ASK_CONFIRM", "reason": "PIN_CORRECT"})

    def test_si_paga(self):
        result = decide_dict(confirmation_payload("YES"))
        self.assertEqual(result, {"decision": "PAY", "reason": "CONFIRMED"})

    def test_exceso_va_a_la_wallet_sin_pin_por_monto(self):
        excess = {"debitAmount": f.AMOUNT_DEBIT_EXCESS, "receiveAmount": f.AMOUNT_THIRTY_MILLION, "exceedsRemaining": True}
        verified = {"status": "VERIFIED", "score": 0.9}
        result = decide_dict(base_payload(
            intent={**f.INTENT_D, "amount": f.AMOUNT_THIRTY_MILLION, "recipient": "mi hija"},
            quote=excess,
            voice=verified,
            enrolled=True,
        ))
        self.assertEqual(result, {"decision": "ASK_CONFIRM", "reason": "ALL_CHECKS_PASSED"})
        result = decide_dict(confirmation_payload("YES", quote=excess))
        self.assertEqual(result, {"decision": "REQUIRE_AUTH", "reason": "CONFIRMED_NEEDS_WALLET_AUTH"})


class FrasesRealesDeVoz(unittest.TestCase):
    def payload(self, intent, **overrides):
        return base_payload(intent=intent, **overrides)

    def test_enviale_plata_a_mi_hija_pidio_monto(self):
        self.assertEqual(decide_dict(self.payload(f.INTENT_SIN_MONTO_UNCLEAR)), {"decision": "REASK", "reason": "AMOUNT_MISSING"})

    def test_enviale_veinte_mil_falta_destinatario(self):
        self.assertEqual(decide_dict(self.payload(f.INTENT_SIN_PREPOSICION)), {"decision": "REASK", "reason": "RECIPIENT_MISSING"})

    def test_enviale_10_505_a_laura_error_de_monto(self):
        self.assertEqual(decide_dict(self.payload(f.INTENT_ERROR_MONTO)), {"decision": "REASK", "reason": "AMOUNT_ERROR"})

    def test_dos_montos_dichos(self):
        self.assertEqual(decide_dict(self.payload(f.INTENT_DOS_MONTOS)), {"decision": "REASK", "reason": "INTENT_AMBIGUOUS"})

    def test_dos_destinatarios_dichos(self):
        self.assertEqual(decide_dict(self.payload(f.INTENT_DOS_DESTINATARIOS)), {"decision": "REASK", "reason": "INTENT_AMBIGUOUS"})

    def test_hola(self):
        self.assertEqual(decide_dict(self.payload(f.INTENT_HOLA)), {"decision": "REASK", "reason": "INTENT_UNKNOWN"})

    def test_cancela(self):
        self.assertEqual(decide_dict(self.payload(f.INTENT_CANCELAR)), {"decision": "REJECT", "reason": "CANCELLED_BY_USER"})

    def test_fuera_de_gramatica(self):
        self.assertEqual(decide_dict(self.payload(f.INTENT_FUERA_DE_GRAMATICA)), {"decision": "REASK", "reason": "INTENT_UNKNOWN"})

    def test_pedro_no_esta_en_la_agenda(self):
        self.assertEqual(decide_dict(self.payload(f.INTENT_D, resolution=f.RESOLUTION_NOT_FOUND)), {"decision": "REASK", "reason": "RECIPIENT_NOT_FOUND"})

    def test_laura_es_una_coincidencia_doble(self):
        self.assertEqual(decide_dict(self.payload(f.INTENT_D, resolution=f.RESOLUTION_CHOICE_LADELA)), {"decision": "ASK_RECIPIENT", "reason": "RECIPIENT_AMBIGUOUS"})


class FechasIso8601(unittest.TestCase):
    def test_now_malformado(self):
        for bad in ("garbage", "", "2026-13-45T00:00:00Z", "ayer", "2026-10-17"):
            with self.assertRaises(InvalidContextError):
                parse_context(base_payload(now=bad))

    def test_created_at_malformado(self):
        with self.assertRaises(InvalidContextError):
            parse_context(base_payload(pendingPayment={"recipient": "w", "createdAt": "ayer", "status": "PROCESSING"}))

    def test_el_mensaje_no_contiene_el_valor(self):
        for bad in ("garbage", "ayer"):
            data = base_payload(now=bad)
            with self.assertRaises(InvalidContextError) as caught:
                parse_context(data)
            self.assertNotIn("garbage", str(caught.exception))
            self.assertNotIn("ayer", str(caught.exception))

    def test_formatos_validos_de_hora(self):
        for good in ("2026-10-17T10:00:00Z", "2026-10-17T10:00:00+00:00", "2026-10-17T10:00:00"):
            data = base_payload(now=good)
            self.assertEqual(parse_context(data).now, good)

    def test_created_at_valido_con_z(self):
        data = base_payload(pendingPayment={"recipient": "w", "createdAt": "2026-10-17T09:59:00Z", "status": "PROCESSING"})
        ctx = parse_context(data)
        self.assertEqual(ctx.pendingPayment.createdAt, "2026-10-17T09:59:00Z")

    def test_hora_valida_decide_normal(self):
        data = base_payload(now="2026-10-17T10:00:00Z")
        self.assertEqual(decide_dict(data), {"decision": "ASK_PIN", "reason": "VOICE_NOT_VERIFIED"})


class ParseContextEstricto(unittest.TestCase):
    def test_forma_completa_roundtrip_de_campos(self):
        ctx = parse_context(base_payload())
        self.assertEqual(ctx.phase.value, "COMMAND")
        self.assertEqual(ctx.intent.status.value, "OK")
        self.assertEqual(ctx.resolution.contact.walletAddress, f.RESOLUTION_RESOLVED_LADELA["contact"]["walletAddress"])
        self.assertTrue(ctx.resolution.contact.previouslyPaid)
        self.assertEqual(ctx.quote.receiveAmount.value, "2000000")

    def test_clave_faltante(self):
        data = base_payload()
        del data["now"]
        with self.assertRaises(InvalidContextError):
            parse_context(data)

    def test_clave_desconocida(self):
        data = base_payload()
        data["surprise"] = 1
        with self.assertRaises(InvalidContextError):
            parse_context(data)

    def test_enum_desconocido(self):
        with self.assertRaises(InvalidContextError):
            parse_context(base_payload(intent={**f.INTENT_D, "status": "WHATEVER"}))
        with self.assertRaises(InvalidContextError):
            parse_context(base_payload(voice={"status": "MAYBE", "score": None}))
        with self.assertRaises(InvalidContextError):
            parse_context(pin_payload(result="WHATEVER"))
        with self.assertRaises(InvalidContextError):
            parse_context(base_payload(pendingPayment={"recipient": "w", "createdAt": f.NOW, "status": "LOST"}))

    def test_monto_no_ascii_digitos(self):
        for bad in ("20.5", "١٢٣٤", "²³⁴⁵", "20 000", "-5", ""):
            with self.assertRaises(InvalidContextError):
                parse_context(base_payload(intent={**f.INTENT_D, "amount": {"value": bad, "assetCode": "COP", "assetScale": 2}}))

    def test_resolution_unclear_es_contexto_invalido(self):
        with self.assertRaises(InvalidContextError):
            parse_context(base_payload(resolution={"kind": "UNCLEAR"}))

    def test_tipos_incorrectos(self):
        cases = [
            base_payload(enrolled="yes"),
            base_payload(unclearReplies="0"),
            base_payload(now=1758000000),
            base_payload(quote="not-a-dict"),
            base_payload(pin="not-a-dict"),
            base_payload(intent="not-a-dict"),
            base_payload(intent={**f.INTENT_D, "recipient": 42}),
            pin_payload(sessionFailures="1"),
            pin_payload(locked=1),
            base_payload(transcriptConfidence="0.9"),
            base_payload(config={**base_payload()["config"], "pendingWindowSeconds": "120"}),
        ]
        for data in cases:
            with self.assertRaises(InvalidContextError):
                parse_context(data)

    def test_mensaje_fijo_sin_datos_del_request(self):
        probes = [
            base_payload(intent={**f.INTENT_D, "recipient": "Doña Marta Pérez"}),
            base_payload(intent={**f.INTENT_D, "amount": {"value": "20.5", "assetCode": "COP", "assetScale": 2}}),
            base_payload(resolution={"kind": "UNCLEAR"}),
            base_payload(enrolled="yes"),
        ]
        messages = set()
        for data in probes:
            try:
                parse_context(data)
            except InvalidContextError as exc:
                messages.add(str(exc))
                self.assertNotIn("Doña Marta", str(exc))
                self.assertNotIn("20.5", str(exc))
        self.assertEqual(len(messages), 1)

    def test_parse_y_decide_coinciden_con_dataclasses(self):
        data = base_payload()
        expected = decide(parse_context(data)).to_dict()
        self.assertEqual(decide_dict(data), expected)


class DecisionToDict(unittest.TestCase):
    def test_to_dict_solo_decision_y_reason(self):
        ctx = parse_context(pin_payload(result="OK"))
        d = decide(ctx).to_dict()
        self.assertEqual(list(d.keys()), ["decision", "reason"])
        self.assertEqual(d, {"decision": "ASK_CONFIRM", "reason": "PIN_CORRECT"})

    def test_decision_dataclass_to_dict(self):
        d = Decision(DecisionType.PAY, Reason.CONFIRMED).to_dict()
        self.assertEqual(d, {"decision": "PAY", "reason": "CONFIRMED"})