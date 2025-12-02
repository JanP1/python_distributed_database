import pytest
import asyncio
from consensus_server import ConsensusServer
from raft_messages import RaftMessage, RaftMessageType

@pytest.mark.asyncio
async def test_two_nodes_raft():
    node1 = ConsensusServer(1, 8000, 5000, peers=[{"ip": "127.0.0.1", "tcp_port": 5001}], algorithm="raft")
    node2 = ConsensusServer(2, 8001, 5001, peers=[{"ip": "127.0.0.1", "tcp_port": 5000}], algorithm="raft")

    node1.node.role = "leader"

    async def mock_send(ip, port, message, *args, **kwargs):
        # Feed the RaftMessage directly to node2
        node2.node.receive_message(message, [], 2, [node2.ip_addr, node1.ip_addr])

    node1.send_tcp_message = mock_send

    await node1.propose_operation_raft("SET x=42")

    last_entry = node1.node.log.entries[-1]
    assert last_entry["message"] == "SET x=42"
