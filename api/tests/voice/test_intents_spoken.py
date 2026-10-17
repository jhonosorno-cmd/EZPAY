"""Frases naturales de la prueba en la sala con Groq (17 oct): saludos y muletillas antes del verbo,
pedidos corteses, subjuntivo y un "gracias" final. Todas deben dar PAY OK con 20.000 COP a Laura."""
import pytest

from voice.amounts import AssetConfig
from voice.intents import Action, Status, extract_intent

COP = AssetConfig("COP", 2)

SPOKEN = [
    "Hola, envíale 20.000 pesos a Laura.",
    "Hola EZPAY, envíale 20.000 pesos a Laura.",
    "Oye, envíale 20.000 pesos a Laura.",
    "Bueno, mándale 20.000 pesos a Laura.",
    "Ok, envíale 20.000 pesos a Laura.",
    "Sí, envíale 20.000 pesos a Laura.",
    "Buenos días, envíale 20.000 pesos a Laura.",
    "Le quiero enviar 20.000 pesos a Laura.",
    "Necesito que le envíes 20.000 pesos a Laura.",
    "Quiero que le mandes 20.000 pesos a Laura.",
    "Envíale 20.000 pesos a Laura. Gracias.",
    "Envíale 20.000 pesos a Laura. Muchas gracias.",
]


@pytest.mark.parametrize("text", SPOKEN)
def test_natural_spoken_command_is_a_complete_payment(text):
    intent = extract_intent(text, COP)
    assert (intent.action, intent.status, intent.recipient) == (Action.PAY, Status.OK, "laura")
    assert intent.amount.value == "2000000"


@pytest.mark.parametrize("text", ["Hola.", "Hola buenos días.", "Oye.", "Gracias.", "Bueno, ¿cómo estás?",
                                  "¿Puedes enviarle 20.000 pesos a Laura?", "Hola, ¿podrías enviar veinte mil a Laura?"])
def test_greetings_without_a_payment_verb_are_still_unknown(text):
    assert extract_intent(text, COP).action is Action.UNKNOWN


def test_thanks_does_not_hide_a_second_order():
    # dos órdenes de pago siguen siendo UNCLEAR aunque haya un "gracias"
    intent = extract_intent("Envíale 20.000 a Laura. Gracias. Mándale 5.000 a José.", COP)
    assert intent.status is Status.UNCLEAR
