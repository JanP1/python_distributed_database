import unittest
from .transactions import Transakcje


class TestTransakcjeMutation(unittest.TestCase):
    def setUp(self):
        self.bank = Transakcje()
        self.bank.accounts = {"KONTO_A": 100.0, "KONTO_B": 0.0}

    def test_withdraw(self):
        self.bank.execute_transaction("WITHDRAW;KONTO_A;50.0")
        self.assertEqual(self.bank.accounts["KONTO_A"], 50.0)
        self.bank.execute_transaction("WITHDRAW;KONTO_A;50.0")
        self.assertEqual(self.bank.accounts["KONTO_A"], 0.0)
        self.bank.execute_transaction("WITHDRAW;KONTO_A;10.0")
        self.assertEqual(self.bank.accounts["KONTO_A"], 0.0)

    def test_deposit(self):
        self.bank.execute_transaction("DEPOSIT;KONTO_A;50.0")
        self.assertEqual(self.bank.accounts["KONTO_A"], 150.0)

    def test_transfer_success(self):
        self.bank.execute_transaction("TRANSFER;KONTO_A;KONTO_B;50.0")
        self.assertEqual(self.bank.accounts["KONTO_A"], 50.0)
        self.assertEqual(self.bank.accounts["KONTO_B"], 50.0)

    def test_transfer_exact_balance(self):
        self.bank.accounts["KONTO_A"] = 100.0
        self.bank.accounts["KONTO_B"] = 0.0

        self.bank.execute_transaction("TRANSFER;KONTO_A;KONTO_B;100.0")
        self.assertEqual(self.bank.accounts["KONTO_A"], 0.0)
        self.assertEqual(self.bank.accounts["KONTO_B"], 100.0)

    def test_malformed_command(self):
        try:
            self.bank.execute_transaction("DEPOSIT;KONTO_A")
        except IndexError:
            self.fail("Mutant wykryty! Kod zaakceptował niekompletną komendę.")


if __name__ == "__main__":
    unittest.main()
