"""
Raft Server with HTTP REST API and TCP consensus communication.
Each server listens on HTTP for client requests and TCP for inter-node Raft messages.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List

from raft_messages import RaftMessage, RaftMessageType
from raft_nodes import Node


class RaftServer:
    def __init__(
        self, node_id: int, http_port: int, tcp_port: int, peers: List[Dict[str, Any]]
    ):
        """
        Initialize Raft server.

        Args:
            node_id: Unique identifier for this node
            http_port: Port for HTTP REST API
            tcp_port: Port for TCP Raft communication
            peers: List of peer nodes [{"ip": "172.20.0.2", "tcp_port": 5001}, ...]
        """
        self.node_id = node_id
        self.http_port = http_port
        self.tcp_port = tcp_port
        self.peers = peers

        # Create Raft node
        self.ip_addr = self.get_own_ip()
        self.node = Node(self.ip_addr, True, node_id)

        # Message queue for async processing
        self.message_queue = asyncio.Queue()

        # Track peer connections
        self.peer_connections: Dict[str, tuple] = {}

        print(f"[Node {self.node_id}] Initialized at {self.ip_addr}:{self.tcp_port}")
        print(f"[Node {self.node_id}] HTTP API on port {self.http_port}")
        print(f"[Node {self.node_id}] Peers: {self.peers}")

    def get_own_ip(self) -> str:
        """Get own IP address from environment or use localhost."""
        return os.getenv("NODE_IP", "127.0.0.1")

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
                return json.dumps(
                    {
                        "node_id": self.node_id,
                        "role": self.node.role,
                        "term": self.node.current_term,
                        "leader": self.node.leader_id,
                        "log_size": len(self.node.log.entries),
                    }
                )

            elif path == "/propose" and method == "POST":
                # Client proposes a change
                data = json.loads(body) if body else {}
                operation = data.get("operation", "")

                if self.node.role != "leader":
                    return json.dumps(
                        {
                            "success": False,
                            "error": "Not the leader",
                            "leader": self.node.leader_id,
                        }
                    )

                # Leader proposes to cluster
                await self.propose_operation(operation)

                return json.dumps(
                    {
                        "success": True,
                        "operation": operation,
                        "term": self.node.current_term,
                    }
                )

            elif path == "/log" and method == "GET":
                return json.dumps(
                    {"node_id": self.node_id, "log": self.node.log.entries}
                )

            elif path == "/start_election" and method == "POST":
                # Manually trigger election (for testing)
                await self.start_election()
                return json.dumps({"success": True, "message": "Election started"})

            else:
                return json.dumps({"error": "Not found"})

        except Exception as e:
            return json.dumps({"error": str(e)})

    async def propose_operation(self, operation: str):
        """Leader proposes an operation to the cluster."""
        if self.node.role != "leader":
            return

        # Add to local log
        self.node.log.append(
            (self.node.current_term, len(self.node.log.entries)),
            datetime.now(),
            operation,
        )

        # Send append entries to all peers
        for peer in self.peers:
            message = RaftMessage(
                from_ip=self.ip_addr,
                to_ip=peer["ip"],
                message_type=RaftMessageType.APPEND_ENTRIES,
                term=self.node.current_term,
                message_content={"entries": [operation], "leader": self.ip_addr},
            )
            await self.send_tcp_message(peer["ip"], peer["tcp_port"], message)

    async def start_election(self):
        """Start leader election."""
        self.node.current_term += 1
        self.node.role = "candidate"
        self.node.voted_for = self.ip_addr
        self.node.votes_received = {self.ip_addr}

        print(
            f"[Node {self.node_id}] Starting election for term {self.node.current_term}"
        )

        # Request votes from all peers
        for peer in self.peers:
            message = RaftMessage(
                from_ip=self.ip_addr,
                to_ip=peer["ip"],
                message_type=RaftMessageType.REQUEST_VOTE,
                term=self.node.current_term,
                message_content=self.ip_addr,
            )
            await self.send_tcp_message(peer["ip"], peer["tcp_port"], message)

    async def handle_tcp_message(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle incoming TCP messages (Raft consensus protocol)."""
        try:
            data = await reader.read(8192)
            if not data:
                return

            message_str = data.decode("utf-8")
            message_dict = json.loads(message_str)

            # Reconstruct RaftMessage
            message = RaftMessage(
                from_ip=message_dict["from_ip"],
                to_ip=message_dict["to_ip"],
                message_type=RaftMessageType[message_dict["message_type"]],
                term=message_dict["term"],
                message_content=message_dict.get("message_content"),
            )

            print(
                f"[Node {self.node_id}] Received {message.message_type} from {message.from_ip}"
            )

            # Process message and collect responses
            response_pool = []
            all_peer_ips = [p["ip"] for p in self.peers] + [self.ip_addr]
            quorum = len(all_peer_ips) // 2 + 1

            self.node.receive_message(message, response_pool, quorum, all_peer_ips)

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

    async def send_tcp_message(self, ip: str, port: int, message: RaftMessage):
        """Send a TCP message to a peer."""
        try:
            reader, writer = await asyncio.open_connection(ip, port)

            # Serialize message
            message_dict = {
                "from_ip": message.from_ip,
                "to_ip": message.to_ip,
                "message_type": message.message_type.name,
                "term": message.term,
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
        """Start TCP server for Raft communication."""
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

    # Parse peers from environment
    peers_str = os.getenv("PEERS", "")
    peers = []
    if peers_str:
        for peer_str in peers_str.split(";"):
            parts = peer_str.split(":")
            if len(parts) == 2:
                peers.append({"ip": parts[0], "tcp_port": int(parts[1])})

    server = RaftServer(node_id, http_port, tcp_port, peers)

    # Wait a bit for other nodes to start
    await asyncio.sleep(2)

    # Node 1 starts first election
    if node_id == 1:
        await asyncio.sleep(1)
        await server.start_election()

    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
