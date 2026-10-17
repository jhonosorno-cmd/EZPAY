"""scripts/salidas.py: arma lo que reciben Pagos, Frontend y ML 2 a partir de un texto ya transcrito."""
import json

from decision.context_io import parse_context
from scripts.salidas import salidas_de_la_respuesta, salidas_del_comando


def test_comando_de_pago_trae_las_salidas_de_cada_rol_y_es_json():
    s = salidas_del_comando(" Envíale 20.000 a Laura hija", had_speech=True, engine="groq")
    json.dumps(s)  # todo serializable
    assert s["transcript"] == {"text": " Envíale 20.000 a Laura hija", "hadSpeech": True, "engine": "groq",
                               "transcriptConfidence": None}
    assert s["intent"]["action"] == "PAY" and s["intent"]["amount"]["value"] == "2000000"
    assert s["resolution"]["kind"] == "RESOLVED" and s["resolution"]["contact"]["name"]
    assert set(s["context"]) >= {"phase", "intent", "resolution", "voice", "quote", "config"}
    parse_context(s["context"])  # ML 2 lo acepta tal cual
    assert s["decision"] == {"decision": "ASK_PIN", "reason": "VOICE_NOT_VERIFIED"}
    assert s["say"] == "Por seguridad, escribe tu PIN en el teclado."


def test_destinatario_que_no_esta_en_la_agenda_no_paga_y_pregunta():
    s = salidas_del_comando("Envíale 20.000 a la obra de IBA", True, "groq")
    assert s["resolution"]["kind"] == "NOT_FOUND"
    assert s["decision"]["decision"] != "PAY" and s["say"]


def test_texto_que_no_se_entiende_no_paga_y_dice_que_no_entendio():
    s = salidas_del_comando(" Yale 20.000 a Laura, hija.", True, "groq")
    assert s["decision"]["decision"] != "PAY" and s["say"]


def test_silencio_no_genera_decision_de_pago():
    s = salidas_del_comando("", had_speech=False, engine="none")
    assert s["transcript"]["hadSpeech"] is False
    assert s["decision"]["decision"] != "PAY"


def test_respuesta_si_paga_y_no_cancela():
    comando = salidas_del_comando(" Envíale 20.000 a Laura hija", True, "groq")
    si = salidas_de_la_respuesta(comando["context"], " Sí")
    assert si["reply"] == "YES" and si["decision"] == {"decision": "PAY", "reason": "CONFIRMED"}
    no = salidas_de_la_respuesta(comando["context"], " No.")
    assert no["reply"] == "NO" and no["decision"]["decision"] != "PAY" and no["say"]


def test_respuesta_poco_clara_no_paga_y_vuelve_a_preguntar():
    comando = salidas_del_comando(" Envíale 20.000 a Laura hija", True, "groq")
    r = salidas_de_la_respuesta(comando["context"], " Mmm, no sé.")
    assert r["reply"] == "UNCLEAR" and r["decision"]["decision"] != "PAY"
