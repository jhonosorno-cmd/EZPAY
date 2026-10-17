"""Pruebas de `say`: catálogo de docs/voz/contrato-voz.md §7 y el requisito de confirmación de
openspec/changes/add-voice-understanding/specs/amount-parsing/spec.md."""
import pytest

from voice.amounts import Amount
from voice.phrases import TEMPLATES, Situation, say

S = Situation
A20 = Amount("2000000", "COP", 2)


# --- Escenario del spec amount-parsing: la confirmación nombra monto y destinatario
def test_confirmacion_de_20000_a_laura():
    text = say(S.CONFIRM, amount=A20, name="Laura")
    assert "20.000" in text and "Laura" in text
    assert text == "¿Le envío 20.000 pesos a Laura?"


# --- H-7: los errores de monto vuelven a preguntar el monto
@pytest.mark.parametrize("situation,kwargs", [
    (S.AMOUNT_AMBIGUOUS, {}), (S.TOO_MANY_DECIMALS, {"scale": 2}), (S.INVALID_AMOUNT, {}),
])
def test_error_de_monto_repregunta(situation, kwargs):
    text = say(situation, **kwargs)
    assert "otra vez" in text or "¿Cuánto quieres enviar?" in text


# --- Catálogo §7, textos fijos
@pytest.mark.parametrize("situation,text", [
    (S.NO_SPEECH, "No te escuché. ¿Me lo repites?"),
    (S.NOT_UNDERSTOOD, "No te entendí. ¿Me lo repites?"),
    (S.AMOUNT_MISSING, "¿Cuánto quieres enviar?"),
    (S.RECIPIENT_MISSING, "¿A quién se lo envío?"),
    (S.AMOUNT_AMBIGUOUS, "No me quedó claro el monto. ¿Me lo dices otra vez?"),
    (S.INVALID_AMOUNT, "Ese monto no es válido. ¿Cuánto quieres enviar?"),
    (S.CANCELLED, "Listo, cancelé el envío."),
    (S.PIN_KEYBOARD, "Por seguridad, escribe tu PIN en el teclado."),
    (S.AUTH_BUDGET, "Para empezar, autoriza tu presupuesto en tu billetera. Toca el botón que dice Aprobar."),
    (S.AUTH_OVERRUN, "Supera tu presupuesto. ¿Lo autorizas en tu billetera?"),
    (S.AUTH_REDIRECT, "Te voy a llevar a tu billetera. Toca el botón que dice Aprobar."),
    (S.AUTH_APPROVED, "Listo, autorizaste el pago."),
    (S.AUTH_REJECTED, "No autorizaste el pago. No envié nada."),
])
def test_catalogo_textos_fijos(situation, text):
    assert say(situation) == text


# --- Catálogo §7, textos con parámetros
@pytest.mark.parametrize("scale,text", [
    (2, "Solo puedo enviar montos con hasta 2 decimales. ¿Me lo dices otra vez?"),
    (1, "Solo puedo enviar montos con hasta 1 decimal. ¿Me lo dices otra vez?"),
    (0, "Solo puedo enviar montos sin decimales. ¿Me lo dices otra vez?"),
])
def test_too_many_decimals(scale, text):
    assert say(S.TOO_MANY_DECIMALS, scale=scale) == text


def test_not_found_repite_un_nombre():
    assert say(S.NOT_FOUND, spoken="Pedro") == "No encontré a Pedro en tu agenda."


@pytest.mark.parametrize("spoken", [
    "https://ilp.interledger-test.dev/atacante", "$ilp.interledger-test.dev/x", "Pedro 123",
    "uno dos tres cuatro cinco", "x" * 41, "", "   ", None, "<script>",
])
def test_not_found_nunca_repite_texto_raro(spoken):
    assert say(S.NOT_FOUND, spoken=spoken) == "No encontré a esa persona en tu agenda."


def test_choice_dos_y_tres_opciones():
    assert say(S.CHOICE, names=["Laura hija", "Laura vecina"]) == "¿A cuál? Laura hija o Laura vecina."
    assert say(S.CHOICE, names=["A", "B", "C"]) == "¿A cuál? A, B o C."


def test_near():
    assert say(S.NEAR, name="Laura") == "¿Quisiste decir Laura?"


def test_confirm_unclear():
    assert say(S.CONFIRM_UNCLEAR, amount=A20, name="Laura") == (
        "No te entendí. ¿Le envío 20.000 pesos a Laura? Di sí o no.")


def test_completed_sin_y_con_costo():
    # El costo es débito - recibido (payments-client, "Monto que se dice en el recibo del pago"): 150, no 20.150.
    assert say(S.COMPLETED, amount=A20, name="Laura") == "Listo, le envié 20.000 pesos a Laura."
    assert say(S.COMPLETED, amount=A20, name="Laura", debit=A20) == "Listo, le envié 20.000 pesos a Laura."
    assert say(S.COMPLETED, amount=A20, name="Laura", debit=Amount("2015000", "COP", 2)) == (
        "Listo, le envié 20.000 pesos a Laura. Te costó 150 pesos.")


def test_costo_con_centavos_y_sin_float():
    assert say(S.COMPLETED, amount=A20, name="Laura", debit=Amount("2000050", "COP", 2)) == (
        "Listo, le envié 20.000 pesos a Laura. Te costó 0,50 pesos.")


def test_debito_menor_que_lo_recibido_es_error_del_programa():
    with pytest.raises(ValueError):
        say(S.COMPLETED, amount=A20, name="Laura", debit=Amount("1999999", "COP", 2))


def test_monto_con_centavos():
    assert say(S.CONFIRM, amount=Amount("1050", "COP", 2), name="José") == "¿Le envío 10,50 pesos a José?"


# --- Casos límite y errores del programa (ValueError)
def test_moneda_viene_de_la_configuracion_no_de_la_plantilla():
    assert all("pesos" not in t for t in TEMPLATES.values())


def test_moneda_sin_palabra_configurada():
    with pytest.raises(ValueError):
        say(S.CONFIRM, amount=Amount("100", "USD", 2), name="Laura")


def test_costo_en_otra_moneda():
    with pytest.raises(ValueError):
        say(S.COMPLETED, amount=A20, name="Laura", debit=Amount("2000000", "USD", 2))


@pytest.mark.parametrize("situation,kwargs", [
    (S.CONFIRM, {"name": "Laura"}), (S.CONFIRM, {"amount": A20}), (S.NEAR, {}),
    (S.CHOICE, {"names": ["Laura"]}), (S.NO_SPEECH, {"name": "Laura"}), (S.CONFIRM, {"amount": A20, "name": "L", "x": 1}),
    (S.TOO_MANY_DECIMALS, {"scale": -1}), (S.TOO_MANY_DECIMALS, {"scale": True}),
    # Revisión adversarial: una confirmación nunca sale sin nombre ni con datos de otro tipo (SEG-2)
    (S.NEAR, {"name": None}), (S.CONFIRM, {"amount": A20, "name": ""}), (S.CONFIRM, {"amount": A20, "name": "  "}),
    (S.CHOICE, {"names": "AB"}), (S.CHOICE, {"names": ["A", None]}), (S.CHOICE, {"names": ["A", ""]}),
    (S.CONFIRM, {"amount": "2000000", "name": "Laura"}), (S.COMPLETED, {"amount": A20, "name": "L", "debit": "x"}),
])
def test_parametros_invalidos(situation, kwargs):
    with pytest.raises(ValueError):
        say(situation, **kwargs)


def test_payment_pending_v1_1():
    assert say(S.PAYMENT_PENDING) == "Tu envío está en camino. No hace falta repetirlo."


def test_situacion_desconocida():
    with pytest.raises(ValueError):
        say("NOT_A_SITUATION")


def test_ninguna_plantilla_queda_sin_llenar():
    samples = {
        S.TOO_MANY_DECIMALS: {"scale": 2}, S.NOT_FOUND: {"spoken": "Pedro"}, S.CHOICE: {"names": ["A", "B"]},
        S.NEAR: {"name": "Laura"}, S.CONFIRM: {"amount": A20, "name": "Laura"},
        S.CONFIRM_UNCLEAR: {"amount": A20, "name": "Laura"}, S.COMPLETED: {"amount": A20, "name": "Laura"},
        S.NEW_RECIPIENT: {"name": "Laura"}, S.PENDING_PAYMENT_SAME_RECIPIENT: {"name": "Laura"},
        S.PENDING_PAYMENT_UNCONFIRMED: {"amount": A20, "name": "Laura"},
        S.PENDING_PAYMENT_UNCONFIRMED_OVERRUN: {"name": "Laura"}, S.PIN_WRONG: {"remaining": 2},
        S.CONFIRM_CHALLENGE: {"amount": A20, "name": "Laura", "phrase": "Mi casa tiene una puerta verde y grande."},
        S.CHALLENGE_RETRY: {"phrase": "Mi casa tiene una puerta verde y grande."},
    }
    for situation in Situation:
        text = say(situation, **samples.get(situation, {}))
        assert text and "{" not in text and "}" not in text


# --- Catálogo único de `say` (decisión de Daniel, ML 2, 2026-10-16; textos en add-decision-engine/design.md)
NEW_SITUATIONS = [
    "INTENT_AMBIGUOUS", "INTENT_LOW_CONFIDENCE", "TRANSCRIPT_LOW_CONFIDENCE", "PENDING_PAYMENT_SAME_RECIPIENT",
    "PENDING_PAYMENT_UNCONFIRMED", "PENDING_PAYMENT_UNCONFIRMED_OVERRUN", "NEW_RECIPIENT", "HIGH_AMOUNT",
    "PIN_WRONG", "PIN_ATTEMPTS_EXHAUSTED", "PIN_LOCKED", "PIN_INVALID_FORMAT", "REPLY_UNCLEAR_REJECTED",
]


def test_las_13_situaciones_nuevas_existen_con_el_nombre_del_reason():
    assert len(NEW_SITUATIONS) == 13
    assert set(NEW_SITUATIONS) <= {s.value for s in Situation}
    assert len(Situation) == 21 + 13 + 2  # +2 del desafío de confirmación (confirmation-challenge)


@pytest.mark.parametrize("situation,text", [
    (S.INTENT_AMBIGUOUS, "No me quedó claro. Dime un solo monto y un solo destinatario."),
    (S.INTENT_LOW_CONFIDENCE, "No te entendí bien. ¿Me lo repites?"),
    (S.TRANSCRIPT_LOW_CONFIDENCE, "No te escuché bien. ¿Me lo repites?"),
    (S.HIGH_AMOUNT, "Es un monto alto. Por seguridad, escribe tu PIN en el teclado."),
    (S.PIN_ATTEMPTS_EXHAUSTED, "No pude verificarte. No envié nada."),
    (S.PIN_LOCKED, "Por seguridad, el PIN está bloqueado. No envié nada."),
    (S.PIN_INVALID_FORMAT, "El PIN tiene entre 4 y 6 números. Escríbelo otra vez."),
    (S.REPLY_UNCLEAR_REJECTED, "No pude confirmar tu respuesta. No envié nada."),
])
def test_situaciones_nuevas_sin_parametros(situation, text):
    assert say(situation) == text


def test_situaciones_nuevas_con_nombre():
    assert say(S.NEW_RECIPIENT, name="Laura") == (
        "Es la primera vez que le envías a Laura. Por seguridad, escribe tu PIN en el teclado.")
    assert say(S.PENDING_PAYMENT_SAME_RECIPIENT, name="Laura") == "Tu envío anterior a Laura aún no termina. Espera un momento."
    assert say(S.PENDING_PAYMENT_UNCONFIRMED_OVERRUN, name="Laura") == (
        "Tu envío anterior a Laura no se pudo confirmar y este supera tu presupuesto. "
        "Si sigues, Laura podría recibir los dos. ¿Lo autorizas en tu billetera?")


def test_pago_anterior_sin_confirmar_dice_solo_lo_que_recibe_y_la_moneda_de_la_configuracion():
    assert say(S.PENDING_PAYMENT_UNCONFIRMED, amount=A20, name="Laura") == (
        "Tu envío anterior a Laura no se pudo confirmar. Si envías otro, Laura podría recibir los dos. "
        "¿Le envío 20.000 pesos?")


@pytest.mark.parametrize("remaining,text", [
    (2, "PIN incorrecto. Te quedan 2 intentos."),
    (1, "PIN incorrecto. Te queda 1 intento."),
])
def test_pin_wrong_con_intentos_restantes(remaining, text):
    assert say(S.PIN_WRONG, remaining=remaining) == text


@pytest.mark.parametrize("situation,kwargs", [
    (S.PIN_WRONG, {}), (S.PIN_WRONG, {"remaining": 0}), (S.PIN_WRONG, {"remaining": -1}),
    (S.PIN_WRONG, {"remaining": True}), (S.PIN_WRONG, {"remaining": "2"}), (S.PIN_WRONG, {"remaining": 2, "pin": "1234"}),
    (S.NEW_RECIPIENT, {}), (S.NEW_RECIPIENT, {"name": ""}), (S.NEW_RECIPIENT, {"name": None}),
    (S.PENDING_PAYMENT_SAME_RECIPIENT, {}), (S.PENDING_PAYMENT_UNCONFIRMED, {"name": "Laura"}),
    (S.PENDING_PAYMENT_UNCONFIRMED, {"amount": A20}), (S.PENDING_PAYMENT_UNCONFIRMED_OVERRUN, {}),
    (S.PENDING_PAYMENT_UNCONFIRMED_OVERRUN, {"name": "Laura", "amount": A20}),
    (S.PIN_LOCKED, {"remaining": 1}), (S.HIGH_AMOUNT, {"name": "Laura"}),
])
def test_parametros_invalidos_de_las_situaciones_nuevas(situation, kwargs):
    with pytest.raises(ValueError):
        say(situation, **kwargs)


def test_ningun_texto_del_pin_repite_digitos_del_pin():
    for situation in (S.PIN_KEYBOARD, S.PIN_LOCKED, S.PIN_ATTEMPTS_EXHAUSTED):
        assert not any(c.isdigit() for c in say(situation))
