import pytest
import asyncio
from datetime import datetime
from consensus_server import ConsensusServer

@pytest.mark.asyncio
async def test_add_log():
    server = ConsensusServer(1, 8000, 5000, peers=[], algorithm="raft")
    server.node.log.append((0, 0), datetime.now(), "SET x=1")
    assert server.node.log.entries[-1]["message"] == "SET x=1"

@pytest.mark.asyncio
async def test_raft_propose_operation():
    server = ConsensusServer(1, 8000, 5000, peers=[], algorithm="raft")
    server.node.role = "leader"

    async def dummy_send(ip=None, port=None, message=None, *args, **kwargs):
        pass

    server.send_tcp_message = dummy_send

    await server.propose_operation_raft("SET x=1")

    last_entry = server.node.log.entries[-1]
    assert isinstance(last_entry, dict)
    assert last_entry["message"] == "SET x=1"
