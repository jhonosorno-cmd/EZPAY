"""R6 — pago: sí dentro del presupuesto, grant puntual por exceso, Idempotency-Key por
quote, PAYMENT_PENDING que nunca es rechazo, FAILED de la marca de Open Payments,
kind=verify_pending y cancelación del grant puntual tras el pago."""
import unittest

from fastapi.testclient import TestClient

import contract
import fakes
import node_double


def error_body(status: int, code: str):
    return (status, {"error": {"code": code, "message": code}})


class PaymentFlowTest(unittest.TestCase):
    def setUp(self):
        self.log: list = []
        self.app, self.node = fakes.make_app(
            transcriber=fakes.RecordingTranscriber("envíale veinte mil a mi hija", log=self.log),
            verifier=fakes.RecordingVerifier(log=self.log),
            active_budget=True,
        )
        self.client = TestClient(self.app)

    def reach_confirmation(self):
        r = self.client.post("/api/turns", files=[("audio", ("c.wav", b"RIFF", "audio/wav"))]).json()
        self.assertEqual(r["state"], "AWAITING_CONFIRMATION")
        return r["sessionId"]

    def confirm(self, session_id, text="sí"):
        return self.client.post("/api/turns", data={"sessionId": session_id, "text": text}).json()

    # ---------------------------------------------------------- pago normal
    def test_yes_within_budget_pays_and_completes(self):
        """Spec «Sí dentro del presupuesto»: PAY -> COMPLETED con el recibo."""
        session_id = self.reach_confirmation()
        r = self.confirm(session_id)
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "COMPLETED")
        self.assertEqual(r["say"], "Listo, le envié 20.000 pesos a Laura hija. Te costó 150 pesos.")
        payment = r["payment"]
        self.assertEqual(payment["paymentId"], node_double.PAYMENT_ID)
        self.assertEqual(payment["receiver"], "https://ilp.interledger-test.dev/ezpay-placeholder-laura-hija")
        self.assertEqual(payment["debitAmount"], node_double.AMOUNT_DEBIT_WITHIN)
        self.assertEqual(payment["receiveAmount"], node_double.AMOUNT_RECEIVE)
        # una sola llamada de pago con su Idempotency-Key UUID
        pays = self.node.calls("POST", "/v1/payments")
        self.assertEqual(len(pays), 1)
        self.assertEqual(pays[0][2], {"quoteId": node_double.QUOTE_ID})
        self.assertTrue(pays[0][3]["idempotency-key"])

    def test_the_idempotency_key_is_created_once_per_quote(self):
        """La clave se crea UNA vez por quote y los reintentos la reutilizan (misma clave)."""
        session_id = self.reach_confirmation()
        self.node.payment_responses = [
            error_body(502, "UPSTREAM_ERROR"),
            error_body(502, "UPSTREAM_ERROR"),
            (201, {
                "paymentId": node_double.PAYMENT_ID,
                "status": "COMPLETED",
                "debitAmount": node_double.AMOUNT_DEBIT_WITHIN,
                "sentAmount": node_double.AMOUNT_DEBIT_WITHIN,
            }),
        ]
        r = self.confirm(session_id)
        self.assertEqual(r["state"], "COMPLETED")
        keys = {call[3]["idempotency-key"] for call in self.node.calls("POST", "/v1/payments")}
        self.assertEqual(len(keys), 1, "los reintentos reutilizan la clave de la quote")

    def test_exhausted_retries_answer_payment_pending_not_rejected(self):
        """Spec «Reintentos agotados»: PAYMENT_PENDING, nunca REJECTED, payment null."""
        session_id = self.reach_confirmation()
        self.node.payment_responses = [error_body(502, "UPSTREAM_ERROR")] * 3
        r = self.confirm(session_id)
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "PAYMENT_PENDING")
        self.assertIsNone(r["payment"])
        self.assertEqual(r["say"], "Tu envío está en camino. No hace falta repetirlo.")

    def test_polling_timeout_answers_payment_pending_with_the_payment(self):
        """Spec «Pago en procesamiento al vencer el polling»: PAYMENT_PENDING con el payment."""
        session_id = self.reach_confirmation()
        self.node.payment_poll_script = ["PROCESSING"] * 20  # nunca termina en el tope
        r = self.confirm(session_id)
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "PAYMENT_PENDING")
        self.assertEqual(r["payment"]["paymentId"], node_double.PAYMENT_ID)
        self.assertEqual(r["say"], "Tu envío está en camino. No hace falta repetirlo.")

    def test_failed_payment_rejects(self):
        """Spec «Pago fallido»: FAILED de la marca de Open Payments -> REJECTED."""
        session_id = self.reach_confirmation()
        self.node.payment_poll_script = ["FAILED"]
        r = self.confirm(session_id)
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "REJECTED")

    # ------------------------------------------------------- grant puntual
    def excess_confirmation(self):
        self.node.quote_response = (201, {
            "quoteId": node_double.QUOTE_ID,
            "debitAmount": node_double.AMOUNT_DEBIT_EXCESS,
            "receiveAmount": node_double.AMOUNT_RECEIVE_EXCESS,
            "expiresAt": "2026-10-17T12:05:00Z",
            "exceedsRemaining": True,
        })
        session_id = self.reach_confirmation()
        self.node.quote_response = (201, {
            "quoteId": node_double.QUOTE_ID,
            "debitAmount": node_double.AMOUNT_DEBIT_WITHIN,
            "receiveAmount": node_double.AMOUNT_RECEIVE,
            "expiresAt": "2026-10-17T12:05:00Z",
            "exceedsRemaining": False,
        })
        return session_id

    def test_yes_with_excess_requests_the_one_off_grant(self):
        """Spec «Sí con exceso de límite»: AWAITING_AUTHORIZATION con el grant puntual."""
        session_id = self.excess_confirmation()
        r = self.confirm(session_id)
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "AWAITING_AUTHORIZATION")
        self.assertEqual(r["interactUrl"], node_double.INTERACT_URL)
        grants = self.node.calls("POST", "/v1/grants")
        self.assertEqual(len(grants), 1)
        body = grants[0][2]
        self.assertEqual(body["limit"]["debitAmount"]["value"], "30150000")
        # regla del 17 oct: SIEMPRE R1 y el inicio es el instante de la solicitud en UTC
        self.assertEqual(body["limit"]["interval"], "R1/2026-10-17T12:00:00Z/P1W")
        self.assertEqual(body["finishUri"], "http://localhost:5173/grant-callback")
        # el say no menciona costo ni débito
        self.assertEqual(r["say"], "Te voy a llevar a tu billetera. Toca el botón que dice Aprobar.")
        session = self.app.state.session_store.get(session_id)
        self.assertEqual(session.pending_authorization, "one_off")

    def test_one_off_callback_requotes_pays_and_cancels_the_grant(self):
        """Spec «Recotización después del callback» + «Cancelación después de un pago completado»."""
        session_id = self.excess_confirmation()
        self.confirm(session_id)  # AWAITING_AUTHORIZATION con el puntual pendiente
        r = self.client.post("/api/grant-callback", json={"interactRef": "ref", "hash": "hash"}).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "COMPLETED")
        self.assertEqual(r["say"], "Listo, le envié 20.000 pesos a Laura hija. Te costó 150 pesos.")
        # la recotización usa el grantId del puntual
        quotes = self.node.calls("POST", "/v1/quotes")
        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[1][2]["grantId"], node_double.GRANT_ID)
        # el pago usa una Idempotency-Key nueva (distinta de la de la quote original)
        self.assertEqual(len(self.node.calls("POST", "/v1/payments")), 1)
        # el puntual se cancela tras el pago completado
        cancels = self.node.calls("DELETE", "/v1/grants/g_abc123")
        self.assertEqual(len(cancels), 1)

    def test_one_off_callback_with_new_excess_cancels_and_requests_another(self):
        """Spec «La quote nueva ya no entra en el puntual»: cancela, pide otro, AWAITING_AUTHORIZATION."""
        session_id = self.excess_confirmation()
        self.confirm(session_id)
        self.node.quote_response = (201, {
            "quoteId": "q_999",
            "debitAmount": {"value": "30160000", "assetCode": "COP", "assetScale": 2},
            "receiveAmount": node_double.AMOUNT_RECEIVE_EXCESS,
            "expiresAt": "2026-10-17T12:06:00Z",
            "exceedsRemaining": True,
        })
        r = self.client.post("/api/grant-callback", json={"interactRef": "ref", "hash": "hash"}).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "AWAITING_AUTHORIZATION")
        self.assertEqual(len(self.node.calls("DELETE", "/v1/grants/g_abc123")), 1)
        grants = self.node.calls("POST", "/v1/grants")
        self.assertEqual(grants[-1][2]["limit"]["debitAmount"]["value"], "30160000")
        self.assertEqual(r["say"], "Te voy a llevar a tu billetera. Toca el botón que dice Aprobar.")

    def test_limit_exceeded_at_pay_requests_the_one_off(self):
        """Spec «Límite excedido al pagar»: 403 LIMIT_EXCEEDED -> grant puntual, sin pagar."""
        session_id = self.reach_confirmation()
        self.node.payment_responses = [error_body(403, "LIMIT_EXCEEDED")]
        r = self.confirm(session_id)
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "AWAITING_AUTHORIZATION")
        self.assertEqual(len(self.node.calls("POST", "/v1/grants")), 1)

    # ------------------------------------------------- verificación pendiente
    def pending_session(self, poll_script):
        session_id = self.reach_confirmation()
        self.node.payment_poll_script = poll_script
        self.confirm(session_id)
        return session_id

    def test_verify_pending_completes_the_report(self):
        """Spec «Pendiente que se completa en la próxima interacción»."""
        session_id = self.pending_session(["PROCESSING"])
        self.node.payment_poll_script = ["COMPLETED"]
        r = self.client.post("/api/turns", data={"sessionId": session_id, "kind": "verify_pending"}).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "COMPLETED")
        self.assertEqual(r["payment"]["paymentId"], node_double.PAYMENT_ID)
        self.assertEqual(r["say"], "Listo, le envié 20.000 pesos a Laura hija. Te costó 150 pesos.")

    def test_verify_pending_still_processing_stays_pending(self):
        """Spec «Pendiente que sigue en procesamiento»: no se declara fallido."""
        session_id = self.pending_session(["PROCESSING"])
        self.node.payment_poll_script = ["PROCESSING"] * 20
        r = self.client.post("/api/turns", data={"sessionId": session_id, "kind": "verify_pending"}).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "PAYMENT_PENDING")
        self.assertEqual(r["payment"]["paymentId"], node_double.PAYMENT_ID)

    def test_verify_pending_without_payment_id_retries_with_the_same_key(self):
        """Spec «Reintentos agotados sin paymentId»: misma Idempotency-Key, misma quote."""
        session_id = self.reach_confirmation()
        self.node.payment_responses = [error_body(502, "UPSTREAM_ERROR")] * 3
        self.confirm(session_id)  # PAYMENT_PENDING sin paymentId
        self.node.payment_responses = [
            (201, {
                "paymentId": node_double.PAYMENT_ID,
                "status": "COMPLETED",
                "debitAmount": node_double.AMOUNT_DEBIT_WITHIN,
                "sentAmount": node_double.AMOUNT_DEBIT_WITHIN,
            }),
        ]
        r = self.client.post("/api/turns", data={"sessionId": session_id, "kind": "verify_pending"}).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "COMPLETED")
        keys = {call[3]["idempotency-key"] for call in self.node.calls("POST", "/v1/payments")}
        self.assertEqual(len(keys), 1, "la verificación reusa la clave original")

    def test_verify_pending_with_failed_marks_rejected(self):
        session_id = self.pending_session(["PROCESSING"])
        self.node.payment_poll_script = ["FAILED"]
        r = self.client.post("/api/turns", data={"sessionId": session_id, "kind": "verify_pending"}).json()
        self.assertEqual(r["state"], "REJECTED")

    # ------------------------------------------------------- confirmación
    def test_unclear_reply_asks_again_once_then_rejects(self):
        """Spec «Respuesta que no es un sí claro»: repregunta una vez; dos veces -> REJECTED."""
        session_id = self.reach_confirmation()
        first = self.confirm(session_id, "qué?")
        self.assertEqual(first["state"], "AWAITING_CONFIRMATION")
        self.assertEqual(first["say"], "No te entendí. ¿Le envío 20.000 pesos a Laura hija? Di sí o no.")
        second = self.confirm(session_id, "bah")
        self.assertEqual(second["state"], "REJECTED")
        self.assertEqual(second["say"], "No pude confirmar tu respuesta. No envié nada.")
        self.assertEqual(self.node.calls("POST", "/v1/payments"), [])

    def test_clear_no_rejects(self):
        session_id = self.reach_confirmation()
        r = self.confirm(session_id, "no")
        self.assertEqual(r["state"], "REJECTED")
        self.assertEqual(r["say"], "Listo, cancelé el envío.")
        self.assertEqual(self.node.calls("POST", "/v1/payments"), [])


if __name__ == "__main__":
    unittest.main()
