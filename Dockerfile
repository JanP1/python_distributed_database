# Dockerfile for Unified Consensus Node (Raft/Paxos)
FROM python:3.12-slim

WORKDIR /app

# Copy Raft implementation files
COPY Raft/raft_messages.py ./Raft/
COPY Raft/raft_nodes.py ./Raft/

# Copy Paxos implementation files
COPY Paxos/paxos_messages.py ./Paxos/
COPY Paxos/paxos_nodes.py ./Paxos/

# Copy unified server
COPY consensus_server.py .

# Expose ports
# HTTP REST API port (8000-8002 for nodes 1-3)
EXPOSE 8000
# TCP consensus communication port (5000-5002 for nodes 1-3)
EXPOSE 5000

# Run the consensus server
CMD ["python", "-u", "consensus_server.py"]
