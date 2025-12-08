import time
import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Set, Optional

from raft_messages import RaftMessage, RaftMessageType

@dataclass
class Log:
    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def append(self, request_number: Any, timestamp: Any, message: Any = None) -> None:
        if message is None:
            message = request_number
            request_number = (0, 0)

        self.entries.append(
            {
                "request_number": request_number,  # (term, index)
                "timestamp": str(timestamp),
                "message": message,
            }
        )

class Node:
    def __init__(self, ip_addr: str, up_to_date: bool, ID: int, logger: Optional[Callable[[str, str], None]] = None) -> None:
        self.ID = ID
        self.ip_addr: str = ip_addr
        self.logger = logger

        self.accounts: dict[str, float] = {'KONTO_A': 10000.00, 'KONTO_B': 5000.00}
        
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        self.log: Log = Log()

        # --- Volatile state ---
        self.commit_index: int = -1
        self.last_applied: int = -1

        # --- Volatile state (Leader only) ---
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}

        # --- Election state ---
        self.role: str = "follower" 
        self.votes_received: Set[str] = set()
        self.leader_id: Optional[str] = None

        # --- Timers ---
        self._now = time.monotonic
        # ZWIĘKSZONE TIMEOUTY DLA STABILNOŚCI
        self.election_base: float = 2.0 
        self.election_jitter: float = 1.0 
        
        self.last_heartbeat: float = self._now()
        self.election_deadline: float = 0.0
        self._reset_election_deadline()

    def log_event(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger(message, level)
        else:
            print(f"[{level}] {message}")
            
    def _reset_election_deadline(self) -> None:
        span = self.election_base + random.uniform(0, self.election_jitter)
        self.election_deadline = self._now() + span

    def get_last_log_index(self) -> int:
        return len(self.log.entries) - 1

    def get_last_log_term(self) -> int:
        if not self.log.entries:
            return 0
        return self.log.entries[-1]["request_number"][0]

    def _candidate_log_up_to_date(self, cand_last_idx: int, cand_last_term: int) -> bool:
        my_idx = self.get_last_log_index()
        my_term = self.get_last_log_term()
        if cand_last_term > my_term: return True
        if cand_last_term < my_term: return False
        return cand_last_idx >= my_idx

    def apply_committed_entries(self):
        """Aplikuje wpisy z logu do maszyny stanów (kont)."""
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            if self.last_applied < len(self.log.entries):
                entry = self.log.entries[self.last_applied]
                operation = entry["message"]
                print(f"[State Machine] Applying index {self.last_applied}: {operation}")
                self.log_event(f"Committing index {self.last_applied}: {operation}", "COMMIT")
                self.execute_transaction(operation)

    def execute_transaction(self, transaction_data: str):
        """Logika biznesowa: DEPOSIT, WITHDRAW, TRANSFER."""
        parts = [p.strip() for p in transaction_data.split(';')]
        if not parts: return False
            
        tx_type = parts[0].upper()
            
        if tx_type == "TRANSFER" and len(parts) >= 4:
            source, dest, amount = parts[1], parts[2], float(parts[3])
            if self.accounts.get(source, 0.0) >= amount:
                self.accounts[source] -= amount
                self.accounts[dest] = self.accounts.get(dest, 0.0) + amount
                print(f"==APPLIED== Transfer {amount} from {source} to {dest}")
            else:
                print(f"!!! ERROR: Insufficient funds on {source}")
            
        elif tx_type == "DEPOSIT" and len(parts) >= 3:
            account, amount = parts[1], float(parts[2])
            self.accounts[account] = self.accounts.get(account, 0.0) + amount
            print(f"==APPLIED== Deposit {amount} to {account}")
            
        elif tx_type == "WITHDRAW" and len(parts) >= 3:
            account, amount = parts[1], float(parts[2])
            if self.accounts.get(account, 0.0) >= amount:
                self.accounts[account] -= amount
                print(f"==APPLIED== Withdraw {amount} from {account}")
            else:
                print(f"!!! ERROR: Insufficient funds on {account}")

    def receive_message(
        self, message: RaftMessage, message_pool: List[RaftMessage], quorum: int, nodes_ips: List[str]
    ) -> None:
        
        if message.term > self.current_term:
            self.log_event(f"New term {message.term} detected (from {message.from_ip})", "TERM")
            self.current_term = message.term
            self.role = "follower"
            self.voted_for = None
            self.leader_id = None
            self._reset_election_deadline()

        if message.term < self.current_term:
            if message.message_type == RaftMessageType.REQUEST_VOTE:
                self.send_message(message_pool, [message.from_ip], RaftMessageType.VOTE, self.current_term, {"granted": False})
            elif message.message_type == RaftMessageType.APPEND_ENTRIES:
                self.send_message(message_pool, [message.from_ip], RaftMessageType.APPEND_RESPONSE, self.current_term, {"success": False})
            return

        if message.message_type == RaftMessageType.APPEND_ENTRIES:
            self.leader_id = message.from_ip
            self.role = "follower"
            self._reset_election_deadline()

        if message.message_type == RaftMessageType.REQUEST_VOTE:
            self._handle_request_vote(message, message_pool)
        elif message.message_type == RaftMessageType.VOTE:
            self._handle_vote_response(message, quorum, nodes_ips, message_pool)
        elif message.message_type == RaftMessageType.APPEND_ENTRIES:
            self._handle_append_entries(message, message_pool)
        elif message.message_type == RaftMessageType.APPEND_RESPONSE:
            self._handle_append_response(message, quorum, nodes_ips, message_pool)

    def _handle_request_vote(self, message: RaftMessage, message_pool: List[RaftMessage]) -> None:
        content = message.message_content
        candidate_id = content.get("candidate_id", message.from_ip) if isinstance(content, dict) else message.from_ip
        
        can_vote = (self.voted_for is None) or (self.voted_for == candidate_id)
        
        log_is_ok = True
        if isinstance(content, dict):
            cand_idx = content.get("last_log_index", -1)
            cand_term = content.get("last_log_term", 0)
            log_is_ok = self._candidate_log_up_to_date(cand_idx, cand_term)

        if can_vote and log_is_ok:
            self.voted_for = candidate_id
            self.log_event(f"Voted for {candidate_id} in term {self.current_term}", "VOTE")
            self.send_message(message_pool, [message.from_ip], RaftMessageType.VOTE, self.current_term, {"granted": True})
            self._reset_election_deadline()
        else:
            self.send_message(message_pool, [message.from_ip], RaftMessageType.VOTE, self.current_term, {"granted": False})

    def _handle_vote_response(self, message: RaftMessage, quorum: int, nodes_ips: List[str], message_pool: List[RaftMessage]) -> None:
        if self.role != "candidate": return
        if isinstance(message.message_content, dict) and message.message_content.get("granted"):
            self.votes_received.add(message.from_ip)
            
        if len(self.votes_received) >= quorum:
            self.become_leader(nodes_ips, message_pool)

    def _handle_append_entries(self, message: RaftMessage, message_pool: List[RaftMessage]) -> None:
        content = message.message_content
        prev_log_index = content.get("prev_log_index", -1)
        prev_log_term = content.get("prev_log_term", 0)
        entries = content.get("entries", [])
        leader_commit = content.get("leader_commit", -1)

        if prev_log_index > self.get_last_log_index():
            self.send_message(message_pool, [message.from_ip], RaftMessageType.APPEND_RESPONSE, 
                              self.current_term, {"success": False, "index": self.get_last_log_index()})
            return

        if prev_log_index >= 0:
            my_term_at_index = self.log.entries[prev_log_index]["request_number"][0]
            if my_term_at_index != prev_log_term:
                self.log.entries = self.log.entries[:prev_log_index]
                self.send_message(message_pool, [message.from_ip], RaftMessageType.APPEND_RESPONSE, 
                                  self.current_term, {"success": False, "index": self.get_last_log_index()})
                return

        for i, entry in enumerate(entries):
            idx = prev_log_index + 1 + i
            if idx < len(self.log.entries):
                if self.log.entries[idx]["request_number"][0] != entry["request_number"][0]:
                    self.log.entries = self.log.entries[:idx]
                    self.log.entries.append(entry)
            else:
                self.log.entries.append(entry)

        if leader_commit > self.commit_index:
            self.commit_index = min(leader_commit, self.get_last_log_index())
            self.apply_committed_entries() 

        self.send_message(message_pool, [message.from_ip], RaftMessageType.APPEND_RESPONSE, 
                          self.current_term, {"success": True, "index": self.get_last_log_index()})

    def _handle_append_response(self, message: RaftMessage, quorum: int, nodes_ips: List[str], message_pool: List[RaftMessage]) -> None:
        if self.role != "leader": return

        content = message.message_content
        success = content.get("success", False)
        follower_index = content.get("index", 0)
        peer = message.from_ip

        if success:
            self.match_index[peer] = follower_index
            self.next_index[peer] = follower_index + 1
            
            sorted_matches = sorted([self.match_index.get(p, -1) for p in nodes_ips if p != self.ip_addr] + [self.get_last_log_index()])
            majority_index = sorted_matches[len(sorted_matches) - quorum]
            
            if majority_index > self.commit_index:
                if self.log.entries[majority_index]["request_number"][0] == self.current_term:
                    self.commit_index = majority_index
                    print(f"[Leader] Committed index {self.commit_index}")
                    self.apply_committed_entries() 
        else:
            self.next_index[peer] = max(0, self.next_index[peer] - 1)

    def become_leader(self, nodes_ips: List[str], message_pool: List[RaftMessage]) -> None:
        if self.role == "leader": return
        self.role = "leader"
        self.leader_id = self.ip_addr
        print(f"!!! Node {self.ID} became LEADER (Term {self.current_term}) !!!")
        self.log_event(f"Became LEADER (Term {self.current_term})", "LEADER")
        
        last_idx = self.get_last_log_index()
        for ip in nodes_ips:
            if ip == self.ip_addr: continue
            self.next_index[ip] = last_idx + 1
            self.match_index[ip] = -1
            
        self.broadcast_append_entries(message_pool, nodes_ips)

    def broadcast_append_entries(self, message_pool: List[RaftMessage], nodes_ips: List[str]) -> None:
        for ip in nodes_ips:
            if ip == self.ip_addr: continue
            
            prev_idx = self.next_index.get(ip, 0) - 1
            prev_term = 0
            if prev_idx >= 0 and prev_idx < len(self.log.entries):
                prev_term = self.log.entries[prev_idx]["request_number"][0]
            
            entries_to_send = []
            if (prev_idx + 1) < len(self.log.entries):
                entries_to_send = self.log.entries[prev_idx + 1:]
                
            content = {
                "prev_log_index": prev_idx,
                "prev_log_term": prev_term,
                "entries": entries_to_send,
                "leader_commit": self.commit_index,
                "leader_id": self.ip_addr
            }
            
            self.send_message(message_pool, [ip], RaftMessageType.APPEND_ENTRIES, self.current_term, content)

    def send_message(self, pool: List[RaftMessage], targets: List[str], m_type: RaftMessageType, term: int, content: Any) -> None:
        for ip in targets:
            if ip == self.ip_addr: continue
            pool.append(RaftMessage(self.ip_addr, ip, m_type, term, content))