import pytest
import asyncio
from datetime import datetime
from consensus_server import ConsensusServer

@pytest.mark.asyncio
async def test_add_log():
    server = ConsensusServer(1, 8000, 5000, peers=[], algorithm="raft")
    server.node.log.append((0, 0), datetime.now(), "SET x=1")
    last_entry = server.node.log.entries[-1]
    assert last_entry["message"] == "SET x=1"

@pytest.mark.asyncio
async def test_raft_propose_operation():
    server = ConsensusServer(1, 8000, 5000, peers=[], algorithm="raft")
    server.node.role = "leader"

    # Mock send_tcp_message so it doesn't try to open real connections
    async def dummy_send(*args, **kwargs):
        pass
    server.send_tcp_message = dummy_send

    # Directly append to the leader log as in the current implementation
    new_index = server.node.get_last_log_index() + 1
    server.node.log.append((server.node.current_term, new_index), datetime.now(), "SET x=42")

    last_entry = server.node.log.entries[-1]
    assert last_entry["message"] == "SET x=42"

@pytest.mark.asyncio
async def test_two_nodes_raft_mocked():
    node1 = ConsensusServer(1, 8000, 5000, peers=[{"ip": "127.0.0.1", "tcp_port": 5001}], algorithm="raft")
    node2 = ConsensusServer(2, 8001, 5001, peers=[{"ip": "127.0.0.1", "tcp_port": 5000}], algorithm="raft")

    node1.node.role = "leader"

    # Mock sending: directly feed messages to node2
    async def mock_send(ip, port, message):
        node2.node.receive_message(message, [], 2, [node1.ip_addr, node2.ip_addr])

    node1.send_tcp_message = mock_send

    # Append an operation to node1 log
    new_index = node1.node.get_last_log_index() + 1
    node1.node.log.append((node1.node.current_term, new_index), datetime.now(), "SET x=42")

    # Normally, you would broadcast via send_tcp_message
    # For test, we can simulate broadcasting a RaftMessage directly
    from raft_messages import RaftMessage, RaftMessageType
    msg = RaftMessage(
        from_ip=node1.ip_addr,
        to_ip=node2.ip_addr,
        message_type=RaftMessageType.APPEND_ENTRIES,
        term=node1.node.current_term,
        message_content={
            "prev_log_index": new_index - 1,
            "prev_log_term": node1.node.current_term,
            "entries": [node1.node.log.entries[-1]],
            "leader_commit": node1.node.commit_index
        }
    )
    await node1.send_tcp_message(node2.ip_addr, 5001, msg)

    # Check that node2 received the entry
    last_entry_node2 = node2.node.log.entries[-1]
    assert last_entry_node2["message"] == "SET x=42"
