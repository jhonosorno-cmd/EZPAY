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
    (S.PIN_KEYBOARD, "Escribe tu PIN en el teclado."),
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
    assert say(S.COMPLETED, amount=A20, name="Laura") == "Listo, le envié 20.000 pesos a Laura."
    assert say(S.COMPLETED, amount=A20, name="Laura", debit=A20) == "Listo, le envié 20.000 pesos a Laura."
    assert say(S.COMPLETED, amount=A20, name="Laura", debit=Amount("2015000", "COP", 2)) == (
        "Listo, le envié 20.000 pesos a Laura. Te costó 20.150 pesos.")


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
    }
    for situation in Situation:
        text = say(situation, **samples.get(situation, {}))
        assert text and "{" not in text and "}" not in text
