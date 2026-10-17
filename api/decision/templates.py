"""Tabla reason -> plantilla de `say` (SOLO datos, para verificar cobertura).

Catálogo real de ML 1 (api/voice); el orquestador inserta los valores de {…},
nunca el motor ni el LLM. Un `reason` sin plantilla es un error de contrato.
Excepción decidida: CONFIRMED no tiene `say` propio — el `say` lo define el
resultado del pago. Reglas [DECIDIDO]: (a) antes del "sí" solo receiveAmount y
nombre, nunca el costo (B-6); (b) ningún `say` contiene dígitos del PIN (B-7);
(c) {recibe} se formatea sin float, "20.000".
"""
from .models import Reason

SAY_TEMPLATES: dict[Reason, "str | dict[str, str] | None"] = {
    Reason.CANCELLED_BY_USER: "Listo, cancelé el envío.",
    Reason.INTENT_UNKNOWN: "No te entendí. ¿Me lo repites?",
    Reason.AMOUNT_ERROR: {
        "TOO_MANY_DECIMALS": "Solo puedo enviar montos con hasta {n} decimales. ¿Me lo dices otra vez?",
        "AMBIGUOUS_AMOUNT": "No me quedó claro el monto. ¿Me lo dices otra vez?",
        "INVALID_AMOUNT": "Ese monto no es válido. ¿Cuánto quieres enviar?",
    },
    Reason.INTENT_AMBIGUOUS: "No me quedó claro. Dime un solo monto y un solo destinatario.",
    Reason.AMOUNT_MISSING: "¿Cuánto quieres enviar?",
    Reason.RECIPIENT_MISSING: "¿A quién se lo envío?",
    Reason.INTENT_UNCLEAR: "No te entendí. ¿Me lo repites?",
    Reason.INTENT_LOW_CONFIDENCE: "No te entendí bien. ¿Me lo repites?",
    Reason.TRANSCRIPT_LOW_CONFIDENCE: "No te escuché bien. ¿Me lo repites?",
    Reason.RECIPIENT_NOT_FOUND: "No encontré a {destinatario} en tu agenda.",
    Reason.RECIPIENT_AMBIGUOUS: {
        "MULTI": "¿A cuál? {opción1} o {opción2}.",
        "ONE": "¿Quisiste decir {nombre}?",
    },
    Reason.NO_BUDGET_GRANT: "Para empezar, autoriza tu presupuesto en tu billetera. Toca el botón que dice Aprobar.",
    Reason.PENDING_PAYMENT_SAME_RECIPIENT: "Tu envío anterior a {nombre} aún no termina. Espera un momento.",
    Reason.PENDING_PAYMENT_UNCONFIRMED: {
        "WITHIN": "Tu envío anterior a {nombre} no se pudo confirmar. Si envías otro, {nombre} podría recibir los dos. ¿Le envío {recibe} pesos?",
        "EXCEEDS": "Tu envío anterior a {nombre} no se pudo confirmar y este supera tu presupuesto. Si sigues, {nombre} podría recibir los dos. ¿Lo autorizas en tu billetera?",
    },
    Reason.VOICE_NOT_VERIFIED: "Por seguridad, escribe tu PIN en el teclado.",
    Reason.NEW_RECIPIENT: "Es la primera vez que le envías a {nombre}. Por seguridad, escribe tu PIN en el teclado.",
    Reason.HIGH_AMOUNT: "Es un monto alto. Por seguridad, escribe tu PIN en el teclado.",
    Reason.ALL_CHECKS_PASSED: {
        "WITHIN": "¿Le envío {recibe} pesos a {nombre}?",
        "EXCEEDS": "Supera tu presupuesto. ¿Lo autorizas en tu billetera?",
    },
    Reason.PIN_CORRECT: {
        "WITHIN": "¿Le envío {recibe} pesos a {nombre}?",
        "EXCEEDS": "Supera tu presupuesto. ¿Lo autorizas en tu billetera?",
    },
    Reason.PIN_WRONG: {
        "MANY": "PIN incorrecto. Te quedan {n} intentos.",
        "ONE": "PIN incorrecto. Te queda 1 intento.",
    },
    Reason.PIN_ATTEMPTS_EXHAUSTED: "No pude verificarte. No envié nada.",
    Reason.PIN_LOCKED: "Por seguridad, el PIN está bloqueado. No envié nada.",
    Reason.PIN_INVALID_FORMAT: "El PIN tiene entre 4 y 6 números. Escríbelo otra vez.",
    Reason.CONFIRMED: None,
    Reason.CONFIRMED_NEEDS_WALLET_AUTH: "Te voy a llevar a tu billetera. Toca el botón que dice Aprobar.",
    Reason.USER_DECLINED: "Listo, cancelé el envío.",
    Reason.REPLY_UNCLEAR_ASK_AGAIN: "No te entendí. ¿Le envío {recibe} pesos a {nombre}? Di sí o no.",
    Reason.REPLY_UNCLEAR_REJECTED: "No pude confirmar tu respuesta. No envié nada.",
}

# CONFIRMED: sin say propio; el orquestador arma la frase según el resultado:
# "Listo, le envié {recibe} pesos a {nombre}." al completarse; "Te costó {costo}
# pesos." se agrega solo DESPUÉS de COMPLETED; en PROCESSING/PAYMENT_PENDING
# solo la pantalla de carga, sin frase.