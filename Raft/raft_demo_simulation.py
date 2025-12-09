import copy, time
from raft_nodes import Node
from raft_messages import RaftMessage, RaftMessageType

# ========================================================================
#  POMOCNICZE
# ========================================================================

def ips(nodes):
    return [n.ip_addr for n in nodes]

def quorum(nodes):
    return (len(nodes) // 2) + 1

def show_accounts(label, nodes):
    print(f"\n=== {label} ===")
    for n in nodes:
        print(f"Node {n.ip_addr}: {n.accounts}")

def show_logs(label, nodes):
    print(f"\n=== {label} ===")
    for n in nodes:
        print(f"Node {n.ip_addr}: log_index={n.get_last_log_index()}, commit_index={n.commit_index}")
        for i, e in enumerate(n.log.entries):
            print(f"  [{i}] term={e['request_number'][0]}  msg={e['message']}")

def deliver_all(nodes, pool):
    """Dostarcz wszystkie wiadomości i wypisz je dla czytelności."""
    while pool:
        msg = pool.pop(0)
        print(f"[MSG] {msg.from_ip} → {msg.to_ip}: {msg.message_type.name}, T={msg.term}")
        target = next(n for n in nodes if n.ip_addr == msg.to_ip)
        target.receive_message(msg, pool, quorum(nodes), ips(nodes))

# ========================================================================
#  ELECTION
# ========================================================================

def elect_leader(nodes, forced_candidate_id=None):
    # Wybieramy kandydata (domyślnie pierwszy, lub wskazany)
    candidate = nodes[0]
    if forced_candidate_id:
        candidate = next(n for n in nodes if n.ip_addr == forced_candidate_id)

    print(f"\n===========================================================")
    print(f"=== ROZPOCZĘCIE WYBORÓW (Kandydat: {candidate.ip_addr}) ===")
    print(f"===========================================================")

    # 1. Symulacja timeoutu wyborczego - węzeł staje się kandydatem
    candidate.current_term += 1
    candidate.role = "candidate"
    candidate.voted_for = candidate.ip_addr
    candidate.votes_received = {candidate.ip_addr}
    
    print(f"[KANDYDAT] {candidate.ip_addr} rozpoczyna Term {candidate.current_term}.")
    print(f"[GŁOS] {candidate.ip_addr} głosuje na siebie (Głosy: 1/{len(nodes)})")

    # 2. Generowanie wiadomości RequestVote
    pool = []
    last_idx = candidate.get_last_log_index()
    last_term = candidate.get_last_log_term()
    
    for n in nodes:
        if n.ip_addr == candidate.ip_addr: continue
        
        # Tworzymy wiadomość RequestVote
        msg = RaftMessage(
            from_ip=candidate.ip_addr,
            to_ip=n.ip_addr,
            message_type=RaftMessageType.REQUEST_VOTE,
            term=candidate.current_term,
            message_content={
                "candidate_id": candidate.ip_addr,
                "last_log_index": last_idx,
                "last_log_term": last_term
            }
        )
        pool.append(msg)

    # 3. Pętla dostarczania z wizualizacją
    while pool:
        msg = pool.pop(0)
        target = next(n for n in nodes if n.ip_addr == msg.to_ip)
        
        # Logowanie ruchu sieciowego przed dostarczeniem
        if msg.message_type == RaftMessageType.REQUEST_VOTE:
            print(f"   [SEND] {msg.from_ip} -> {msg.to_ip}: Prośba o głos (Term={msg.term}, LastLog={msg.message_content['last_log_index']})")
        
        elif msg.message_type == RaftMessageType.VOTE:
            granted = msg.message_content.get("granted")
            decision = "TAK (+1)" if granted else "NIE"
            print(f"   [RECV] {msg.from_ip} -> {msg.to_ip}: Odpowiedź? {decision}")

        # Dostarczenie wiadomości do węzła (tu dzieje się cała logika Raft)
        # Używamy tymczasowej puli, żeby przechwycić odpowiedzi wygenerowane w tym kroku
        step_pool = []
        
        prev_role = target.role if target == candidate else None
        target.receive_message(msg, step_pool, quorum(nodes), ips(nodes))
        
        # Sprawdzamy czy kandydat został liderem w tym kroku
        if target == candidate and prev_role == "candidate" and target.role == "leader":
             print(f"      !!! SUKCES! {candidate.ip_addr} zebrał większość głosów i został LIDEREM !!!")

        # Przeniesienie odpowiedzi do głównej puli
        pool.extend(step_pool)

    # Podsumowanie
    print(f"===========================================================")
    print(f"[WYNIK] Lider: {candidate.leader_id}")
    print(f"[STATYSTYKA] Kandydat {candidate.ip_addr} otrzymał {len(candidate.votes_received)} głosy: {sorted(list(candidate.votes_received))}")
    print(f"===========================================================")
    
    return candidate

# ========================================================================
#  PROPOSE (z bardzo szczegółowymi logami)
# ========================================================================

def propose(leader, nodes, operation):
    print("\n--------------------------------------------------------------------")
    print(f"[PROPOSE] Lider {leader.ip_addr} dodaje operację: {operation}")
    print("--------------------------------------------------------------------")

    # dopisujemy entry w pełnym formacie
    new_index = leader.get_last_log_index() + 1
    leader.log.append((leader.current_term, new_index), time.time(), operation)
    states_before = {n.ip_addr: copy.deepcopy(n.accounts) for n in nodes}
    
    show_logs("Logi po dodaniu na liderze", nodes)

    # rozsyłamy AppendEntries
    pool = []
    print("\n[REPLIKACJA] Lider wysyła AppendEntries")
    leader.broadcast_append_entries(pool, ips(nodes))
    deliver_all(nodes, pool)

    # czekamy aż commit będzie równy na wszystkich
    print("\n[OCZEKIWANIE] Czekam aż wszystkie węzły skomitują wpis...")
    for _ in range(20):
        if all(n.commit_index == leader.commit_index for n in nodes):
            print(">>> Wszystkie węzły dogoniły commit_index lidera.")
            break
        leader.broadcast_append_entries(pool, ips(nodes))
        deliver_all(nodes, pool)

    # APPLY
    print("\n[APPLY] Wykonywanie transakcji na wszystkich węzłach:")
    for n in nodes:
        before = states_before[n.ip_addr]
       # n.apply_committed_entries()
        print(f"Node {n.ip_addr}: PRZED={before} → PO={n.accounts}")

    show_logs("Logi po replikacji i APPLY", nodes)
    show_accounts("Stan kont po tej operacji", nodes)

# ========================================================================
#  AWARIA FOLLOWERA C
# ========================================================================

def simulate_follower_failure(leader, nodes):
    print("\n====================================================================")
    print("======================  SYMULACJA AWARII C  ========================")
    print("====================================================================")

    alive = [n for n in nodes if n.ip_addr != "C"]
    node_c = next(n for n in nodes if n.ip_addr == "C")

    print("\n[C DOWN] Węzeł C przestaje odpowiadać\n")

    # Lider dodaje entry
    new_index = leader.get_last_log_index() + 1
    leader.log.append((leader.current_term, new_index), time.time(), "DEPOSIT; KONTO_B; 300")

    states_before = {n.ip_addr: copy.deepcopy(n.accounts) for n in nodes}
    
    print("\n[Tylko A, B, D dostają AppendEntries]")
    pool = []
    leader.broadcast_append_entries(pool, ["A", "B"])
    deliver_all(alive, pool)

    print("\n[APPLY] A, B, D wykonują operację, C nie.")
    for n in alive:
        before = states_before[n.ip_addr]
        n.apply_committed_entries()
        print(f"Node {n.ip_addr}: PRZED={before} → PO={n.accounts}")

    print("\n[C nie ma wpisu]:", node_c.accounts)

    show_logs("Logi po awarii C", nodes)
    show_accounts("Stany kont po awarii C", nodes)

# ========================================================================
#  UPADek LIDERA A + wybór B + powrót A
# ========================================================================

def simulate_leader_failure(nodes):
    print("\n====================================================================")
    print("=====================  SYMULACJA UPADKU LIDERA  ====================")
    print("====================================================================")

    leader_a = next(n for n in nodes if n.ip_addr == "A")
    alive = [n for n in nodes if n.ip_addr != "A"]

    print("\n[A DOWN] Lider A upada!")

    # B zostaje liderem
    new_leader = elect_leader(alive, forced_candidate_id="B")

    print("\n[NEW LEADER] B wykonuje nową operację")
    propose(new_leader, alive, "WITHDRAW; KONTO_A; 700")

    # A wraca
    print("\n[RETURN] A wraca do klastra — musi nadrobić log")
    all_nodes = alive + [leader_a]

    states_before = {n.ip_addr: copy.deepcopy(n.accounts) for n in nodes}
    
    pool = []
    new_leader.broadcast_append_entries(pool, ips(all_nodes))
    deliver_all(all_nodes, pool)

    print("\n[APPLY] Wszystkie węzły wykonują zaległe operacje:")
    for n in all_nodes:
        before = states_before[n.ip_addr]
        n.apply_committed_entries()
        print(f"Node {n.ip_addr}: PRZED={before} → PO={n.accounts}")

    show_logs("Logi po powrocie lidera A", all_nodes)
    show_accounts("Finalny stan kont", all_nodes)

    
# ========================================================================
#  MAIN
# ========================================================================

if __name__ == "__main__":
    nodes = [
        Node("A", True, 1),
        Node("B", True, 2),
        Node("C", True, 3),
        Node("D", True, 4),
    ]

    leader = elect_leader(nodes)

    propose(leader, nodes, "DEPOSIT; KONTO_A; 2000")
    propose(leader, nodes, "WITHDRAW; KONTO_B; 1000")
    propose(leader, nodes, "TRANSFER; KONTO_A; KONTO_B; 1500")

    simulate_follower_failure(leader, nodes)
    simulate_leader_failure(nodes)