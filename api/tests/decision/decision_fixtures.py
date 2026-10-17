"""Helpers para armar `context` de prueba (uno por requisito del spec).

Montos quote reales de los mocks de Pagos (rama origin/payments/openapi-mocks,
openapi/contract-a.yaml):
  dentro del presupuesto: debit 2015000 / receive 2000000, COP escala 2, exceedsRemaining false
  con exceso:             debit 30150000 / receive 30000000, exceedsRemaining true
  pago en proceso:        paymentId p_789, status PROCESSING
"""
from decision.models import (
    Amount,
    Contact,
    Context,
    EngineConfig,
    Intent,
    PendingPayment,
    Phase,
    PinContext,
    Quote,
    Resolution,
    Reply,
    Voice,
)

NOW = "2026-10-17T10:00:00+00:00"
CREATED_WITHIN_WINDOW = "2026-10-17T09:59:00+00:00"  # 60 s antes de NOW (<= 120 s)
CREATED_AT_WINDOW_EDGE = "2026-10-17T09:58:00+00:00"  # exactamente 120 s (<= 120 s: regla 6)
CREATED_PAST_WINDOW = "2026-10-17T09:57:00+00:00"  # 180 s antes de NOW (> 120 s)
PAYMENT_ID_MOCK = "p_789"  # no entra al Context; trazabilidad del fixture

QUOTE_WITHIN_BUDGET = Quote(
    debitAmount=Amount("2015000", "COP", 2),
    receiveAmount=Amount("2000000", "COP", 2),
    exceedsRemaining=False,
)
QUOTE_EXCEEDS_BUDGET = Quote(
    debitAmount=Amount("30150000", "COP", 2),
    receiveAmount=Amount("30000000", "COP", 2),
    exceedsRemaining=True,
)

LAURA = Contact(
    alias="laura-hija",
    name="Laura",
    walletAddress="laura@wallet.example",
    previouslyPaid=True,
)
LUCIA = Contact(
    alias="lucia-vecina",
    name="Lucía",
    walletAddress="lucia@wallet.example",
    previouslyPaid=False,
)

TWENTY_THOUSAND_COP = Amount("2000000", "COP", 2)
FIFTY_THOUSAND_COP = Amount("5000000", "COP", 2)


# Literales JSON idénticos a los to_dict() de Voz (rama origin/voz/h1-parser,
# api/voice/intents.py, api/voice/contacts.py y api/tests/voice/test_context_shapes.py).
# Se usan en tests/decision/test_context_io.py; el paquete voice no se importa.
INTENT_D = {"action": "PAY", "amount": {"value": "2000000", "assetCode": "COP", "assetScale": 2},
            "amountError": None, "recipient": "mi hija", "status": "OK"}  # "Envíale veinte mil a mi hija"
INTENT_SIN_MONTO_UNCLEAR = {"action": "PAY", "amount": None, "amountError": None,
                            "recipient": "mi hija", "status": "UNCLEAR"}  # "Envíale plata a mi hija"
INTENT_SIN_MONTO_OK = {"action": "PAY", "amount": None, "amountError": None,
                       "recipient": "mi hija", "status": "OK"}
INTENT_SIN_PREPOSICION = {"action": "PAY", "amount": {"value": "2000000", "assetCode": "COP", "assetScale": 2},
                          "amountError": None, "recipient": None, "status": "UNCLEAR"}  # "Envíale veinte mil"
INTENT_SIN_PREPOSICION_OK = {"action": "PAY", "amount": {"value": "2000000", "assetCode": "COP", "assetScale": 2},
                             "amountError": None, "recipient": None, "status": "OK"}
INTENT_ERROR_MONTO = {"action": "PAY", "amount": None, "amountError": "TOO_MANY_DECIMALS",
                      "recipient": "Laura", "status": "UNCLEAR"}  # "Envíale 10,505 a Laura"
INTENT_DOS_MONTOS = {"action": "PAY", "amount": None, "amountError": None,
                     "recipient": "Laura", "status": "AMBIGUOUS"}  # "veinte mil y treinta mil a Laura"
INTENT_DOS_DESTINATARIOS = {"action": "PAY", "amount": {"value": "2000000", "assetCode": "COP", "assetScale": 2},
                            "amountError": None, "recipient": None, "status": "AMBIGUOUS"}
INTENT_HOLA = {"action": "UNKNOWN", "amount": None, "amountError": None, "recipient": None, "status": "OK"}
INTENT_CANCELAR = {"action": "CANCEL", "amount": None, "amountError": None, "recipient": None, "status": "OK"}
INTENT_FUERA_DE_GRAMATICA = {"action": "UNKNOWN", "amount": None, "amountError": None,
                             "recipient": None, "status": "UNCLEAR"}  # texto vacío o None

RESOLUTION_RESOLVED_LADELA = {"kind": "RESOLVED", "contact": {"alias": "mi-hija", "name": "Laura hija",
                              "walletAddress": "https://ilp.interledger-test.dev/ezpay-placeholder-laura-hija",
                              "previouslyPaid": True}}
RESOLUTION_CHOICE_LADELA = {"kind": "CHOICE", "options": [{"alias": "mi-hija", "name": "Laura hija"},
                            {"alias": "laura-vecina", "name": "Laura vecina"}]}  # destinatario dicho: "Laura"
RESOLUTION_NOT_FOUND = {"kind": "NOT_FOUND"}  # destinatario dicho: "Pedro"

AMOUNT_TWENTY_THOUSAND = {"value": "2000000", "assetCode": "COP", "assetScale": 2}
AMOUNT_THIRTY_MILLION = {"value": "30000000", "assetCode": "COP", "assetScale": 2}
AMOUNT_DEBIT_EXCESS = {"value": "30150000", "assetCode": "COP", "assetScale": 2}
AMOUNT_DEBIT_WITHIN = {"value": "2015000", "assetCode": "COP", "assetScale": 2}


def config(**overrides):
    values = {
        "highAmountThreshold": None,
        "pendingWindowSeconds": 120,
        "minIntentConfidence": None,
        "minTranscriptConfidence": None,
    }
    values.update(overrides)
    return EngineConfig(**values)


def intent(**overrides):
    values = {
        "action": "PAY",
        "amount": TWENTY_THOUSAND_COP,
        "amountError": None,
        "recipient": "Laura",
        "status": "OK",
    }
    values.update(overrides)
    return Intent(**values)


def resolution_resolved(contact=LAURA):
    return Resolution(kind="RESOLVED", contact=contact)


def resolution_choice(*names):
    from decision.models import AgendaOption

    return Resolution(
        kind="CHOICE",
        options=tuple(AgendaOption(alias=name.lower(), name=name) for name in names),
    )


def pending_payment(createdAt=CREATED_WITHIN_WINDOW, status="PROCESSING", recipient=LAURA.walletAddress):
    return PendingPayment(recipient=recipient, createdAt=createdAt, status=status)


def command_context(**overrides):
    values = {
        "phase": Phase.COMMAND,
        "intent": intent(),
        "resolution": resolution_resolved(),
        "voice": Voice(status="NOT_AVAILABLE", score=None),
        "enrolled": False,
        "hasBudgetGrant": True,
        "quote": QUOTE_WITHIN_BUDGET,
        "pendingPayment": None,
        "now": NOW,
        "reply": None,
        "unclearReplies": 0,
        "pin": PinContext(result=None, sessionFailures=0, locked=False),
        "transcriptConfidence": None,
        "intentConfidence": None,
        "config": config(),
    }
    values.update(overrides)
    return Context(**values)


def pin_context(**overrides):
    values = {
        "phase": Phase.PIN,
        "intent": intent(),
        "resolution": resolution_resolved(),
        "voice": Voice(status="NOT_AVAILABLE", score=None),
        "enrolled": False,
        "hasBudgetGrant": True,
        "quote": QUOTE_WITHIN_BUDGET,
        "pendingPayment": None,
        "now": NOW,
        "reply": None,
        "unclearReplies": 0,
        "pin": PinContext(result="OK", sessionFailures=0, locked=False),
        "transcriptConfidence": None,
        "intentConfidence": None,
        "config": config(),
    }
    values.update(overrides)
    return Context(**values)


def confirmation_context(**overrides):
    values = {
        "phase": Phase.CONFIRMATION,
        "intent": intent(),
        "resolution": resolution_resolved(),
        "voice": Voice(status="VERIFIED", score=0.8),
        "enrolled": True,
        "hasBudgetGrant": True,
        "quote": QUOTE_WITHIN_BUDGET,
        "pendingPayment": None,
        "now": NOW,
        "reply": Reply.YES,
        "unclearReplies": 0,
        "pin": PinContext(result=None, sessionFailures=0, locked=False),
        "transcriptConfidence": None,
        "intentConfidence": None,
        "config": config(),
    }
    values.update(overrides)
    return Context(**values)