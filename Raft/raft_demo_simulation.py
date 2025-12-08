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

# --- KONFIGURACJA KOLORÓW ---
class C:
    H = '\033[95m'   # Header
    OK = '\033[92m'  # Success/Green
    WARN = '\033[93m' # Warning/Yellow
    ERR = '\033[91m' # Error/Red
    BLUE = '\033[94m'
    R = '\033[0m'    # Reset

class RaftAppSimulation:
    def __init__(self):
        print(f"{C.H}=== SYMULACJA APLIKACJI BANKOWEJ NA ALGORYTMIE RAFT ==={C.R}")
        
        # Konfiguracja 4 węzłów
        self.ips = ["192.168.1.10", "192.168.1.11", "192.168.1.12", "192.168.1.14"]
        self.nodes = {}
        
        for i, ip in enumerate(self.ips):
            # Tworzymy węzły z pustym loggerem (żeby nie śmiecić w konsoli)
            self.nodes[ip] = Node(ip, True, i + 1, logger=lambda m, l: None)

        self.pool = []
        self.leader_ip = None
        self.step = 0

    def print_balances(self):
        """Wyświetla stan kont na wszystkich węzłach, by pokazać spójność danych."""
        print(f"\n{C.BLUE}--- AKTUALNY STAN KONT (REPLIKACJA) ---{C.R}")
        for ip in self.ips:
            n = self.nodes[ip]
            # Formatowanie: Node 1: A=10000, B=5000
            print(f"Node {n.ID:<2} | A: {n.accounts['KONTO_A']:.2f} | B: {n.accounts['KONTO_B']:.2f} | LogIndex: {n.get_last_log_index()}")
        print("-" * 60)

    def process_network(self, cycles=5):
        """Symuluje przepływ wiadomości w sieci przez kilka cykli."""
        for _ in range(cycles):
            next_pool = []
            if not self.pool: break

            for msg in self.pool:
                target = self.nodes.get(msg.to_ip)
                if target:
                    # Symulacja odbioru (Quorum = 3 dla 4 węzłów)
                    target.receive_message(msg, next_pool, 3, self.ips)
            
            self.pool = next_pool
            # time.sleep(0.1) # Odkomentuj dla spowolnienia

    def propose_transaction(self, operation_str):
        """Wysyła transakcję do lidera i propaguje ją w sieci."""
        leader = self.nodes.get(self.leader_ip)
        if not leader or leader.role != "leader":
            print(f"{C.ERR}BŁĄD: Brak aktywnego lidera do przetworzenia transakcji!{C.R}")
            return

        print(f"\n{C.H}>>> KLIENT WYSYŁA: {operation_str}{C.R}")
        
        # 1. Lider dodaje wpis do swojego logu
        new_index = leader.get_last_log_index() + 1
        leader.log.append((leader.current_term, new_index), "NOW", operation_str)
        
        # 2. Lider tworzy wiadomość AppendEntries
        content = {
            "entries": [leader.log.entries[-1]],
            "leader": leader.ip_addr,
            "leader_id": leader.ip_addr,
            "prev_log_index": new_index - 1,
            "prev_log_term": leader.current_term, # Uproszczenie
            "leader_commit": leader.commit_index
        }
        
        # 3. Rozsyłanie do sieci
        leader.send_message(self.pool, self.ips, RaftMessageType.APPEND_ENTRIES, leader.current_term, content)
        
        # 4. Przetwarzanie sieci (Followerzy -> Lider -> Commit -> Followerzy)
        # Potrzebujemy kilku cykli: Request -> Response -> Commit Index Update
        self.process_network(cycles=10) 

    # --- SCENARIUSZE ---

    def run_election(self):
        print(f"\n{C.WARN}[KROK 1] Wybory lidera (Node 1 startuje){C.R}")
        n1 = self.nodes[self.ips[0]]
        n1.current_term = 1
        n1.role = "candidate"
        n1.votes_received = {n1.ip_addr}
        n1.voted_for = n1.ip_addr
        
        # Wysyła RequestVote
        content = {"candidate_id": n1.ip_addr, "last_log_index": -1, "last_log_term": 0}
        n1.send_message(self.pool, [ip for ip in self.ips if ip != n1.ip_addr], RaftMessageType.REQUEST_VOTE, 1, content)
        
        self.process_network(cycles=5)
        
        if n1.role == "leader":
            print(f"{C.OK}SUKCES: Node 1 został liderem.{C.R}")
            self.leader_ip = n1.ip_addr
        else:
            print(f"{C.ERR}BŁĄD: Elekcja nie powiodła się.{C.R}")

    def run_deposit(self):
        print(f"\n{C.WARN}[KROK 2] Wpłata (DEPOSIT 500.00 na KONTO_A){C.R}")
        # Format zgodny z Twoim kodem: DEPOSIT;KONTO;KWOTA;ID
        op = "DEPOSIT;KONTO_A;500.00;TX_ID:101"
        self.propose_transaction(op)
        self.print_balances()

    def run_withdraw(self):
        print(f"\n{C.WARN}[KROK 3] Wypłata (WITHDRAW 200.00 z KONTO_B){C.R}")
        op = "WITHDRAW;KONTO_B;200.00;TX_ID:102"
        self.propose_transaction(op)
        self.print_balances()

    def run_transfer(self):
        print(f"\n{C.WARN}[KROK 4] Przelew (TRANSFER 1000.00 z A do B){C.R}")
        # Format: TRANSFER;ZRODLO;CEL;KWOTA;ID
        op = "TRANSFER;KONTO_A;KONTO_B;1000.00;TX_ID:103"
        self.propose_transaction(op)
        self.print_balances()

    def run_deadlock_simulation(self):
        print(f"\n{C.ERR}=================================================={C.R}")
        print(f"{C.ERR}       [KROK 5] SYMULACJA ZAKLESZCZENIA (SPLIT VOTE)      {C.R}")
        print(f"{C.ERR}=================================================={C.R}")
        print("Opis: Node 2 i Node 3 rozpoczynają elekcję W TYM SAMYM MOMENCIE.")
        print("Oba głosują na siebie. Głosy reszty sieci się rozkładają.")
        print("Efekt: Brak lidera -> System nie może przetwarzać transakcji.")

        # Resetujemy kolejkę wiadomości
        self.pool = []
        
        # Wymuszamy sytuację patową
        term = 10
        n2 = self.nodes[self.ips[1]]
        n3 = self.nodes[self.ips[2]]
        
        # Obydwa wchodzą w rolę kandydata
        for n in [n2, n3]:
            n.role = "candidate"
            n.current_term = term
            n.votes_received = {n.ip_addr} # Głosuje na siebie
            n.voted_for = n.ip_addr
            
        # --- POPRAWKA: Ręcznie ustawiamy głosy pozostałych węzłów ---
        # Wymuszamy remis 2 vs 2
        
        # Node 1 zagłosuje na Node 2
        n1 = self.nodes[self.ips[0]]
        n1.role = "follower"  
        n1.leader_id = None
        
        n1.current_term = term
        n1.voted_for = n2.ip_addr
        
        # Node 4 zagłosuje na Node 3
        n4 = self.nodes[self.ips[3]]
        n4.current_term = term
        n4.voted_for = n3.ip_addr

        # Teraz kandydaci wysyłają prośby, ale nikt nie zmieni głosu,
        # bo voted_for jest już ustawione na ten Term.
        for n in [n2, n3]:
            content = {
                "candidate_id": n.ip_addr, 
                "last_log_index": n.get_last_log_index(), 
                "last_log_term": n.current_term
            }
            n.send_message(self.pool, self.ips, RaftMessageType.REQUEST_VOTE, term, content)

        print(f"\n{C.BLUE}Sieć przetwarza głosy...{C.R}")
        self.process_network(cycles=6)

        # Sprawdzamy wynik
        print(f"\n{C.H}WYNIK ZAKLESZCZENIA:{C.R}")
        has_leader = False
        for n in self.nodes.values():
            color = C.ERR if n.role == "candidate" else C.R
            print(f"Node {n.ID} Role: {color}{n.role.upper()}{C.R} (Term: {n.current_term}, VotedFor: {n.voted_for})")
            if n.role == "leader": has_leader = True

        if not has_leader:
            print(f"\n{C.ERR}>>> ZAKLESZCZENIE POTWIERDZONE: Brak lidera. System zatrzymany. <<<{C.R}")
            print(f"Próba wykonania transakcji teraz zakończyłaby się błędem.")
        
        # Próba transakcji w czasie awarii
        print(f"\nPróba wysłania przelewu w trakcie awarii...")
        self.propose_transaction("TRANSFER;KONTO_A;KONTO_B;100.00")


if __name__ == "__main__":
    sim = RaftAppSimulation()
    
    # 1. Pokaż stan początkowy (powinno być 10000 i 5000)
    sim.print_balances()
    
    # 2. Wybierz lidera
    sim.run_election()
    
    # 3. Wykonaj operacje biznesowe
    sim.run_deposit()
    sim.run_withdraw()
    sim.run_transfer()
    
    input(f"\n{C.H}[Naciśnij ENTER, aby wywołać awarię/zakleszczenie]{C.R}")
    
    # 4. Wywołaj zakleszczenie
    sim.run_deadlock_simulation()