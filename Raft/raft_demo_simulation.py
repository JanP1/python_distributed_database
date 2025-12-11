import time
from raft_nodes import Node
from raft_messages import RaftMessage, RaftMessageType


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


def elect_leader(nodes):
    print("\n=== START ELECTION (A zostaje liderem) ===")

    node = nodes[0]
    node.current_term += 1
    node.role = "leader"
    node.leader_id = node.ip_addr

    pool = []
    node.become_leader(ips(nodes), pool)
    deliver_all(nodes, pool)

    print(f"=== WYBRANO LIDERA: {node.ip_addr} ===")
    return node


def propose(leader, nodes, operation):
    print("\n--------------------------------------------------------------------")
    print(f"[PROPOSE] Lider {leader.ip_addr} dodaje operację: {operation}")
    print("--------------------------------------------------------------------")

    new_index = leader.get_last_log_index() + 1
    leader.log.append((leader.current_term, new_index), time.time(), operation)

    show_logs("Logi po dodaniu na liderze", nodes)

    pool = []
    print("\n[REPLIKACJA] Lider wysyła AppendEntries")
    leader.broadcast_append_entries(pool, ips(nodes))
    deliver_all(nodes, pool)

    print("\n[OCZEKIWANIE] Czekam aż wszystkie węzły skomitują wpis...")
    for _ in range(20):
        if all(n.commit_index == leader.commit_index for n in nodes):
            print(">>> Wszystkie węzły dogoniły commit_index lidera.")
            break
        leader.broadcast_append_entries(pool, ips(nodes))
        deliver_all(nodes, pool)

    print("\n[APPLY] Wykonywanie transakcji na wszystkich węzłach:")
    for n in nodes:
        before = dict(n.accounts)
        n.apply_committed_entries()
        print(f"Node {n.ip_addr}: PRZED={before} → PO={n.accounts}")

    show_logs("Logi po replikacji i APPLY", nodes)
    show_accounts("Stan kont po tej operacji", nodes)


def simulate_follower_failure(leader, nodes):
    print("\n====================================================================")
    print("======================  SYMULACJA AWARII C  ========================")
    print("====================================================================")

    alive = [n for n in nodes if n.ip_addr != "C"]
    node_c = next(n for n in nodes if n.ip_addr == "C")

    print("\n[C DOWN] Węzeł C przestaje odpowiadać\n")

    new_index = leader.get_last_log_index() + 1
    leader.log.append((leader.current_term, new_index), time.time(), "DEPOSIT; KONTO_B; 300")

    print("\n[Tylko A i B dostają AppendEntries]")
    pool = []
    leader.broadcast_append_entries(pool, ["A", "B"])
    deliver_all(alive, pool)

    print("\n[APPLY] A i B wykonują operację, C nie.")
    for n in alive:
        before = dict(n.accounts)
        n.apply_committed_entries()
        print(f"Node {n.ip_addr}: PRZED={before} → PO={n.accounts}")

    print("\n[C nie ma wpisu]:", node_c.accounts)

    show_logs("Logi po awarii C", nodes)
    show_accounts("Stany kont po awarii C", nodes)

def simulate_leader_failure(nodes):
    print("\n====================================================================")
    print("=====================  SYMULACJA UPADKU LIDERA  ====================")
    print("====================================================================")

    leader_a = next(n for n in nodes if n.ip_addr == "A")
    alive = [n for n in nodes if n.ip_addr != "A"]

    print("\n[A DOWN] Lider A upada!")

    new_leader = elect_leader(alive)

    print("\n[NEW LEADER] B wykonuje nową operację")
    propose(new_leader, alive, "WITHDRAW; KONTO_A; 700")

    print("\n[RETURN] A wraca do klastra — musi nadrobić log")
    all_nodes = alive + [leader_a]

    pool = []
    new_leader.broadcast_append_entries(pool, ips(all_nodes))
    deliver_all(all_nodes, pool)

    print("\n[APPLY] Wszystkie węzły wykonują zaległe operacje:")
    for n in all_nodes:
        before = dict(n.accounts)
        n.apply_committed_entries()
        print(f"Node {n.ip_addr}: PRZED={before} → PO={n.accounts}")

    show_logs("Logi po powrocie lidera A", all_nodes)
    show_accounts("Finalny stan kont", all_nodes)

if __name__ == "__main__":
    nodes = [
        Node("A", True, 1),
        Node("B", True, 2),
        Node("C", True, 3),
    ]

    leader = elect_leader(nodes)

    propose(leader, nodes, "DEPOSIT; KONTO_A; 2000")
    propose(leader, nodes, "WITHDRAW; KONTO_B; 1000")
    propose(leader, nodes, "TRANSFER; KONTO_A; KONTO_B; 1500")

    simulate_follower_failure(leader, nodes)
    simulate_leader_failure(nodes)
