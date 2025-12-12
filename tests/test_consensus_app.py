# test_raft_nodes.py
import pytest
from raft_nodes import Node, Log
from raft_messages import RaftMessage, RaftMessageType

@pytest.fixture
def node():
    return Node(ip_addr="127.0.0.1", up_to_date=True, ID=1)

def test_execute_transaction_deposit(node):
    # Symulujemy commit index i apply
    node.last_applied = 0
    node.execute_transaction("DEPOSIT;KONTO_A;500.0")
    assert node.accounts['KONTO_A'] == 10500.00

def test_handle_vote_request_granted(node):
    """Głosuj TAK, jeśli nie głosowałeś i log kandydata jest aktualny."""
    msg = RaftMessage(
        from_ip="127.0.0.2", to_ip="127.0.0.1",
        message_type=RaftMessageType.REQUEST_VOTE,
        term=1,
        message_content={"candidate_id": "127.0.0.2", "last_log_index": 0, "last_log_term": 0}
    )
    pool = []
    node.current_term = 0
    
    node.receive_message(msg, pool, quorum=2, nodes_ips=["127.0.0.1", "127.0.0.2"])
    
    assert len(pool) == 1
    response = pool[0]
    assert response.message_type == RaftMessageType.VOTE
    assert response.message_content["granted"] is True
    assert node.voted_for == "127.0.0.2"

def test_become_candidate_and_start_election(node):
    initial_term = node.current_term
    last_idx, last_term = node.begin_election()
    
    assert node.role == "candidate"
    assert node.current_term == initial_term + 1
    assert node.voted_for == node.ip_addr
    assert node.ip_addr in node.votes_received

def test_append_entries_success(node):
    """Test dodawania wpisów do logu."""
    node.current_term = 1
    
    entries = [{"request_number": (1, 0), "timestamp": "...", "message": "DEPOSIT;A;10"}]
    msg = RaftMessage(
        from_ip="127.0.0.2", to_ip="127.0.0.1",
        message_type=RaftMessageType.APPEND_ENTRIES,
        term=1,
        message_content={
            "prev_log_index": -1, "prev_log_term": 0,
            "entries": entries, "leader_commit": 0
        }
    )
    pool = []
    node.receive_message(msg, pool, quorum=2, nodes_ips=[])
    
    assert pool[0].message_type == RaftMessageType.APPEND_RESPONSE
    assert pool[0].message_content["success"] is True
    
    assert len(node.log.entries) == 1
    assert node.log.entries[0]["message"] == "DEPOSIT;A;10"