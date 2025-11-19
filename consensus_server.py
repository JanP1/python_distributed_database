"""
Unified Consensus Server supporting both Paxos and Raft algorithms.
Each server listens on HTTP for client requests and TCP for inter-node consensus messages.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

# Add algorithm directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Raft"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Paxos"))


class ConsensusServer:
    def __init__(
        self,
        node_id: int,
        http_port: int,
        tcp_port: int,
        peers: List[Dict[str, Any]],
        algorithm: str = "raft",
    ):
        """
        Initialize Consensus server.

        Args:
            node_id: Unique identifier for this node
            http_port: Port for HTTP REST API
            tcp_port: Port for TCP consensus communication
            peers: List of peer nodes [{"ip": "172.20.0.2", "tcp_port": 5001}, ...]
            algorithm: "raft" or "paxos"
        """
        self.node_id = node_id
        self.http_port = http_port
        self.tcp_port = tcp_port
        self.peers = peers
        self.algorithm = algorithm.lower()
        self.ip_addr = self.get_own_ip()

        # Initialize appropriate node based on algorithm
        if self.algorithm == "raft":
            from raft_messages import RaftMessage, RaftMessageType
            from raft_nodes import Node as RaftNode

            self.node = RaftNode(self.ip_addr, True, node_id)
            self.MessageType = RaftMessageType
            self.Message = RaftMessage
        elif self.algorithm == "paxos":
            from paxos_messages import PaxosMessage, PaxosMessageType
            from paxos_nodes import Node as PaxosNode

            self.node = PaxosNode(self.ip_addr, True, node_id)
            self.MessageType = PaxosMessageType
            self.Message = PaxosMessage
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        # Consensus logs for UI display
        self.consensus_logs: List[Dict[str, Any]] = []

        self.add_log(f"Node initialized with {self.algorithm.upper()}", "INFO")
        print(
            f"[Node {self.node_id}] Initialized with {self.algorithm.upper()} at {self.ip_addr}:{self.tcp_port}"
        )
        print(f"[Node {self.node_id}] HTTP API on port {self.http_port}")
        print(f"[Node {self.node_id}] Peers: {self.peers}")

    def get_own_ip(self) -> str:
        """Get own IP address from environment or use localhost."""
        return os.getenv("NODE_IP", "127.0.0.1")

    def add_log(self, message: str, level: str = "INFO"):
        """Add consensus log entry for UI display."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "node_id": self.node_id,
            "level": level,
            "message": message,
            "algorithm": self.algorithm,
        }
        self.consensus_logs.append(log_entry)
        # Keep only last 100 logs to avoid memory issues
        if len(self.consensus_logs) > 100:
            self.consensus_logs.pop(0)

    async def reinitialize_node(self):
        """Reinitialize node with new algorithm."""
        print(f"[Node {self.node_id}] Switching to {self.algorithm.upper()} algorithm")

        if self.algorithm == "raft":
            from raft_messages import RaftMessage, RaftMessageType
            from raft_nodes import Node as RaftNode

            self.node = RaftNode(self.ip_addr, True, self.node_id)
            self.MessageType = RaftMessageType
            self.Message = RaftMessage

            # Auto-start election for Node 1, or delayed for others
            if self.node_id == 1:
                asyncio.create_task(self._delayed_election(0.5))
            else:
                asyncio.create_task(self._delayed_election(1.5))

        elif self.algorithm == "paxos":
            from paxos_messages import PaxosMessage, PaxosMessageType
            from paxos_nodes import Node as PaxosNode

            self.node = PaxosNode(self.ip_addr, True, self.node_id)
            self.MessageType = PaxosMessageType
            self.Message = PaxosMessage

        print(
            f"[Node {self.node_id}] Successfully switched to {self.algorithm.upper()}"
        )

    async def _delayed_election(self, delay: float):
        """Start election after delay if no leader."""
        await asyncio.sleep(delay)
        if self.node.leader_id is None:
            await self.start_election()

    async def handle_http_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle incoming HTTP requests (REST API for client operations)."""
        try:
            request = await reader.read(4096)
            request_str = request.decode("utf-8")

            # Simple HTTP parser
            lines = request_str.split("\r\n")
            if not lines:
                writer.close()
                await writer.wait_closed()
                return

            request_line = lines[0]
            parts = request_line.split(" ")

            if len(parts) < 2:
                writer.close()
                await writer.wait_closed()
                return

            method = parts[0]
            path = parts[1]

            # Handle CORS preflight OPTIONS request
            if method == "OPTIONS":
                http_response = (
                    f"HTTP/1.1 204 No Content\r\n"
                    f"Access-Control-Allow-Origin: *\r\n"
                    f"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                    f"Access-Control-Allow-Headers: Content-Type\r\n"
                    f"Access-Control-Max-Age: 86400\r\n"
                    f"\r\n"
                )
                writer.write(http_response.encode("utf-8"))
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            # Parse body for POST requests
            body = ""
            if "\r\n\r\n" in request_str:
                body = request_str.split("\r\n\r\n", 1)[1]

            response = await self.route_http_request(method, path, body)

            # Send HTTP response
            http_response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(response)}\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                f"Access-Control-Allow-Headers: Content-Type\r\n"
                f"\r\n"
                f"{response}"
            )

            writer.write(http_response.encode("utf-8"))
            await writer.drain()

        except Exception as e:
            print(f"[Node {self.node_id}] HTTP error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def route_http_request(self, method: str, path: str, body: str) -> str:
        """Route HTTP requests to appropriate handlers."""
        try:
            if path == "/status" and method == "GET":
                if self.algorithm == "raft":
                    return json.dumps(
                        {
                            "node_id": self.node_id,
                            "algorithm": self.algorithm,
                            "role": self.node.role,
                            "term": self.node.current_term,
                            "leader": self.node.leader_id,
                            "log_size": len(self.node.log.entries),
                        }
                    )
                else:  # paxos
                    return json.dumps(
                        {
                            "node_id": self.node_id,
                            "algorithm": self.algorithm,
                            "ip": self.ip_addr,
                            "log_size": len(self.node.log.entries),
                            "promised_id": f"{self.node.highiest_promised_id[0]}.{self.node.highiest_promised_id[1]}",
                        }
                    )

            elif path == "/propose" and method == "POST":
                # Client proposes a change
                data = json.loads(body) if body else {}
                operation = data.get("operation", "")

                if self.algorithm == "raft":
                    if self.node.role != "leader":
                        return json.dumps(
                            {
                                "success": False,
                                "error": "Not the leader",
                                "leader": self.node.leader_id,
                            }
                        )
                    await self.propose_operation_raft(operation)
                    return json.dumps(
                        {
                            "success": True,
                            "operation": operation,
                            "term": self.node.current_term,
                        }
                    )
                else:  # paxos
                    await self.propose_operation_paxos(operation)
                    return json.dumps(
                        {"success": True, "operation": operation, "algorithm": "paxos"}
                    )

            elif path == "/log" and method == "GET":
                return json.dumps(
                    {
                        "node_id": self.node_id,
                        "algorithm": self.algorithm,
                        "log": self.node.log.entries,
                    }
                )

            elif path == "/consensus_logs" and method == "GET":
                return json.dumps(
                    {"node_id": self.node_id, "logs": self.consensus_logs}
                )

            elif path == "/start_election" and method == "POST":
                if self.algorithm == "raft":
                    await self.start_election()
                    return json.dumps({"success": True, "message": "Election started"})
                else:
                    return json.dumps(
                        {"success": False, "error": "Paxos doesn't have elections"}
                    )

            elif path == "/switch_algorithm" and method == "POST":
                data = json.loads(body) if body else {}
                new_algorithm = data.get("algorithm", "").lower()

                if new_algorithm not in ["raft", "paxos"]:
                    return json.dumps({"success": False, "error": "Invalid algorithm"})

                if new_algorithm != self.algorithm:
                    self.algorithm = new_algorithm
                    await self.reinitialize_node()
                    return json.dumps({"success": True, "algorithm": self.algorithm})
                else:
                    return json.dumps(
                        {
                            "success": True,
                            "algorithm": self.algorithm,
                            "message": "Already using this algorithm",
                        }
                    )

            elif path == "/reset" and method == "POST":
                # Reset node to initial state (clear logs but keep algorithm)
                await self.reinitialize_node()
                self.add_log("Node reset to initial state", "INFO")
                return json.dumps(
                    {
                        "success": True,
                        "message": "Node reset successfully",
                        "algorithm": self.algorithm,
                    }
                )

            else:
                return json.dumps({"error": "Not found"})

        except Exception as e:
            return json.dumps({"error": str(e)})

    async def propose_operation_raft(self, operation: str):
        """Leader proposes an operation to the cluster using Raft."""
        if self.node.role != "leader":
            return

        self.add_log(f"Leader proposing: {operation}", "PROPOSE")

        # Add to local log
        self.node.log.append(
            (self.node.current_term, len(self.node.log.entries)),
            datetime.now(),
            operation,
        )

        # Send append entries to all peers
        for peer in self.peers:
            message = self.Message(
                from_ip=self.ip_addr,
                to_ip=peer["ip"],
                message_type=self.MessageType.APPEND_ENTRIES,
                term=self.node.current_term,
                message_content={"entries": [operation], "leader": self.ip_addr},
            )
            await self.send_tcp_message(peer["ip"], peer["tcp_port"], message)

    async def propose_operation_paxos(self, operation: str):
        """Propose an operation using Paxos (PREPARE phase)."""
        # Generate unique proposal ID
        self.node.highiest_promised_id = (
            self.node.highiest_promised_id[0] + 1,
            self.node_id,
        )
        round_id = (
            f"{self.node.highiest_promised_id[0]}.{self.node.highiest_promised_id[1]}"
        )

        self.add_log(f"Proposing: {operation} (round {round_id})", "PROPOSE")
        self.node.message_content = operation

        # Send PREPARE to all peers
        all_ips = [p["ip"] for p in self.peers] + [self.ip_addr]
        for peer_ip in all_ips:
            if peer_ip == self.ip_addr:
                continue
            peer = next((p for p in self.peers if p["ip"] == peer_ip), None)
            if peer:
                message = self.Message(
                    from_ip=self.ip_addr,
                    to_ip=peer["ip"],
                    message_type=self.MessageType.PREPARE,
                    round_identyfier=round_id,
                    message_content=operation,
                )
                await self.send_tcp_message(peer["ip"], peer["tcp_port"], message)

    async def start_election(self):
        """Start leader election (Raft only)."""
        if self.algorithm != "raft":
            return

        self.node.current_term += 1
        self.node.role = "candidate"
        self.node.voted_for = self.ip_addr
        self.node.votes_received = {self.ip_addr}

        self.add_log(f"Starting election for term {self.node.current_term}", "ELECTION")
        print(
            f"[Node {self.node_id}] Starting election for term {self.node.current_term}"
        )

        # Request votes from all peers
        for peer in self.peers:
            message = self.Message(
                from_ip=self.ip_addr,
                to_ip=peer["ip"],
                message_type=self.MessageType.REQUEST_VOTE,
                term=self.node.current_term,
                message_content=self.ip_addr,
            )
            await self.send_tcp_message(peer["ip"], peer["tcp_port"], message)

    async def handle_tcp_message(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle incoming TCP messages (consensus protocol)."""
        try:
            data = await reader.read(8192)
            if not data:
                return

            message_str = data.decode("utf-8")
            message_dict = json.loads(message_str)

            # Reconstruct message based on algorithm
            message_type = message_dict["message_type"]

            # Ignore messages from wrong algorithm
            raft_messages = [
                "REQUEST_VOTE",
                "VOTE",
                "APPEND_ENTRIES",
                "APPEND_RESPONSE",
            ]
            paxos_messages = ["PREPARE", "PROMISE", "ACCEPT", "ACCEPTED"]

            if self.algorithm == "raft" and message_type in paxos_messages:
                # Ignore Paxos messages when running Raft
                return
            elif self.algorithm == "paxos" and message_type in raft_messages:
                # Ignore Raft messages when running Paxos
                return

            if self.algorithm == "raft":
                message = self.Message(
                    from_ip=message_dict["from_ip"],
                    to_ip=message_dict["to_ip"],
                    message_type=self.MessageType[message_dict["message_type"]],
                    term=message_dict["term"],
                    message_content=message_dict.get("message_content"),
                )
                self.add_log(
                    f"Received {message.message_type.name} from Node {message_dict.get('from_node_id', '?')}",
                    "CONSENSUS",
                )
                print(
                    f"[Node {self.node_id}] Received {message.message_type} from {message.from_ip}"
                )
            else:  # paxos
                message = self.Message(
                    from_ip=message_dict["from_ip"],
                    to_ip=message_dict["to_ip"],
                    message_type=self.MessageType[message_dict["message_type"]],
                    round_identyfier=message_dict["round_identyfier"],
                    message_content=message_dict.get("message_content"),
                )
                self.add_log(
                    f"Received {message.message_type.name} round {message_dict['round_identyfier']}",
                    "CONSENSUS",
                )
                print(
                    f"[Node {self.node_id}] Received {message.message_type} from {message.from_ip}"
                )

            # Process message and collect responses
            response_pool = []
            all_peer_ips = [p["ip"] for p in self.peers] + [self.ip_addr]
            quorum = len(all_peer_ips) // 2 + 1

            if self.algorithm == "raft":
                self.node.receive_message(message, response_pool, quorum, all_peer_ips)
            else:  # paxos
                self.node.recieve_message(message, response_pool, quorum, all_peer_ips)

            # Send any response messages
            for response in response_pool:
                if response.to_ip != self.ip_addr:
                    # Find peer port
                    peer = next(
                        (p for p in self.peers if p["ip"] == response.to_ip), None
                    )
                    if peer:
                        await self.send_tcp_message(
                            peer["ip"], peer["tcp_port"], response
                        )

        except Exception as e:
            print(f"[Node {self.node_id}] TCP error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def send_tcp_message(self, ip: str, port: int, message: Any):
        """Send a TCP message to a peer."""
        try:
            reader, writer = await asyncio.open_connection(ip, port)

            # Serialize message
            if self.algorithm == "raft":
                message_dict = {
                    "from_ip": message.from_ip,
                    "to_ip": message.to_ip,
                    "message_type": message.message_type.name,
                    "term": message.term,
                    "message_content": message.message_content,
                }
            else:  # paxos
                message_dict = {
                    "from_ip": message.from_ip,
                    "to_ip": message.to_ip,
                    "message_type": message.message_type.name,
                    "round_identyfier": message.round_identyfier,
                    "message_content": message.message_content,
                }

            message_str = json.dumps(message_dict)

            writer.write(message_str.encode("utf-8"))
            await writer.drain()

            writer.close()
            await writer.wait_closed()

        except Exception as e:
            print(f"[Node {self.node_id}] Failed to send to {ip}:{port}: {e}")

    async def start_http_server(self):
        """Start HTTP server for REST API."""
        server = await asyncio.start_server(
            self.handle_http_request, "0.0.0.0", self.http_port
        )

        print(f"[Node {self.node_id}] HTTP server started on port {self.http_port}")

        async with server:
            await server.serve_forever()

    async def start_tcp_server(self):
        """Start TCP server for consensus communication."""
        server = await asyncio.start_server(
            self.handle_tcp_message, "0.0.0.0", self.tcp_port
        )

        print(f"[Node {self.node_id}] TCP server started on port {self.tcp_port}")

        async with server:
            await server.serve_forever()

    async def run(self):
        """Run both HTTP and TCP servers."""
        await asyncio.gather(self.start_http_server(), self.start_tcp_server())


async def main():
    """Main entry point."""
    # Get configuration from environment
    node_id = int(os.getenv("NODE_ID", "1"))
    http_port = int(os.getenv("HTTP_PORT", "8000"))
    tcp_port = int(os.getenv("TCP_PORT", "5000"))
    algorithm = os.getenv("ALGORITHM", "raft")

    # Parse peers from environment
    peers_str = os.getenv("PEERS", "")
    peers = []
    if peers_str:
        for peer_str in peers_str.split(";"):
            parts = peer_str.split(":")
            if len(parts) == 2:
                peers.append({"ip": parts[0], "tcp_port": int(parts[1])})

    server = ConsensusServer(node_id, http_port, tcp_port, peers, algorithm)

    # Start servers in background
    async def start_servers():
        await server.run()

    # Start election task for Raft
    async def auto_election():
        if algorithm.lower() == "raft":
            # Wait for other nodes to start
            await asyncio.sleep(1)

            # Node 1 starts first election quickly
            if node_id == 1:
                await asyncio.sleep(0.5)
                await server.start_election()
            else:
                # Other nodes wait a bit longer
                await asyncio.sleep(2)
                # If no leader after 2 seconds, start election
                if server.node.leader_id is None:
                    await server.start_election()

    # Run both tasks
    await asyncio.gather(start_servers(), auto_election())


if __name__ == "__main__":
    asyncio.run(main())
