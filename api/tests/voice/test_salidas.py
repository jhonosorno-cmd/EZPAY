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


# --- Frases sugeridas del modo libre: lo esperado debe coincidir con lo que el sistema entiende del texto exacto
from scripts.salidas import FRASES_LIBRES  # noqa: E402


def test_hay_frases_sugeridas_distintas():
    assert len(FRASES_LIBRES) >= 15
    assert len({f.decir for f in FRASES_LIBRES}) == len(FRASES_LIBRES)


def test_lo_esperado_de_cada_frase_coincide_con_lo_que_entiende_el_sistema():
    for f in FRASES_LIBRES:
        s = salidas_del_comando(f.decir, True, "groq")
        monto = s["intent"]["amount"]
        pesos = int(monto["value"]) // 10 ** monto["assetScale"] if monto else None
        assert pesos == f.pesos, (f.decir, pesos)
        assert s["resolution"]["kind"] == f.resolucion, (f.decir, s["resolution"]["kind"])
        assert s["decision"]["decision"] != "PAY"  # un comando por voz nunca paga sin PIN ni confirmación


def test_las_sugeridas_cubren_nombres_fuera_de_la_agenda_y_casos_sin_monto_o_sin_nombre():
    resoluciones = {f.resolucion for f in FRASES_LIBRES}
    assert {"RESOLVED", "NOT_FOUND", "CHOICE"} <= resoluciones
    assert any(f.pesos is None for f in FRASES_LIBRES)
