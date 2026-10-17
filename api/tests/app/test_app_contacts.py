"""Agenda de contactos (extensión x-proposed del Contrato B): alta validada contra Open Payments,
duplicados, borrado y uso inmediato en un turno de pago. Wallets inventadas, sin red."""
import unittest

from app_doubles import DoubleAppMixin


class ContactsTest(DoubleAppMixin, unittest.TestCase):
    def add(self, name, wallet, status=201):
        r = self.client.post("/api/contacts", json={"name": name, "walletAddress": wallet})
        self.assertEqual(r.status_code, status, r.text)
        return r.json()

    def test_list_starts_with_the_seed_agenda(self):
        aliases = {c["alias"] for c in self.client.get("/api/contacts").json()["contacts"]}
        self.assertEqual(aliases, {"mi-hija", "laura-vecina", "jose"})

    def test_add_validates_the_wallet_and_persists(self):
        body = self.add("Pedro Pérez", "https://wallet.test/pedro")
        self.assertEqual(body["alias"], "pedro-perez")
        self.assertEqual(body["walletAddress"], "https://wallet.test/pedro")
        self.assertIn("https://wallet.test/pedro", self.orch.contacts._resolver.calls)
        names = [c["name"] for c in self.client.get("/api/contacts").json()["contacts"]]
        self.assertIn("Pedro Pérez", names)

    def test_payment_pointer_is_normalized(self):
        body = self.add("Pedro", "$wallet.test/pedro")
        self.assertEqual(body["walletAddress"], "https://wallet.test/pedro")

    def test_wallet_in_another_currency_is_rejected(self):
        self.assertEqual(self.add("Gringo", "https://wallet.test/usd", 400)["error"]["code"], "INVALID_WALLET")

    def test_unknown_wallet_is_rejected(self):
        self.assertEqual(self.add("Nadie", "https://wallet.test/nadie", 400)["error"]["code"], "INVALID_WALLET")

    def test_not_a_url_is_rejected_without_network(self):
        self.assertEqual(self.add("Pedro", "pedro", 400)["error"]["code"], "INVALID_WALLET")
        self.assertEqual(self.orch.contacts._resolver.calls, [])

    def test_own_wallet_is_rejected(self):
        self.assertEqual(self.add("Yo", "https://wallet.test/marta", 400)["error"]["code"], "INVALID_WALLET")

    def test_duplicates_are_rejected(self):
        self.add("Pedro", "https://wallet.test/pedro")
        self.assertEqual(self.add("Pedro", "https://wallet.test/otro", 409)["error"]["code"], "CONTACT_EXISTS")
        self.assertEqual(self.add("Otro", "https://wallet.test/pedro", 409)["error"]["code"], "CONTACT_EXISTS")

    def test_name_with_digits_is_rejected(self):
        self.assertEqual(self.add("R2D2", "https://wallet.test/r2", 400)["error"]["code"], "INVALID_CONTACT")

    def test_delete(self):
        self.assertEqual(self.client.delete("/api/contacts/jose").status_code, 204)
        self.assertEqual(self.client.delete("/api/contacts/jose").json()["error"]["code"], "CONTACT_NOT_FOUND")

    def test_new_contact_is_payable_right_away(self):
        self.add("Pedro", "https://wallet.test/pedro")
        self.client.post("/api/budget", json={"debitAmount": {"value": "20000000", "assetCode": "COP", "assetScale": 2}})
        self.client.post("/api/grant-callback", json={"interactRef": "r", "hash": "h"})
        body = self.client.post("/api/turns", files={"audio": ("c.webm", "envíale veinte mil a Pedro".encode(), "audio/webm")}).json()
        self.assertEqual(body["state"], "AWAITING_PIN")  # destinatario nuevo: PIN (NEW_RECIPIENT)
        quote = [c for c in self.node.calls if c[0] == "create_quote"][-1]
        self.assertEqual(quote[2], "https://wallet.test/pedro")


if __name__ == "__main__":
    unittest.main()
