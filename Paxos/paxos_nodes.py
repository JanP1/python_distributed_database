import random
import time
from collections import defaultdict
from datetime import datetime
from paxos_messages import PaxosMessage, PaxosMessageType
from typing import Iterable, List, Optional, Tuple, Dict, Callable
from dataclasses import dataclass

@dataclass
class AcceptedValue:
    value: str = ""
    count: int = 0

class Log:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    def append(self, request_number: Tuple[int,int], message:str, timestamp: datetime)-> None:
        self.entries.append({
            "request_number": request_number,
            "timestamp": str(timestamp),
            "message": message
        })

class Node:
    def __init__(self, ip_addr: str, up_to_date: bool, ID: int, logger: Optional[Callable[[str, str], None]] = None) -> None:
        self.ID = ID
        self.ip_addr: str = ip_addr
        self.logger = logger  # Przechowujemy funkcję logującą
        
        self.accounts: dict[str, float] = {'KONTO_A': 10000.00, 'KONTO_B': 5000.00}
        self.locked_accounts: dict[str, str] = {}
        
        # --- Paxos State ---
        self._highest_promised_id = (0, 0)
        self._highest_accepted_id = (0, 0)
        self.accepted_value = ""
        self.proposer_round_id = (0, 0)
        self.accept_sent = False
        self.promises_received = {}
        self.message_content = ""
        
        self.accepted_phase_values_id = 0
        self.accepted_phase_values: defaultdict[int, AcceptedValue] = defaultdict(AcceptedValue)
        
        self.log = Log()

    # Pomocnicza metoda do bezpiecznego logowania
    def log_event(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger(message, level)
        else:
            print(f"[{level}] {message}")

    @property
    def highest_promised_id(self) -> Tuple[int, int]:
        return self._highest_promised_id

    @highest_promised_id.setter
    def highest_promised_id(self, value: Tuple[int, int]) -> None:
        self._highest_promised_id = value

    @property
    def highest_accepted_id(self) -> Tuple[int, int]:
        return self._highest_accepted_id

    @highest_accepted_id.setter
    def highest_accepted_id(self, value: Tuple[int, int]) -> None:
        self._highest_accepted_id = value
        
    def reset_paxos_state(self) -> None:
        self.accepted_value = ""
        self.promises_received.clear()
        self.message_content = ""
        self.accepted_phase_values_id = 0
        self.accept_sent = False
        self.accepted_phase_values.clear()
        self.locked_accounts.clear()

    def _get_required_accounts(self, tx_data: str) -> List[str]:
        parts = [p.strip() for p in tx_data.split(';')]
        tx_type = parts[0].upper()
        if tx_type == "TRANSFER" and len(parts) >= 3:
            return sorted([parts[1], parts[2]]) 
        elif tx_type in ("DEPOSIT", "WITHDRAW") and len(parts) >= 2:
            return [parts[1]]
        return []

    def _extract_tx_id(self, tx_data: str) -> Optional[str]:
        for p in tx_data.split(";"):
            p = p.strip()
            if p.startswith("TX_ID:"):
                return p.split(":",1)[1].strip()
        return None
        
    def set_new_proposal(self, new_value: str, next_round_id: Tuple[int, int]) -> None:
        self.message_content = new_value
        self.promises_received.clear()
        self.accept_sent = False
        self.proposer_round_id = tuple(next_round_id)

    def try_lock_all(self, transaction_id: str, required_accounts: List[str]) -> bool:
        for account_id in required_accounts:
            owner_id = self.locked_accounts.get(account_id)
            if owner_id and owner_id < transaction_id:
                return False
        for account_id in required_accounts:
            self.locked_accounts[account_id] = transaction_id
        return True
    
    def unlock_all(self, transaction_id: str) -> None:
        keys_to_delete = [k for k, tid in self.locked_accounts.items() if tid == transaction_id]
        for key in keys_to_delete:
            del self.locked_accounts[key]
    
    def execute_transaction(self, transaction_data: str):
        parts = [p.strip() for p in transaction_data.split(';')]
        if not parts: return False
            
        tx_type = parts[0].upper()
            
        if tx_type == "TRANSFER" and len(parts) >= 4:
            source, dest, amount = parts[1], parts[2], float(parts[3])
            if self.accounts.get(source, 0.0) >= amount:
                self.accounts[source] -= amount
                self.accounts[dest] = self.accounts.get(dest, 0.0) + amount
                self.log_event(f"Transferred {amount} {source}->{dest}", "INFO")
                return True
            else:
                self.log_event(f"Insufficient funds on {source}", "ERROR")
                return False
            
        if tx_type == "DEPOSIT" and len(parts) >= 3:
            account, amount = parts[1].strip(), float(parts[2])
            self.accounts[account] = self.accounts.get(account, 0.0) + amount
            self.log_event(f"Deposited {amount} to {account}", "INFO")
            return True
            
        if tx_type == "WITHDRAW" and len(parts) >= 3:
            account, amount = parts[1].strip(), float(parts[2])
            if self.accounts.get(account, 0.0) >= amount:
                self.accounts[account] -= amount
                self.log_event(f"Withdrawn {amount} from {account}", "INFO")
                return True
            else:
                self.log_event(f"Insufficient funds on {account}", "ERROR")
                return False
        return False

    def send_message(self, message_pool: List[PaxosMessage], target_ip: Iterable[str], message: str, message_type: PaxosMessageType, round_identifier: str) -> None:
        if message_type == PaxosMessageType.PREPARE:
            try:
                parts = str(round_identifier).split('.')
                self.proposer_round_id = (int(parts[0]), int(parts[1]))
                self.promises_received.clear() 
                self.accept_sent = False
            except ValueError: pass

        for ip in target_ip:
            message_pool.append(PaxosMessage(self.ip_addr, ip, message_type, round_identifier, message))

    def _round_id_from_message(self, message: PaxosMessage) -> Tuple[int, int]:
        rid = getattr(message, "round_identifier", None)
        if rid is None:
            rid = getattr(message, "round_identyfier", None)
        if rid is None: 
            rid = "0.0"
        try:
            return tuple(int(x) for x in str(rid).split("."))
        except:
            return (0, 0)

    def _find_id_by_value(self, value_to_find: str) -> Optional[int]:
        for id_, accepted_value_obj in self.accepted_phase_values.items():
            if accepted_value_obj.value == value_to_find:
                return id_
        return None

    def schedule_retry(self, transaction_data: str, message_pool: List[PaxosMessage], nodes_ips: Iterable[str], delay_range=(0.1,0.5)):
        delay = random.uniform(*delay_range)
        self.log_event(f"Retrying transaction in {delay:.2f}s", "WARNING")
        time.sleep(delay)
        round_num = self.proposer_round_id[0] + 1
        new_round_id = (round_num, self.ID)
        self.set_new_proposal(transaction_data, new_round_id)
        self.send_message(message_pool, nodes_ips, transaction_data, PaxosMessageType.PREPARE, f"{new_round_id[0]}.{new_round_id[1]}")

    def receive_message(self, message: PaxosMessage, message_pool: List[PaxosMessage], quorum: int, nodes_ips: Iterable[str]) -> None:
        mtype = message.message_type
        round_id = self._round_id_from_message(message)
        
        if mtype == PaxosMessageType.PREPARE:
            tx_data = message.message_content
            if round_id > self.highest_promised_id:
                self.highest_promised_id = round_id

                self.log_event(f"Promised round {round_id}", "PROMISE")
                
                return_message = f"{self.highest_accepted_id[0]}.{self.highest_accepted_id[1]};{self.accepted_value}" \
                    if self.highest_accepted_id != (0,0) and self.accepted_value else f"0.0;{tx_data}"
                self.send_message(message_pool, [message.from_ip], return_message, PaxosMessageType.PROMISE, f"{round_id[0]}.{round_id[1]}")
                if self.locked_accounts: self.locked_accounts.clear()
            else:
                self.log_event(f"Rejected PREPARE {round_id} (promised {self.highest_promised_id})", "REJECT")
            return

        if mtype == PaxosMessageType.PROMISE:
            if round_id > self.proposer_round_id:
                self.proposer_round_id = round_id
                self.promises_received.clear()
                self.accept_sent = False
            if round_id != tuple(self.proposer_round_id): return
            
            self.promises_received[message.from_ip] = message.message_content

            if len(self.promises_received) >= quorum and not self.accept_sent:
                accepted_val = self.message_content
                highest_id = (-1, -1)
                for content in self.promises_received.values():
                    try:
                        id_part, val_part = content.split(";", 1)
                        pid = tuple(int(x) for x in id_part.split("."))
                        if pid > highest_id:
                            highest_id = pid
                            if val_part and pid > (0,0): accepted_val = val_part
                    except: continue
                self.accept_sent = True
                
                self.log_event(f"Quorum reached. Sending ACCEPT val: {accepted_val}", "ACCEPT")
                self.send_message(message_pool, nodes_ips, accepted_val, PaxosMessageType.ACCEPT, f"{round_id[0]}.{round_id[1]}")
            return

        if mtype == PaxosMessageType.ACCEPT:
            tx_data = message.message_content
            tx_id = self._extract_tx_id(tx_data)
            required = self._get_required_accounts(tx_data)
            if tx_id: self.unlock_all(tx_id)
            else: self.locked_accounts.clear()
    
            if round_id >= self.highest_promised_id:
                if tx_id and required and not self.try_lock_all(tx_id, required):
                    self.log_event(f"Deadlock detected on ACCEPT {round_id}", "REJECT")
                    self.schedule_retry(tx_data, message_pool, nodes_ips)
                    return 
                
                self.highest_accepted_id = round_id
                self.accepted_value = tx_data

                self.log_event(f"Accepted proposal {round_id}", "ACCEPTED")
                self.send_message(message_pool, nodes_ips, self.accepted_value, PaxosMessageType.ACCEPTED, f"{round_id[0]}.{round_id[1]}")
            else:
                 self.log_event(f"Rejected ACCEPT {round_id} < {self.highest_promised_id}", "REJECT")
            return

        if mtype == PaxosMessageType.ACCEPTED:
            tx_data = message.message_content
            vid = self._find_id_by_value(tx_data)
            if vid is None:
                self.accepted_phase_values_id += 1
                vid = self.accepted_phase_values_id
                self.accepted_phase_values[vid] = AcceptedValue(tx_data, 0)
            self.accepted_phase_values[vid].count += 1
            if self.accepted_phase_values[vid].count == quorum:
                self.log_event(f"Global Consensus Reached: {tx_data}", "CONSENSUS")
                self.execute_transaction(tx_data)
                tx_id = self._extract_tx_id(tx_data)
                if tx_id: self.unlock_all(tx_id)
                self.log.append(round_id, tx_data, datetime.now())
                self.reset_paxos_state()