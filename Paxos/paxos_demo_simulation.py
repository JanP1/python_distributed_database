import copy
import random
import time
from typing import Dict, List

from paxos_nodes import Node
from paxos_messages import PaxosMessage, PaxosMessageType

# ============================================================
#  POMOCNICZE (jak w raft_simulation)
# ============================================================

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
        # Najprościej: podsumowanie „ile razy” dana wartość była policzona w fazie ACCEPTED
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
        print(f"[MSG] {msg.from_ip} -> {msg.to_ip}  {msg.message_type.name}  (round={msg.round_identifier})")

        # Każde receive_message może dorzucić odpowiedzi do 'pool'
        target.receive_message(msg, pool, quorum(nodes), ips(nodes))

# ============================================================
#  PAXOS: PROPOZYCJA (PREPARE -> PROMISE -> ACCEPT -> ACCEPTED)
# ============================================================

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

    # Proposer przygotowuje propozycję (zgodnie z Twoją implementacją)
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

# ============================================================
#  AWARIA AKCEPTORA (np. C nie odpowiada) – nadal powinno działać przy quorum
# ============================================================

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

    # Tu „sieć” ignoruje pakiety do down_ip
    deliver_all(nodes, pool, down_ips=[down_ip])

    show_paxos_state("Stan Paxosa po awarii akceptora", nodes)
    show_accounts("Konta po awarii akceptora", nodes)

# ============================================================
#  AWARIA PROPOZERA + PRZEJĘCIE RUNDY PRZEZ INNY WĘZEŁ (wyższy round_id)
# ============================================================

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


def run_round_7_deadlock(nodes: List[Node]):
    print("\n" + "=" * 80)
    print("   SCENARIUSZ Runda 7: DEADLOCK / LIVELOCK (Duelling Proposers)")
    print("   Opis: Dwa węzły (A i B) próbują zatwierdzić transakcje jednocześnie.")
    print("   Każdy z nich podbija numer rundy, unieważniając poprzednią ofertę drugiego.")
    print("=" * 80)

    A, B, C, D = nodes
    pool = []
    nodes_ips = ips(nodes)

    # Funkcja pomocnicza do filtrowania i dostarczania konkretnych typów wiadomości
    def deliver_only(message_type_filter, limit=None):
        delivered_count = 0
        to_remove = []
        # Kopiujemy listę, by bezpiecznie modyfikować pool
        for msg in pool[:]:
            if msg.message_type == message_type_filter:
                target = next(n for n in nodes if n.ip_addr == msg.to_ip)
                # Symulujemy dostarczenie
                print(f"[LIVELOCK] {msg.from_ip} -> {msg.to_ip}: {msg.message_type.name} ID:{msg.round_identifier}")
                target.receive_message(msg, pool, quorum(nodes), nodes_ips)
                to_remove.append(msg)
                delivered_count += 1
                if limit and delivered_count >= limit:
                    break
        for msg in to_remove:
            pool.remove(msg)

    # --- KROK 1: Propozytor A rozpoczyna RUNDĘ 10 ---
    print("\n>>>A wysyła PREPARE (10.1)")
    round_a = (10, 1) # ID: 10, Node: 1
    A.set_new_proposal("DEPOSIT; KONTO_A; 100; TX_ID:6", round_a)
    A.send_message(pool, nodes_ips, A.message_content, PaxosMessageType.PREPARE, "10.1")
    
    # Dostarczamy tylko PREPARE od A. Węzły obiecują (PROMISE) rundę 10.1.
    # W poolu pojawiają się wiadomości PROMISE dla A.
    deliver_only(PaxosMessageType.PREPARE)

    # --- KROK 2: Propozytor B wchodzi w słowo z RUNDĄ 11 ---
    # Zanim A zdążył odebrać swoje PROMISE i wysłać ACCEPT, B rozpoczyna nową rundę.
    print("\n>>> B 'wchodzi w słowo' wysyłając PREPARE (11.2)")
    round_b = (11, 2) # ID: 11, Node: 2
    B.set_new_proposal("WITHDRAW; KONTO_B; 50; TX_ID:7", round_b)
    B.send_message(pool, nodes_ips, B.message_content, PaxosMessageType.PREPARE, "11.2")

    # Dostarczamy PREPARE od B. Węzły aktualizują highest_promised_id na 11.2.
    # W poolu pojawiają się wiadomości PROMISE dla B.
    deliver_only(PaxosMessageType.PREPARE)

    show_paxos_state("Stan po PREPARE obu węzłów (obiecana runda B)", nodes)

    # --- KROK 3: A próbuje sfinalizować (ACCEPT), ale jego runda jest już stara ---
    print("\n>>>A odbiera PROMISE i wysyła ACCEPT (10.1)")
    # Dostarczamy PROMISE do A. A widzi quorum i wysyła ACCEPT (10.1).
    deliver_only(PaxosMessageType.PROMISE) 
    
    print("\n>>>Węzły odrzucają ACCEPT od A (bo obiecały już 11.2)")
    # Dostarczamy ACCEPT od A. Węzły odrzucają, bo 10.1 < 11.2
    deliver_only(PaxosMessageType.ACCEPT)

    # --- KROK 5: B próbuje sfinalizować, ale A się nie poddaje i podbija stawkę ---
    # Symulujemy sytuację, gdzie A po odrzuceniu natychmiast ponawia próbę z wyższym numerem
    print("\n>>>A reaguje na porażkę i startuje wyższą RUNDĘ 12 (przed sukcesem B)")
    round_a_new = (12, 1)
    A.set_new_proposal("DEPOSIT; KONTO_A; 100; TX_ID:6", round_a_new)
    A.send_message(pool, nodes_ips, A.message_content, PaxosMessageType.PREPARE, "12.1")
    
    # Węzły dostają PREPARE 12.1 -> aktualizują obietnicę na 12.1
    deliver_only(PaxosMessageType.PREPARE)

    print("\n>>>B odbiera swoje PROMISE i wysyła ACCEPT (11.2)")
    # B myśli, że ma zgodę (zebrał PROMISE z kroku 2), wysyła ACCEPT 11.2
    # Uwaga: w realnej sieci te wiadomości mogły wisieć w kolejce
    deliver_only(PaxosMessageType.PROMISE) # To wyzwoli ACCEPT od B (jeśli są w poolu jeszcze PROMISE dla B)

    print("\n>>>Węzły odrzucają ACCEPT od B (bo obiecały już 12.1)")
    deliver_only(PaxosMessageType.ACCEPT)

    print("\nŻadna transakcja nie przeszła.")
    show_paxos_state("Stan końcowy symulacji Deadlocka", nodes)

if __name__ == "__main__":
    nodes = [
        Node("A", True, 1),
        Node("B", True, 2),
        Node("C", True, 3),
        Node("D", True, 4),
    ]

    print("\n=== START: Klaster Paxos (A,B,C,D) ===")
    show_accounts("Konta startowe", nodes)

    # Kilka transakcji „po kolei”
    propose(nodes, "A", "DEPOSIT; KONTO_A; 2000; TX_ID:1")
    propose(nodes, "A", "WITHDRAW; KONTO_B; 1000; TX_ID:2")
    propose(nodes, "B", "TRANSFER; KONTO_A; KONTO_B; 1500; TX_ID:3")

    # Awaria jednego akceptora (C) — przy 3 węzłach quorum to 2
    simulate_acceptor_failure(nodes, proposer_ip="A",
                              tx_data="DEPOSIT; KONTO_B; 300; TX_ID:4",
                              down_ip="C")

    # Awaria propozytora A + przejęcie przez B
    simulate_proposer_crash_and_recovery(nodes, crashed_ip="A", new_proposer_ip="B",
                                         tx_data="WITHDRAW; KONTO_A; 250; TX_ID:5")
    
    run_round_7_deadlock(nodes)

    print("\n=== KONIEC SYMULACJI ===")
    show_accounts("Konta końcowe", nodes)
