import copy
import random
import time
from typing import Dict, List

from paxos_nodes import Node
from paxos_messages import PaxosMessage, PaxosMessageType

def ips(nodes):
    return [n.ip_addr for n in nodes]

def quorum(nodes):
    return (len(nodes) // 2) + 1

def show_accounts(label, nodes):
    print(f"\n=== {label} ===")
    for n in nodes:
        print(f"Node {n.ip_addr}: {n.accounts}")

def show_paxos_state(label, nodes):
    print(f"\n=== {label} ===")
    for n in nodes:
        print(
            f"Node {n.ip_addr}: promised={n.highest_promised_id} "
            f"accepted_id={n.highest_accepted_id} accepted_value={n.accepted_value!r} "
            f"locked={n.locked_accounts}"
        )
        if n.accepted_phase_values:
            summary = ", ".join(
                [f"#{k}:({v.count})" for k, v in sorted(n.accepted_phase_values.items())]
            )
            print(f"  accepted_phase_values: {summary}")
        else:
            print("  accepted_phase_values: (empty)")

def deliver_all(nodes, pool, down_ips=None):
    """
    Dostarcza wszystkie wiadomości z puli (jak 'sieć').
    down_ips: lista węzłów 'martwych' (pakiety do nich są dropowane).
    """
    down = set(down_ips or [])
    while pool:
        msg = pool.pop(0)

        if msg.to_ip in down:
            print(f"[DROP] {msg.to_ip} DOWN -> odrzucam {msg.message_type.name} od {msg.from_ip}")
            continue

        target = next(n for n in nodes if n.ip_addr == msg.to_ip)

        target.receive_message(msg, pool, quorum(nodes), ips(nodes))

_round_counter = 0

def _next_round_id(proposer: Node):
    """Deterministyczny (i czytelny) identyfikator rundy: (inkrementalny, ID węzła)."""
    global _round_counter
    _round_counter += 1
    return (_round_counter, proposer.ID)

def propose(nodes, proposer_ip, tx_data):
    proposer = next(n for n in nodes if n.ip_addr == proposer_ip)
    round_id = _next_round_id(proposer)
    round_str = f"{round_id[0]}.{round_id[1]}"

    print("\n" + "-" * 68)
    print(f"[PROPOSE] Proposer {proposer.ip_addr} startuje rundę {round_str}")
    print(f"[PROPOSE] Dane transakcji: {tx_data}")
    print("-" * 68)

    proposer.set_new_proposal(tx_data, round_id)

    pool = []
    proposer.send_message(
        message_pool=pool,
        target_ip=ips(nodes),
        message=tx_data,
        message_type=PaxosMessageType.PREPARE,
        round_identifier=round_str,
    )

    deliver_all(nodes, pool)

    show_paxos_state("Stan Paxosa po rundzie", nodes)
    show_accounts("Konta po rundzie", nodes)

def simulate_acceptor_failure(nodes, proposer_ip, tx_data, down_ip):
    print("\n" + "=" * 76)
    print(f"[SCENARIUS] Awaria akceptora: {down_ip} nie odpowiada (pozostałe węzły muszą dać quorum)")
    print("=" * 76)

    proposer = next(n for n in nodes if n.ip_addr == proposer_ip)
    round_id = _next_round_id(proposer)
    round_str = f"{round_id[0]}.{round_id[1]}"

    pool = []
    proposer.set_new_proposal(tx_data, round_id)
    proposer.send_message(pool, ips(nodes), tx_data, PaxosMessageType.PREPARE, round_str)

    deliver_all(nodes, pool, down_ips=[down_ip])

    show_paxos_state("Stan Paxosa po awarii akceptora", nodes)
    show_accounts("Konta po awarii akceptora", nodes)

def simulate_proposer_crash_and_recovery(nodes, crashed_ip, new_proposer_ip, tx_data):
    print("\n" + "=" * 76)
    print(f"[SCENARIUS] Proposer {crashed_ip} 'odpada' po wysłaniu PREPARE; przejmuje {new_proposer_ip} z wyższą rundą")
    print("=" * 76)

    crashed = next(n for n in nodes if n.ip_addr == crashed_ip)
    # 1) crashed wysyła PREPARE, ale nie dochodzi do zakończenia (symulujemy „crash” przez drop odpowiedzi do niego)
    r1 = _next_round_id(crashed)
    r1s = f"{r1[0]}.{r1[1]}"
    crashed.set_new_proposal(tx_data, r1)

    pool = []
    crashed.send_message(pool, ips(nodes), tx_data, PaxosMessageType.PREPARE, r1s)

    # Dostarczamy, ale wszystko co wraca do crashed_ip jest dropowane -> nie zebrałby PROMISE/ACCEPT
    deliver_all(nodes, pool, down_ips=[crashed_ip])

    # 2) nowy propozytor podejmuje rundę z wyższym (inkrementalnym) numerem
    propose(nodes, new_proposer_ip, tx_data)

def run_concurrency_conflict(nodes):
    print("\n" + "="*60)
    print(" SCENARIUSZ 2: Współbieżność i Wykrywanie Zakleszczeń")
    print(" Opis: Node A i Node B próbują jednocześnie zmodyfikować KONTO_A.")
    print("="*60)
    
    # Reset stanu węzłów przed testem
    for n in nodes: 
        n.reset_paxos_state()
        n.highest_promised_id = (0, 0)
        n.highest_accepted_id = (0, 0)

    A = nodes[0]
    B = nodes[1]
    pool = []
    nodes_ips = ips(nodes)

    # Definiujemy dwie kolizyjne transakcje na tym samym koncie
    tx_A = "WITHDRAW;KONTO_A;100;TX_ID:TX_A_1"
    tx_B = "WITHDRAW;KONTO_A;200;TX_ID:TX_B_1"

    print("\n--- KROK 1: Obaj propozytorzy (A i B) wysyłają PREPARE ---")
    
    # A proponuje Runda 2.1
    A.set_new_proposal(tx_A, (2, 1))
    A.send_message(pool, nodes_ips, tx_A, PaxosMessageType.PREPARE, "2.1")
    
    # B proponuje Runda 3.2 
    B.set_new_proposal(tx_B, (3, 2))
    B.send_message(pool, nodes_ips, tx_B, PaxosMessageType.PREPARE, "3.2")

    print(f"Liczba wiadomości w sieci: {len(pool)}")
    
    # Dostarczamy PREPARE do wszystkich.
    # Ponieważ runda B (3.2) > runda A (2.1), węzły obiecały wierność B.
    deliver_all(nodes, pool)
    
    print("\n--- KROK 2: Symulacja Zakleszczenia Zasobów (Resource Lock) ---")
    
    nodes[2].locked_accounts["KONTO_A"] = "TX_A_1" 
    print(f"[SETUP] Node C ma zablokowane KONTO_A przez TX_A_1")

    msg_accept = PaxosMessage(
        from_ip=B.ip_addr, 
        to_ip=nodes[2].ip_addr,
        message_type=PaxosMessageType.ACCEPT,
        round_identifier="3.2",
        message_content=tx_B
    )
    
    print(f"[ACTION] B wysyła ACCEPT({tx_B}) do C...")
    pool = [msg_accept]
    
    deliver_all(nodes, pool)

    
    print("\n--- KROK 3: Sprawdzenie blokad ---")

    print(f"Blokady na Node C: {nodes[2].locked_accounts}")

if __name__ == "__main__":
    nodes = [
        Node("A", True, 1),
        Node("B", True, 2),
        Node("C", True, 3),
        Node("D", True, 4),
    ]

    print("\n=== START: Klaster Paxos (A,B,C,D) ===")
    show_accounts("Konta startowe", nodes)

    # Kilka transakcji 
    propose(nodes, "A", "DEPOSIT; KONTO_A; 2000; TX_ID:1")
    propose(nodes, "A", "WITHDRAW; KONTO_B; 1000; TX_ID:2")
    propose(nodes, "B", "TRANSFER; KONTO_A; KONTO_B; 1500; TX_ID:3")

    # Awaria jednego akceptora (C)
    simulate_acceptor_failure(nodes, proposer_ip="A",
                              tx_data="DEPOSIT; KONTO_B; 300; TX_ID:4",
                              down_ip="C")

    # Awaria propozytora A + przejęcie przez B
    simulate_proposer_crash_and_recovery(nodes, crashed_ip="A", new_proposer_ip="B",
                                         tx_data="WITHDRAW; KONTO_A; 250; TX_ID:5")

    run_concurrency_conflict(nodes)
    
    print("\n=== KONIEC SYMULACJI ===")
    show_accounts("Konta końcowe", nodes)
