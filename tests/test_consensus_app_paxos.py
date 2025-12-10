import pytest
import asyncio
from datetime import datetime
from consensus_server import ConsensusServer
from paxos_messages import PaxosMessage, PaxosMessageType

@pytest.mark.asyncio
async def test_paxos_initialization():
    """
    Sprawdza, czy węzeł Paxos inicjalizuje się poprawnie i czy działa jego log (podstawowy append).
    Odpowiednik test_add_log.
    """
    server = ConsensusServer(1, 8000, 5000, peers=[], algorithm="paxos")
    
    # Ręczne dodanie wpisu do logu (symulacja zapisu po konsensusie)
    # W Paxos ID requestu to krotka (Round, NodeID)
    # POPRAWNIE: request_number, message, timestamp
    server.node.log.append((1, 1), "DEPOSIT;KONTO_A;100", datetime.now())
    
    last_entry = server.node.log.entries[-1]
    assert last_entry["message"] == "DEPOSIT;KONTO_A;100"
    assert server.node.highest_promised_id == (0, 0)

@pytest.mark.asyncio
async def test_paxos_propose_flow():
    """
    Testuje inicjację fazy PREPARE przez propozytora.
    Odpowiednik test_raft_propose_operation.
    """
    server = ConsensusServer(1, 8000, 5000, peers=[{"ip": "127.0.0.1", "tcp_port": 5001}], algorithm="paxos")

    # Mockowanie wysyłania (nie chcemy otwierać socketów)
    sent_messages = []
    async def mock_send(ip, port, message):
        sent_messages.append(message)
    
    server.send_tcp_message = mock_send

    # Wywołujemy metodę serwera, która rozpoczyna Paxos
    operation = "TRANSFER;A;B;10"
    await server.propose_operation_paxos(operation)
    await asyncio.sleep(0.1)
    # 1. Sprawdzamy stan wewnętrzny propozytora
    # Propozytor powinien ustawić treść wiadomości, którą chce przeforsować
    assert server.node.message_content == operation
    # Powinien podbić licznik rundy (np. 1.1 dla node_id=1, round=1)
    assert server.node.proposer_round_id[1] == 1  # ID węzła
    assert server.node.proposer_round_id[0] > 0   # Runda powinna wzrosnąć

    # 2. Sprawdzamy czy wysłano PREPARE
    # Metoda propose_operation_paxos powinna wysłać PREPARE do peerów
    assert len(sent_messages) > 0
    assert sent_messages[0].message_type == PaxosMessageType.PREPARE
    assert sent_messages[0].message_content == operation

@pytest.mark.asyncio
async def test_two_nodes_paxos_prepare_promise():
    """
    Symuluje interakcję między dwoma węzłami: Proposer -> Acceptor.
    Sprawdza, czy Acceptor poprawnie składa obietnicę (PROMISE).
    Odpowiednik test_two_nodes_raft_mocked.
    """
    node1 = ConsensusServer(1, 8000, 5000, peers=[{"ip": "127.0.0.1", "tcp_port": 5001}], algorithm="paxos")
    node2 = ConsensusServer(2, 8001, 5001, peers=[{"ip": "127.0.0.1", "tcp_port": 5000}], algorithm="paxos")

    # Mockowanie sieci: Node 1 wysyła bezpośrednio do metody receive_message Node 2
    # Uwaga: PaxosNode.receive_message wymaga argumentów: message, response_pool, quorum, nodes_ips
    async def mock_send(ip, port, message):
        response_pool = []
        all_ips = [node1.ip_addr, node2.ip_addr]
        quorum = 2
        
        # Symulacja dotarcia pakietu do Node 2
        node2.node.receive_message(message, response_pool, quorum, all_ips)
        
        # (Opcjonalnie) Tutaj Node 2 wygenerowałby odpowiedź PROMISE w response_pool
        return response_pool

    node1.send_tcp_message = mock_send

    # Scenariusz: Node 1 wysyła PREPARE z rundą 5.1
    round_id_str = "5.1"
    round_tuple = (5, 1)
    msg = PaxosMessage(
        from_ip=node1.ip_addr,
        to_ip=node2.ip_addr,
        message_type=PaxosMessageType.PREPARE,
        round_identifier=round_id_str,
        message_content="SET x=99"
    )

    # Bezpośrednie wywołanie logiki odbioru na Node 2 (symulacja przyjścia pakietu)
    # Wymagane, bo mock_send w tym teście tylko definiujemy, ale wywołujemy logikę ręcznie
    response_pool = []
    node2.node.receive_message(msg, response_pool, 2, [node1.ip_addr, node2.ip_addr])

    # WERYFIKACJA:
    # 1. Czy Node 2 obiecał (Promised) tę rundę?
    assert node2.node.highest_promised_id == round_tuple

    # 2. Czy Node 2 wygenerował odpowiedź PROMISE?
    assert len(response_pool) == 1
    response = response_pool[0]
    assert response.message_type == PaxosMessageType.PROMISE
    assert response.to_ip == node1.ip_addr

    @pytest.mark.asyncio
    async def test_paxos_deadlock_prevention_logic():
        server = ConsensusServer(1, 8000, 5000, peers=[], algorithm="paxos")
        
        # 1. Blokujemy zasób używając konkretnego ID
        locked_tx_id = "AAA_TX"
        server.node.locked_accounts["KONTO_A"] = locked_tx_id
        
        # 2. Próbujemy go zająć inną transakcją (powinno się nie udać)
        success = server.node.try_lock_all("BBB_TX", ["KONTO_A"])
        assert success is False, f"Blokada nie zadziałała. Stan: {server.node.locked_accounts}"
        
        # 3. Zwalniamy zasób używając TEGO SAMEGO ID co w punkcie 1
        server.node.unlock_all(locked_tx_id) 
        
        # 4. Próbujemy ponownie nową transakcją (teraz powinno się udać)
        success_retry = server.node.try_lock_all("TX_NEW", ["KONTO_A"])
        assert success_retry is True