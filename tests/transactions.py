class Transakcje:
    def __init__(self):
        self.accounts = {"KONTO_A": 1000.0, "KONTO_B": 1000.0}

    def execute_transaction(self, transaction_data: str):
        parts = [p.strip() for p in transaction_data.split(";")]
        if not parts:
            return

        tx_type = parts[0].upper()

        if tx_type == "TRANSFER" and len(parts) >= 4:
            source, dest, amount = parts[1], parts[2], float(parts[3])
            if self.accounts.get(source, 0.0) >= amount:
                self.accounts[source] -= amount
                self.accounts[dest] = self.accounts.get(dest, 0.0) + amount
            else:
                print(f"!!! ERROR: Insufficient funds on {source}")

        elif tx_type == "DEPOSIT" and len(parts) >= 3:
            account, amount = parts[1], float(parts[2])
            self.accounts[account] = self.accounts.get(account, 0.0) + amount

        elif tx_type == "WITHDRAW" and len(parts) >= 3:
            account, amount = parts[1], float(parts[2])
            if self.accounts.get(account, 0.0) >= amount:
                self.accounts[account] -= amount
            else:
                print(f"!!! ERROR: Insufficient funds on {account}")
