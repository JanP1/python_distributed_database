import asyncio
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from raft_messages import RaftMessage, RaftMessageType
from raft_nodes import Node

class RaftServer:
    def __init__(self, node_id: int, http_port: int, tcp_port: int, peers: List[Dict[str, Any]]):
        self.node_id = node_id
        self.http_port = http_port
        self.tcp_port = tcp_port
        self.peers = peers

        self.ip_addr = self.get_own_ip()
       
        self.node = Node(self.ip_addr, True, node_id)

        
        self.peer_ips: List[str] = [p["ip"] for p in self.peers]

        print(f"[Node {self.node_id}] Init at {self.ip_addr}:{self.tcp_port} | Peers: {self.peer_ips}")

    def get_own_ip(self) -> str:
        return os.getenv("NODE_IP", "127.0.0.1")

    
    async def run_election_timer(self) -> None:
        """Jeśli nie ma lidera (nie jesteśmy liderem), sprawdzamy deadline i uruchamiamy elekcję."""
        print("[System] Election timer started.")
        while True:
            await asyncio.sleep(0.05)

            
            if self.node.role == "leader":
                continue

            now = self.node._now()
            if now >= self.node.election_deadline:
                
                if self.node.role == "candidate":
                    
                    self.node.on_election_failed()
                
                await self.start_election()

    async def run_heartbeat_loop(self) -> None:
        """Lider wysyła regularnie AppendEntries (heartbeat)."""
        print("[System] Heartbeat loop started.")
        while True:
            if self.node.role == "leader":
                
                for peer in self.peers:
                    prev_idx = self.node.get_last_log_index()
                    prev_term = self.node.get_last_log_term()

                    msg = RaftMessage(
                        from_ip=self.ip_addr,
                        to_ip=peer["ip"],
                        message_type=RaftMessageType.APPEND_ENTRIES,
                        term=self.node.current_term,
                        message_content={
                            "prev_log_index": prev_idx,
                            "prev_log_term": prev_term,
                            "entries": [],  # heartbeat
                            "leader_commit": self.node.commit_index,
                            "leader_id": self.ip_addr,
                        },
                    )
                    asyncio.create_task(self.send_tcp_message(peer["ip"], peer["tcp_port"], msg))
                await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(0.2)

    
    async def start_election(self) -> None:
        """Rozpoczyna elekcję (candidate) i rozsyła REQUEST_VOTE z informacją o aktualności logu."""
        last_idx, last_term = self.node.begin_election()

        print(f"[Election] Candidate {self.node_id} starting term {self.node.current_term} "
            f"(log term={last_term}, idx={last_idx})")

        for peer in self.peers:
            message = RaftMessage(
                from_ip=self.ip_addr,
                to_ip=peer["ip"],
                message_type=RaftMessageType.REQUEST_VOTE,
                term=self.node.current_term,
                message_content={
                    "candidate_id": self.ip_addr,
                    "last_log_index": last_idx,
                    "last_log_term": last_term,
                },
            )
            await self.send_tcp_message(peer["ip"], peer["tcp_port"], message)
    
    # TCP (wewnętrzny protokół Raft) + HTTP (interfejs klienta)
    async def handle_tcp_message(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            data = await reader.read(8192)
            if not data:
                return

            msg_dict = json.loads(data.decode("utf-8"))
            message = RaftMessage(
                msg_dict["from_ip"],
                msg_dict["to_ip"],
                RaftMessageType[msg_dict["message_type"]],
                msg_dict["term"],
                msg_dict.get("message_content"),
            )

            response_pool: List[RaftMessage] = []
            all_ips = self.peer_ips + [self.ip_addr]
            quorum = (len(all_ips) // 2) + 1

            self.node.receive_message(message, response_pool, quorum, all_ips)

            
            for resp in response_pool:
                peer = next((p for p in self.peers if p["ip"] == resp.to_ip), None)
                if peer:
                    await self.send_tcp_message(peer["ip"], peer["tcp_port"], resp)

        except Exception as e:
            print(f"[TCP Error] {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def send_tcp_message(self, ip: str, port: int, message: RaftMessage) -> None:
        try:
            reader, writer = await asyncio.open_connection(ip, port)
            payload = {
                "from_ip": message.from_ip,
                "to_ip": message.to_ip,
                "message_type": message.message_type.name,
                "term": message.term,
                "message_content": message.message_content,
            }
            writer.write(json.dumps(payload).encode("utf-8"))
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    async def handle_http_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await reader.read(4096)
            request_str = request.decode("utf-8")

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

            body = ""
            if "\r\n\r\n" in request_str:
                body = request_str.split("\r\n\r\n", 1)[1]

            response = await self.route_http_request(method, path, body)

            http_response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(response)}\r\n"
                "Access-Control-Allow-Origin: *\r\n"
                "\r\n"
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
        try:
            if path == "/status" and method == "GET":
                return json.dumps(
                    {
                        "node_id": self.node_id,
                        "role": self.node.role,
                        "term": self.node.current_term,
                        "leader": self.node.leader_id,
                        "log_size": len(self.node.log.entries),
                        "commit_index": self.node.commit_index,
                    }
                )

            if path == "/propose" and method == "POST":
                data = json.loads(body) if body else {}
                operation = data.get("operation", "")

                if self.node.role != "leader":
                    return json.dumps(
                        {"success": False, "error": "Not the leader", "leader": self.node.leader_id}
                    )

                await self.propose_operation(operation)
                return json.dumps({"success": True, "operation": operation, "term": self.node.current_term})

            if path == "/log" and method == "GET":
                return json.dumps({"node_id": self.node_id, "log": self.node.log.entries})

            if path == "/start_election" and method == "POST":
                await self.start_election()
                return json.dumps({"success": True, "message": "Election started"})

            return json.dumps({"error": "Not found"})

        except Exception as e:
            return json.dumps({"error": str(e)})

    
    async def propose_operation(self, operation: str) -> None:
        if self.node.role != "leader":
            return

        
        new_index = self.node.get_last_log_index() + 1
        self.node.log.append((self.node.current_term, new_index), datetime.now(), operation)

        message_pool = []
        self.node.broadcast_append_entries(message_pool, self.peer_ips)
        
        for msg in message_pool:
            peer = next((p for p in self.peers if p["ip"] == msg.to_ip), None)
            if peer:
                await self.send_tcp_message(peer["ip"], peer["tcp_port"], msg)
                
    # Start serwera (HTTP + TCP) + taski tła
    async def run(self) -> None:
        server_http = await asyncio.start_server(self.handle_http_request, "0.0.0.0", self.http_port)
        server_tcp = await asyncio.start_server(self.handle_tcp_message, "0.0.0.0", self.tcp_port)

        print(f"Servers running. HTTP: {self.http_port}, TCP: {self.tcp_port}")

        task_election = asyncio.create_task(self.run_election_timer())
        task_heartbeat = asyncio.create_task(self.run_heartbeat_loop())

        async with server_http, server_tcp:
            await asyncio.gather(
                server_http.serve_forever(),
                server_tcp.serve_forever(),
                task_election,
                task_heartbeat,
            )


async def main() -> None:
    node_id = int(os.getenv("NODE_ID", "1"))
    http_port = int(os.getenv("HTTP_PORT", "8000"))
    tcp_port = int(os.getenv("TCP_PORT", "5000"))

    peers_env = os.getenv("PEERS", "")
    peers: List[Dict[str, Any]] = []
    if peers_env:
        for p in peers_env.split(";"):
            ip, port = p.split(":")
            peers.append({"ip": ip, "tcp_port": int(port)})

    server = RaftServer(node_id, http_port, tcp_port, peers)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())