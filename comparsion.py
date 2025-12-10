import asyncio
import time
import random
import statistics
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Dict, List, Any
import numpy as np

# Importy z Twoich plików
from consensus_server import ConsensusServer
try:
    from raft_messages import RaftMessage
    from paxos_messages import PaxosMessage
except ImportError:
    pass

# ============================================================
# KONFIGURACJA SYMULACJI
# ============================================================
NUM_NODES = 4
NUM_OPERATIONS = 20      
NUM_TRIALS = 3
NETWORK_DELAY = (0.005, 0.02) # Nieco większe opóźnienie, by wykresy były czytelne

# ============================================================
# KLASA SYMULUJĄCA SIEĆ (MOCK)
# ============================================================
class MockNetwork:
    def __init__(self):
        self.message_count = 0
        self.nodes: Dict[str, ConsensusServer] = {}

    def register_node(self, node: ConsensusServer):
        self.nodes[node.ip_addr] = node

    async def send(self, from_ip, to_ip, message):
        self.message_count += 1
        await asyncio.sleep(random.uniform(*NETWORK_DELAY))
        
        target = self.nodes.get(to_ip)
        if not target: return

        response_pool = []
        all_ips = list(self.nodes.keys())
        quorum = (len(all_ips) // 2) + 1
        
        if target.algorithm == "raft":
            target.node.receive_message(message, response_pool, quorum, all_ips)
        else:
            target.node.receive_message(message, response_pool, quorum, all_ips)

        for resp in response_pool:
            asyncio.create_task(self.send(resp.from_ip, resp.to_ip, resp))

# ============================================================
# POMOCNICZE FUNKCJE
# ============================================================
async def external_paxos_proposal(server: ConsensusServer, operation: str, network: MockNetwork):
    """
    Zewnętrzna funkcja propozycji dla Paxos, która CZEKA na wysłanie pakietów.
    Zapewnia sprawiedliwe porównanie z Raftem.
    """
    # 1. Logika propozytora (z Twojego paxos_nodes.py)
    # PaxosNode zazwyczaj potrzebuje inicjalizacji rundy
    # Symulujemy logikę: server.propose_operation_paxos, ale z await na network.send
    
    # Inkrementacja rundy (logika z Twojego paxos_nodes.py)
    # Zakładamy, że to początek nowej propozycji
    # (W uproszczeniu wywołujemy logikę przygotowania wiadomości PREPARE)
    
    # Musimy ręcznie wygenerować wiadomości PREPARE, żeby móc na nie poczekać
    from paxos_messages import PaxosMessageType # Upewnij się, że import działa
    
    # Inkrementacja licznika rund w węźle (prosta symulacja, bo nie mamy dostępu do prywatnych pól)
    # W Twoim kodzie server.node.propose_operation_paxos robi to automatycznie,
    # ale używa create_task. Tutaj musimy to zrobić ręcznie:
    
    # a) Przygotowanie danych
    server.node.message_content = operation
    # Podbijamy rundę (np. o 1)
    current_round, node_id = server.node.proposer_round_id
    next_round = (current_round + 1, server.node_id)
    server.node.proposer_round_id = next_round
    
    round_str = f"{next_round[0]}.{next_round[1]}"
    
    # b) Generowanie wiadomości
    msg_pool = []
    all_ips = list(network.nodes.keys())
    
    # W paxos_nodes.py metoda send_message dodaje do poola
    # Wywołujemy ją dla każdego peera
    server.node.send_message(msg_pool, all_ips, operation, PaxosMessageType.PREPARE, round_str)
    
    # c) Wysyłka z oczekiwaniem (AWAIT) - to jest klucz do ujednolicenia!
    tasks = []
    for msg in msg_pool:
        # Pomijamy wysyłanie do samego siebie w sieci (obsłużone lokalnie w receive), 
        # ale w mocku wysyłamy wszystko
        tasks.append(network.send(msg.from_ip, msg.to_ip, msg))
    
    if tasks:
        await asyncio.gather(*tasks)
        
    return True

async def external_raft_proposal(server: ConsensusServer, operation: str, network: MockNetwork):
    if server.node.role != "leader": return False
    
    new_index = server.node.get_last_log_index() + 1
    server.node.log.append((server.node.current_term, new_index), datetime.now(), operation)

    msg_pool = []
    all_ips = list(network.nodes.keys())
    if hasattr(server.node, 'broadcast_append_entries'):
        server.node.broadcast_append_entries(msg_pool, all_ips)

    tasks = [network.send(msg.from_ip, msg.to_ip, msg) for msg in msg_pool]
    if tasks: await asyncio.gather(*tasks)
    return True

async def setup_cluster(algorithm: str, network: MockNetwork):
    nodes = []
    ips = [f"127.0.0.{i+1}" for i in range(NUM_NODES)]
    for i in range(NUM_NODES):
        peers = [{"ip": ip, "tcp_port": 5000} for ip in ips if ip != ips[i]]
        server = ConsensusServer(i+1, 8000+i, 5000, peers, algorithm=algorithm)
        server.ip_addr = ips[i]
        server.node.ip_addr = ips[i] 
        server.node.ID = i + 1
        
        async def mock_send_wrapper(ip, port, message, _self_ip=server.ip_addr): 
            await network.send(_self_ip, ip, message)
        server.send_tcp_message = mock_send_wrapper
        network.register_node(server)
        nodes.append(server)
    return nodes

# ============================================================
# BENCHMARK ENGINE
# ============================================================

async def run_benchmark(algorithm: str):
    network = MockNetwork()
    nodes = await setup_cluster(algorithm, network)
    latencies = []
    
    print(f"--- Testowanie: {algorithm.upper()} ---")

    if algorithm == "raft":
        await nodes[0].start_election_raft()
        for _ in range(15):
            await asyncio.sleep(0.1)
            leader = next((n for n in nodes if n.node.role == "leader"), None)
            if leader: break
        if not leader: return [], 0
        proposer = leader
    else:
        proposer = nodes[0]

    network.message_count = 0
    
    for i in range(NUM_OPERATIONS):
        op_data = f"TX_{i};ACC_A;10"
        start = time.perf_counter()
        
        if algorithm == "raft":
            success = await external_raft_proposal(proposer, op_data, network)
            if not success:
                proposer = next((n for n in nodes if n.node.role == "leader"), proposer)
                await external_raft_proposal(proposer, op_data, network)
            await asyncio.sleep(0.05) 
        else: # Paxos
            # Używamy nowej funkcji zewnętrznej, która CZEKA na sieć
            await external_paxos_proposal(proposer, op_data, network)
            # Czekamy na konsensus (Prepare -> Promise -> Accept -> Accepted)
            # Paxos ma 2 rundy, więc czekamy trochę dłużej niż w Rafcie
            await asyncio.sleep(0.05 + NETWORK_DELAY[1]*2)

        latencies.append((time.perf_counter() - start) * 1000)

    return latencies, network.message_count

# ============================================================
# WIZUALIZACJA (NOWA SEKCJA)
# ============================================================
def generate_plots(raw_data):
    """Generuje proste wykresy: Słupkowy (Latencja), Pudełkowy (Stabilność), Słupkowy (Wiadomości)."""
    print("\nGenerowanie podstawowych wykresów...")
    
    # Pobranie danych
    raft_lats = raw_data["raft"]["lats"]
    paxos_lats = raw_data["paxos"]["lats"]
    
    raft_msgs = raw_data["raft"]["msgs"]
    paxos_msgs = raw_data["paxos"]["msgs"]

    # Obliczenia
    # 1. Średnia latencja
    avg_lat = [statistics.mean(raft_lats), statistics.mean(paxos_lats)]
    
    # 2. Średnia liczba wiadomości na jedną operację
    # (suma wszystkich wiadomości w próbach / (liczba prób * liczba operacji))
    total_ops_performed = len(raft_lats) # liczba wszystkich zmierzonych operacji
    avg_msgs = [sum(raft_msgs) / total_ops_performed, sum(paxos_msgs) / total_ops_performed]

    # Konfiguracja: 3 wykresy obok siebie
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 5))
    colors = ['#4CAF50', '#FF9800'] # Zielony (Raft), Pomarańczowy (Paxos)
    labels = ['Raft', 'Paxos']

    # --- WYKRES 1: Średnia Latencja (Słupkowy) ---
    # Najprostszy sposób pokazania "kto jest szybszy"
    bars1 = ax1.bar(labels, avg_lat, color=colors, alpha=0.8)
    ax1.set_title('Średnia Latencja (Szybkość)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Czas (ms)')
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    ax1.bar_label(bars1, fmt='%.1f ms', padding=3)

    # --- WYKRES 2: Rozkład Latencji (Pudełkowy / Box Plot) ---
    # Zastępuje Violin Plot. Pudełko = typowy zakres, Wąsy = odchylenia.
    # Małe pudełko = stabilnie. Duże pudełko = niestabilnie.
    bplot = ax2.boxplot([raft_lats, paxos_lats], labels=labels, patch_artist=True, widths=0.5)
    ax2.set_title('Stabilność (Rozkład wyników)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Czas (ms)')
    ax2.grid(axis='y', linestyle='--', alpha=0.5)
    
    # Kolorowanie pudełek
    for patch, color in zip(bplot['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    # --- WYKRES 3: Złożoność Sieciowa (Słupkowy) ---
    # Zastępuje CDF. Pokazuje "ile to kosztuje sieć".
    bars2 = ax3.bar(labels, avg_msgs, color=colors, alpha=0.8)
    ax3.set_title('Złożoność (Liczba pakietów na operację)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Liczba wiadomości')
    ax3.grid(axis='y', linestyle='--', alpha=0.5)
    ax3.bar_label(bars2, fmt='%.1f', padding=3)

    # Zapis do pliku
    plt.suptitle(f'Porównanie wydajności: Raft vs Paxos', fontsize=16)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig('comparison_plots_basic.png')
    print("Wykresy zapisano w pliku: comparison_plots_basic.png")

# ============================================================
# MAIN
# ============================================================

async def main():
    # Struktura do przechowywania surowych danych dla wykresów
    raw_data = {
        "raft": {"lats": [], "msgs": []},
        "paxos": {"lats": [], "msgs": []}
    }
    
    results_summary = []

    for algo in ["raft", "paxos"]:
        algo_lats = []
        algo_msgs = []
        
        for _ in range(NUM_TRIALS):
            lats, msgs = await run_benchmark(algo)
            if lats:
                algo_lats.extend(lats)
                algo_msgs.append(msgs)
        
        # Zapisujemy surowe dane
        raw_data[algo]["lats"] = algo_lats
        raw_data[algo]["msgs"] = algo_msgs

        if algo_lats:
            avg_lat = statistics.mean(algo_lats)
            std_lat = statistics.stdev(algo_lats) if len(algo_lats) > 1 else 0
            avg_msg = statistics.mean(algo_msgs) / NUM_OPERATIONS
            
            results_summary.append({
                "Algorytm": algo.upper(),
                "Latencja (ms)": round(avg_lat, 2),
                "Odchylenie (ms)": round(std_lat, 2),
                "Msg/Op": round(avg_msg, 2)
            })

    print("\n\n=== TABELA WYNIKÓW ===")
    if results_summary:
        df = pd.DataFrame(results_summary)
        print(df.to_string(index=False))
        
        # Generowanie wykresów
        generate_plots(raw_data)
    else:
        print("Brak wyników do wyświetlenia.")

if __name__ == "__main__":
    asyncio.run(main())