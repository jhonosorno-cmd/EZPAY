"""Fachada de ML 2 para el orquestador (H3, add-ml2-integration/voice-turn-integration).

Funciones sueltas SIN estado de sesión: el orquestador (unidad 7 de Pagos) guarda todo en su
sesión y solo llama aquí. La fachada convierte el audio del comando en `context.voice`, la
respuesta al desafío en `context.confirmation`, elige el modo con `choose_confirmation_mode`,
pide la frase siguiente con `next_challenge_phrase`, conecta el enrolamiento web del Contrato
B (B-5) y falla cerrado: excepción, timeout, modelo sin cargar, huella ausente o audio
ilegible ⇒ NOT_AVAILABLE, nunca VERIFIED (SEG-6). El orquestador no conoce SpeechBrain, el
umbral, el recorte ni las reglas del desafío; el corte de frase lo aplica el motor (P8).

Lo único de módulo es lo que carga una vez al arrancar con `init(...)`: el verificador (ECAPA,
`load()` con `HF_HUB_OFFLINE=1` como hoy), el enrolamiento, el decoder de Voz (`AvDecoder`) y
el banco de frases (`voice.challenge.load_bank`). Todo puede inyectarse para las pruebas con
dobles sin modelo. Si algo falla al cargar, la fachada NO lanza: queda en modo degradado y
`voice_of` da NOT_AVAILABLE y el enrolamiento responde el error controlado.

Privacidad (PRIV-1/PRIV-4): aquí no se escriben audio, embeddings, transcripciones, puntajes
ni frases; los mensajes de log son fijos y sin datos del request.
"""
import concurrent.futures
import logging
import random
import threading
from concurrent.futures import ThreadPoolExecutor

from voice.challenge import load_bank, phrase_match, pick_phrase
from voice.engines import AvDecoder

logger = logging.getLogger(__name__)

TIMEOUT_S_DEFECTO = 2.0  # P2: el paralelo transcribe + verify cabe en 2 s; vencidos, NOT_AVAILABLE

# Fachada no cargada o fallo inesperado del enrolamiento: el 500 INTERNAL_ERROR que el
# Contrato B ya define para /api/enrollment (openapi/contract-b.yaml, InternalError).
ERROR_INTERNO = (500, {"error": {"code": "INTERNAL_ERROR", "message": "INTERNAL_ERROR"}})

_MENSAJE_INVALIDO = "invalid confirmation input"  # fijo y sin el valor recibido (PRIV-4)

_estados = {
    "verifier": None,
    "enrollment": None,
    "decoder": None,
    "bank": [],
    "timeout_s": TIMEOUT_S_DEFECTO,
    "cargada": False,
    "executor": None,
    "candado": threading.Lock(),  # una verificación a la vez; vencida NO se cancela (P2)
}


def init(verifier=None, enrollment=None, decoder=None, bank=None, timeout_s=TIMEOUT_S_DEFECTO):
    """Carga UNA vez lo que no se inyecta. Si algo falla, NO lanza: modo degradado."""
    viejo = _estados["executor"]
    if viejo is not None:
        viejo.shutdown(wait=False)
    try:
        if verifier is None:
            from speaker.verification import SpeakerVerifier

            verifier = SpeakerVerifier()
            verifier.load()  # una vez al arrancar; HF_HUB_OFFLINE=1 lo fija el embedder
        if enrollment is None:
            from speaker.enrollment import SpeakerEnrollment

            enrollment = SpeakerEnrollment(verifier)
        if decoder is None:
            decoder = AvDecoder()
        if bank is None:
            bank = load_bank()
        _estados.update(verifier=verifier, enrollment=enrollment, decoder=decoder,
                        bank=list(bank), timeout_s=float(timeout_s), cargada=True,
                        executor=ThreadPoolExecutor(max_workers=1, thread_name_prefix="ml2-facade"))
    except Exception as e:
        logger.warning("Facade not loaded (%s)", type(e).__name__)
        _estados.update(verifier=None, enrollment=None, decoder=None, bank=[], cargada=False,
                        executor=None)


def _reiniciar():
    """Deja la fachada sin cargar (solo para las pruebas)."""
    if _estados["executor"]:
        _estados["executor"].shutdown(wait=False)
    _estados.update(verifier=None, enrollment=None, decoder=None, bank=[], cargada=False,
                    executor=None)


def _sin_voz():
    return {"status": "NOT_AVAILABLE", "score": None}


def _verificar(pcm, user):
    try:
        return _estados["verifier"].verify(pcm, user)
    except Exception:
        logger.warning("Speaker verification failed")
        return _sin_voz()


def voice_of(audio: bytes, user="usuario", timeout_s=None) -> dict:
    """context.voice: decodifica con el decoder de Voz y llama verifier.verify.

    Sirve para el comando y para la respuesta al desafío. Fallos cerrados (P2):
    excepción, audio ilegible, modelo caído o huella ausente ⇒ NOT_AVAILABLE.
    Timeout de 2 s (configurable) en un executor de 1 hilo: la verificación
    vencida NO se cancela y, mientras siga corriendo, toda llamada nueva
    responde NOT_AVAILABLE de inmediato, sin encolar.
    """
    if not _estados["cargada"]:
        logger.warning("Facade not loaded")
        return _sin_voz()
    try:
        pcm = _estados["decoder"].decode(audio)
    except Exception:
        logger.warning("Facade failed to decode audio")
        return _sin_voz()
    tope = _estados["timeout_s"] if timeout_s is None else float(timeout_s)
    candado = _estados["candado"]
    if not candado.acquire(blocking=False):  # ocupada: la verificación vencida sigue corriendo
        logger.warning("Speaker verification busy; returning NOT_AVAILABLE")
        return _sin_voz()
    try:
        future = _estados["executor"].submit(_verificar, pcm, user)
    except RuntimeError:  # executor apagado
        candado.release()
        return _sin_voz()
    try:
        resultado = future.result(timeout=tope)
    except concurrent.futures.TimeoutError:
        logger.warning("Speaker verification timed out")
        if not future.done():  # sigue corriendo: libera el candado al terminar, sin cancelar
            threading.Thread(target=_soltar_al_terminar, args=(future, candado), daemon=True).start()
            return _sin_voz()
        candado.release()
        return _sin_voz()
    except Exception:
        logger.warning("Speaker verification failed")
        candado.release()
        return _sin_voz()
    candado.release()
    return resultado


def _soltar_al_terminar(future, candado):
    try:
        future.result()
    except Exception:
        pass
    candado.release()


def verify_and_transcribe(audio: bytes, transcribe_fn, user="usuario", timeout_s=None) -> tuple:
    """Corre en paralelo voice_of(audio) y transcribe_fn(); espera las dos.

    La verificación nunca lanza (fail-closed); la transcripción sí puede
    lanzar: sus errores son del contrato de Voz y Pagos y se propagan.
    """
    with ThreadPoolExecutor(max_workers=2) as ex:
        voz = ex.submit(voice_of, audio, user, timeout_s)
        texto = ex.submit(transcribe_fn)
        return voz.result(), texto.result()


def choose_confirmation_mode(challenge_enabled: bool, decision_phase: str,
                             decision: str, command_voice_status: str | None) -> str:
    """CHALLENGE solo con la bandera activa, ASK_CONFIRM directo de la fase
    COMMAND y comando verificado por voz; en cualquier otro caso, REPLY (el PIN
    ya es el segundo factor y no hay ciclos de PIN). La decisión final es del
    orquestador: este helper es puro y sin estado (P5)."""
    if (challenge_enabled and decision == "ASK_CONFIRM" and decision_phase == "COMMAND"
            and command_voice_status == "VERIFIED"):
        return "CHALLENGE"
    return "REPLY"


def next_challenge_phrase(used: list[str], last: str | None = None, rng=None) -> tuple:
    """Siguiente frase del banco con pick_phrase (al azar, nunca el LLM, sin
    repetir) y la lista de usadas actualizada. No muta la lista recibida; el
    orquestador guarda ambas en su sesión. Sin rng usa random.SystemRandom()."""
    rng = rng or random.SystemRandom()
    frase = pick_phrase(_estados["bank"], set(used), rng, last=last)
    return frase, [*used, frase]


def build_confirmation(mode, *, transcript=None, expected_phrase=None, voice=None,
                       challenge_attempts=0) -> dict:
    """Dict camelCase `{"mode", "phraseScore", "voice", "challengeAttempts"}` del B11.

    `phraseScore` es phrase_match (número, no booleano; el corte lo aplica el
    motor, P8), redondeado a 4 decimales; `None` sin respuesta por voz. REPLY
    no verifica nada. Entradas inválidas ⇒ ValueError con mensaje fijo."""
    if mode not in ("CHALLENGE", "REPLY") or isinstance(mode, str) is False:
        raise ValueError(_MENSAJE_INVALIDO)
    if transcript is not None and not isinstance(transcript, str):
        raise ValueError(_MENSAJE_INVALIDO)
    if expected_phrase is not None and not isinstance(expected_phrase, str):
        raise ValueError(_MENSAJE_INVALIDO)
    if voice is not None and not (isinstance(voice, dict) and set(voice) == {"status", "score"}):
        raise ValueError(_MENSAJE_INVALIDO)
    if isinstance(challenge_attempts, bool) or not isinstance(challenge_attempts, int) \
            or challenge_attempts < 0:
        raise ValueError(_MENSAJE_INVALIDO)
    if mode == "REPLY":
        return {"mode": "REPLY", "phraseScore": None, "voice": None,
                "challengeAttempts": challenge_attempts}
    if transcript is None:
        phrase_score = None
    else:
        if expected_phrase is None:
            raise ValueError(_MENSAJE_INVALIDO)
        phrase_score = round(phrase_match(transcript, expected_phrase), 4)
    return {"mode": "CHALLENGE", "phraseScore": phrase_score, "voice": voice,
            "challengeAttempts": challenge_attempts}


def command_say_context(context: dict, mode: str) -> dict:
    """Copia del context para el `say` de la confirmación (fase COMMAND).

    Con CHALLENGE agrega `confirmation = {mode: "CHALLENGE", phraseScore: null,
    voice: null, challengeAttempts: 0}` para que say_situation elija
    CONFIRM_CHALLENGE/CONFIRM_CHALLENGE_OVERRUN; con REPLY sale CONFIRM/
    AUTH_OVERRUN ("sí" como hoy). El dict recibido no se modifica."""
    salida = dict(context)
    if mode == "CHALLENGE":
        salida["confirmation"] = {"mode": "CHALLENGE", "phraseScore": None, "voice": None,
                                  "challengeAttempts": 0}
    return salida


def enroll_from_uploads(audios: list[bytes], consent) -> tuple:
    """Contrato B-5: decodifica las 3 partes y llama SpeakerEnrollment.enroll.

    Devuelve (201, {"enrolled": True}) o (400, {"error": {"code", "message"}})
    con mensaje = código, en el orden de B-5: CONSENT_REQUIRED y
    SAMPLES_REQUIRED se revisan ANTES de decodificar. EnrollmentError se mapea
    1 a 1. Con la fachada no cargada o un fallo inesperado (no EnrollmentError),
    500 INTERNAL_ERROR del contrato."""
    if not _estados["cargada"]:
        logger.warning("Facade not loaded")
        return ERROR_INTERNO
    if consent is not True:
        return (400, {"error": {"code": "CONSENT_REQUIRED", "message": "CONSENT_REQUIRED"}})
    if len(audios) != 3:
        return (400, {"error": {"code": "SAMPLES_REQUIRED", "message": "SAMPLES_REQUIRED"}})
    try:
        muestras = [_estados["decoder"].decode(audio) for audio in audios]
    except Exception:
        logger.warning("Facade failed to decode enrollment audio")
        return (400, {"error": {"code": "INVALID_AUDIO", "message": "INVALID_AUDIO"}})
    try:
        resultado = _estados["enrollment"].enroll(muestras, consent)
    except Exception as e:
        codigo = getattr(e, "code", None)
        if codigo is None:  # fallo inesperado (modelo, disco): no es culpa del audio
            logger.warning("Speaker enrollment failed (%s)", type(e).__name__)
            return ERROR_INTERNO
        return (400, {"error": {"code": codigo, "message": codigo}})
    logger.info("Speaker enrollment completed")
    return (201, resultado)


def enrollment_status() -> tuple:
    """GET /api/enrollment (B-6): (200, {"enrolled": bool}); sin fachada, 500 INTERNAL_ERROR.
    Misma forma (estado HTTP, cuerpo) que enroll_from_uploads."""
    if not _estados["cargada"]:
        logger.warning("Facade not loaded")
        return ERROR_INTERNO
    return (200, _estados["enrollment"].status())


def is_enrolled() -> bool:
    """`enrolled` del context del motor. Sin fachada o con error ⇒ False: el motor pide PIN (D3)."""
    if not _estados["cargada"]:
        return False
    try:
        return _estados["enrollment"].status()["enrolled"] is True
    except Exception:
        logger.warning("Speaker enrollment status failed")
        return False