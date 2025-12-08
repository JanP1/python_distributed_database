import sys
import os
import time
from typing import List

# Import modułów Raft
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Raft"))

try:
    from raft_nodes import Node
    from raft_messages import RaftMessage, RaftMessageType
except ImportError:
    print("BŁĄD: Nie znaleziono plików w folderze 'Raft'.")
    sys.exit(1)

# --- KONFIGURACJA KOLORÓW I FORMATOWANIA ---
class C:
    H = '\033[95m'    # Header (Magenta)
    OK = '\033[92m'   # Success (Green)
    WARN = '\033[93m' # Warning (Yellow)
    ERR = '\033[91m'  # Error (Red)
    INFO = '\033[94m' # Info (Blue)
    R = '\033[0m'     # Reset

class RaftFinalSimulation:
    def __init__(self):
        print(f"{C.H}=== FINALNA SYMULACJA RAFT: CYKL ŻYCIA KLASTRA ==={C.R}")
        
        self.ips = ["192.168.1.10", "192.168.1.11", "192.168.1.12", "192.168.1.14"]
        self.nodes = {}
        self.dead_nodes = set()
        
        # Inicjalizacja węzłów
        for i, ip in enumerate(self.ips):
            self.nodes[ip] = Node(ip, True, i + 1, logger=lambda m, l: None)

        self.pool = []
        self.leader_ip = None

    # --- POMOCNIKI ---
    def print_status(self, title="STAN KLASTRA"):
        print(f"\n{C.INFO}--- {title} ---{C.R}")
        print(f"{'Node':<5} | {'Role':<10} | {'Term':<5} | {'LogIdx':<6} | {'A (Saldo)':<10} | {'Status'}")
        print("-" * 65)
        for ip in self.ips:
            n = self.nodes[ip]
            status = f"{C.ERR}OFFLINE{C.R}" if ip in self.dead_nodes else f"{C.OK}ONLINE{C.R}"
            
            role_str = n.role.upper()
            if n.role == "leader": role_str = f"{C.OK}{role_str}{C.R}"
            elif n.role == "candidate": role_str = f"{C.WARN}{role_str}{C.R}"
            
            if ip in self.dead_nodes:
                 print(f"N{n.ID:<4} | {'-':<10} | {'-':<5} | {'-':<6} | {'-':<10} | {status}")
            else:
                 print(f"N{n.ID:<4} | {role_str:<19} | {n.current_term:<5} | {n.get_last_log_index():<6} | {n.accounts['ACCOUNT_A']:<10.2f} | {status}")
        print("-" * 65)

    def process_network(self, cycles=6):
        """Symuluje pętlę zdarzeń w sieci."""
        for _ in range(cycles):
            next_pool = []
            if not self.pool: break

            for msg in self.pool:
                if msg.from_ip in self.dead_nodes: continue # Martwy nie wysyła

                target = self.nodes.get(msg.to_ip)
                if target and msg.to_ip not in self.dead_nodes: # Martwy nie odbiera
                    target.receive_message(msg, next_pool, 3, self.ips)
            self.pool = next_pool

    def send_transaction(self, operation):
        leader = self.nodes.get(self.leader_ip)
        if not leader or leader.role != "leader" or self.leader_ip in self.dead_nodes:
            print(f"{C.ERR}BŁĄD TRANSALKCJI: Brak aktywnego lidera!{C.R}")
            return False

        print(f"KLIENT -> LIDER (Node {leader.ID}): {operation}")
        
        # 1. Dodanie do logu
        new_idx = leader.get_last_log_index() + 1
        leader.log.append((leader.current_term, new_idx), "NOW", operation)
        
        # 2. Rozgłoszenie
        content = {
            "entries": [leader.log.entries[-1]],
            "leader": leader.ip_addr,
            "leader_id": leader.ip_addr,
            "prev_log_index": new_idx - 1,
            "prev_log_term": leader.current_term,
            "leader_commit": leader.commit_index
        }
        leader.send_message(self.pool, self.ips, RaftMessageType.APPEND_ENTRIES, leader.current_term, content)
        
        # 3. Replikacja
        self.process_network(cycles=12)
        return True

    # =========================================================================
    # SCENARIUSZ 1: NORMALNE OPERACJE
    # =========================================================================
    def step_1_normal_operations(self):
        print(f"\n{C.H}=================================================={C.R}")
        print(f"{C.H} KROK 1: START KLASTRA I OPERACJE FINANSOWE {C.R}")
        print(f"{C.H}=================================================={C.R}")
        
        # 1. Wybory (Node 1)
        print("-> Rozpoczynanie elekcji przez Node 1...")
        n1 = self.nodes[self.ips[0]]
        n1.current_term = 1
        n1.role = "candidate"
        n1.votes_received = {n1.ip_addr}
        n1.voted_for = n1.ip_addr
        content = {"candidate_id": n1.ip_addr, "last_log_index": -1, "last_log_term": 0}
        n1.send_message(self.pool, [ip for ip in self.ips if ip != n1.ip_addr], RaftMessageType.REQUEST_VOTE, 1, content)
        
        self.process_network()
        self.leader_ip = n1.ip_addr
        print(f"{C.OK}Node 1 został liderem.{C.R}")

        # 2. Transakcje
        self.send_transaction("DEPOSIT;ACCOUNT_A;1000.00;TX_1")
        self.send_transaction("WITHDRAW;ACCOUNT_B;200.00;TX_2")
        self.send_transaction("TRANSFER;ACCOUNT_A;ACCOUNT_B;500.00;TX_3")
        
        self.print_status("STAN PO TRANSAKCJACH")

    # =========================================================================
    # SCENARIUSZ 2: ZAKLESZCZENIE I ODKLESZCZENIE
    # =========================================================================
    def step_2_deadlock_and_resolve(self):
        print(f"\n{C.H}=================================================={C.R}")
        print(f"{C.H} KROK 2: ZAKLESZCZENIE (SPLIT VOTE) I ROZWIĄZANIE {C.R}")
        print(f"{C.H}=================================================={C.R}")
        
        print(f"{C.WARN}Symulacja awarii sieci: Utrata lidera i jednoczesna elekcja Node 2 i Node 3.{C.R}")
        
        # Reset ról
        for n in self.nodes.values():
            n.role = "follower"
            n.leader_id = None
        self.leader_ip = None
        self.pool = [] # Czyścimy sieć

        term = 5
        n1, n2, n3, n4 = [self.nodes[ip] for ip in self.ips]

        # Wymuszenie Split Vote (2 vs 2)
        # Node 2 i 3 kandydują
        for n in [n2, n3]:
            n.role = "candidate"
            n.current_term = term
            n.votes_received = {n.ip_addr}
            n.voted_for = n.ip_addr
            # Wysyłają prośby
            content = {"candidate_id": n.ip_addr, "last_log_index": n.get_last_log_index(), "last_log_term": n.current_term}
            n.send_message(self.pool, self.ips, RaftMessageType.REQUEST_VOTE, term, content)

        # Node 1 i 4 głosują na różnych kandydatów
        n1.current_term = term; n1.voted_for = n2.ip_addr # N1 popiera N2
        n4.current_term = term; n4.voted_for = n3.ip_addr # N4 popiera N3

        print("-> Przetwarzanie głosów (nikt nie powinien wygrać)...")
        self.process_network()
        
        # Sprawdzenie
        has_leader = any(n.role == "leader" for n in self.nodes.values())
        if not has_leader:
            print(f"{C.OK}SUKCES: Zakleszczenie potwierdzone (Brak lidera).{C.R}")
        
        # ODKLESZCZENIE (RESOLUTION)
        print(f"\n{C.INFO}--- ROZWIĄZYWANIE ZAKLESZCZENIA (Random Timeout) ---{C.R}")
        print("Symulacja: Node 2 wylosował krótszy czas oczekiwania i wznawia elekcję z wyższym Termem.")
        
        n2.current_term += 1 # Term 6
        n2.votes_received = {n2.ip_addr}
        n2.voted_for = n2.ip_addr
        
        content = {"candidate_id": n2.ip_addr, "last_log_index": n2.get_last_log_index(), "last_log_term": n2.current_term}
        n2.send_message(self.pool, self.ips, RaftMessageType.REQUEST_VOTE, n2.current_term, content)
        
        self.process_network()
        
        if n2.role == "leader":
            print(f"{C.OK}SUKCES: Node 2 przełamał remis i został nowym Liderem (Term {n2.current_term}).{C.R}")
            self.leader_ip = n2.ip_addr
            self.print_status("STAN PO ODKLESZCZENIU")
        else:
            print(f"{C.ERR}Błąd: Nie udało się wybrać lidera.{C.R}")

    # =========================================================================
    # SCENARIUSZ 3: UPADEK LIDERA
    # =========================================================================
    def step_3_leader_crash(self):
        print(f"\n{C.H}=================================================={C.R}")
        print(f"{C.H} KROK 3: AWARIA SPRZĘTOWA LIDERA (FAILOVER) {C.R}")
        print(f"{C.H}=================================================={C.R}")
        
        old_leader_ip = self.leader_ip
        print(f"{C.ERR}!!! AWARIA: Node 2 (Lider) traci zasilanie !!!{C.R}")
        self.dead_nodes.add(old_leader_ip)
        self.leader_ip = None
        
        # Próba transakcji (powinna się nie udać)
        print("Próba zapisu do starego lidera...")
        if not self.send_transaction("DEPOSIT;A;999"):
            print(f"{C.OK}(Oczekiwane) System niedostępny.{C.R}")

        # Wybór nowego lidera (Node 3 przejmuje inicjatywę)
        print(f"\n{C.INFO}Node 3 wykrywa timeout i rozpoczyna elekcję...{C.R}")
        n3 = self.nodes[self.ips[2]] # Node 3
        n3.current_term += 1
        n3.role = "candidate"
        n3.votes_received = {n3.ip_addr}
        n3.voted_for = n3.ip_addr
        
        content = {"candidate_id": n3.ip_addr, "last_log_index": n3.get_last_log_index(), "last_log_term": n3.current_term}
        # Wysyła tylko do żywych
        targets = [ip for ip in self.ips if ip not in self.dead_nodes and ip != n3.ip_addr]
        n3.send_message(self.pool, targets, RaftMessageType.REQUEST_VOTE, n3.current_term, content)
        
        self.process_network()
        
        if n3.role == "leader":
            self.leader_ip = n3.ip_addr
            print(f"{C.OK}SUKCES FAILOVER: Node 3 jest nowym liderem.{C.R}")
            
            # Nowy lider wykonuje operacje, której Node 2 (stary lider) nie zna
            print("Wykonywanie transakcji na nowym liderze...")
            self.send_transaction("DEPOSIT;ACCOUNT_A;999.00;TX_NEW_ERA")
            self.print_status("STAN PO AWARII I FAILOVERZE")
        else:
            print(f"{C.ERR}Błąd: Failover nieudany.{C.R}")

    # =========================================================================
    # SCENARIUSZ 4: POWRÓT LIDERA
    # =========================================================================
    def step_4_leader_return(self):
        print(f"\n{C.H}=================================================={C.R}")
        print(f"{C.H} KROK 4: REANIMACJA STAREGO LIDERA (NODE 2) {C.R}")
        print(f"{C.H}=================================================={C.R}")
        
        # Node 2 wraca
        revived_ip = self.ips[1] # Node 2
        print(f"{C.WARN}Node 2 odzyskuje zasilanie i wraca do sieci.{C.R}")
        self.dead_nodes.remove(revived_ip)
        
        n2 = self.nodes[revived_ip]
        # Symulacja: Node 2 budzi się myśląc, że jest liderem starego Termu (6)
        # Ale obecny lider (Node 3) ma Term 7 lub wyższy.
        print(f"Stan Node 2 przed synchronizacją: Term {n2.current_term}, LogLen {len(n2.log.entries)}")
        
        # Node 3 (Aktualny Lider) wysyła Heartbeat (AppendEntries)
        print("Aktualny lider (Node 3) wysyła Heartbeat do Node 2...")
        n3 = self.nodes[self.leader_ip]
        
        content = {
            "entries": [], # Heartbeat
            "leader": n3.ip_addr,
            "leader_id": n3.ip_addr,
            "prev_log_index": n3.get_last_log_index(),
            "prev_log_term": n3.current_term,
            "leader_commit": n3.commit_index
        }
        n3.send_message(self.pool, [revived_ip], RaftMessageType.APPEND_ENTRIES, n3.current_term, content)
        
        # Przetwarzamy sieć
        # 1. N2 odbiera -> Widzi wyższy Term -> Zmienia się w Followera -> Ale Logi się nie zgadzają (Consistency Check fail) -> Odsyła False
        # 2. N3 odbiera False -> Zmniejsza next_index dla N2 -> Wysyła brakujące wpisy
        # 3. N2 odbiera wpisy -> Aplikuje -> Odsyła True
        print("Synchronizacja logów w toku (Consistency Check & Repair)...")
        self.process_network(cycles=15)
        
        # Weryfikacja
        if n2.role == "follower" and n2.current_term == n3.current_term:
            print(f"{C.OK}SUKCES: Node 2 zintegrowany jako Follower.{C.R}")
            
            # Sprawdźmy czy ma transakcję TX_NEW_ERA (którą przegapił jak był martwy)
            logs = [e["message"] for e in n2.log.entries]
            if any("TX_NEW_ERA" in str(msg) for msg in logs):
                print(f"{C.OK}DANE SPÓJNE: Node 2 pobrał brakującą transakcję 'TX_NEW_ERA'.{C.R}")
            else:
                print(f"{C.ERR}BŁĄD: Node 2 nie zaktualizował logów.{C.R}")
                
            self.print_status("STAN KOŃCOWY KLASTRA")
        else:
            print(f"{C.ERR}Błąd: Node 2 nie zsynchronizował się poprawnie.{C.R}")


if __name__ == "__main__":
    sim = RaftFinalSimulation()
    
    # KROK 1
    sim.step_1_normal_operations()
    input(f"\n{C.INFO}[Naciśnij ENTER, aby przejść do Zakleszczenia]{C.R}")
    
    # KROK 2
    sim.step_2_deadlock_and_resolve()
    input(f"\n{C.INFO}[Naciśnij ENTER, aby zabić Lidera]{C.R}")
    
    # KROK 3
    sim.step_3_leader_crash()
    input(f"\n{C.INFO}[Naciśnij ENTER, aby przywrócić starego Lidera]{C.R}")
    
    # KROK 4
    sim.step_4_leader_return()