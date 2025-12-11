import asyncio
import json
import os
import sys
import struct
from datetime import datetime
from typing import Any, Dict, List

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
        self.node_id = node_id
        self.http_port = http_port
        self.tcp_port = tcp_port
        self.peers = peers
        self.algorithm = algorithm.lower()
        self.ip_addr = self.get_own_ip()
        self.paxos_round_counter = 0
        self.consensus_logs: List[Dict[str, Any]] = []
        
        self.node = None
        self.MessageType = None
        self.Message = None

        self._initialize_node()
        self.add_log(f"Node initialized with {self.algorithm.upper()}", "INFO")
        print(f"[Node {self.node_id}] Started {self.algorithm.upper()} HTTP:{self.http_port} TCP:{self.tcp_port}")

    def get_own_ip(self) -> str:
        return os.getenv("NODE_IP", "127.0.0.1")

    def _initialize_node(self):
        try:
            if self.algorithm == "raft":
                from raft_messages import RaftMessage, RaftMessageType
                from raft_nodes import Node as RaftNode
                self.node = RaftNode(self.ip_addr, True, self.node_id, logger=self.add_log)
                self.MessageType = RaftMessageType
                self.Message = RaftMessage
            elif self.algorithm == "paxos":
                from paxos_messages import PaxosMessage, PaxosMessageType
                from paxos_nodes import Node as PaxosNode
                # ZMIANA: Przekazujemy self.add_log jako logger
                self.node = PaxosNode(self.ip_addr, True, self.node_id, logger=self.add_log)
                self.MessageType = PaxosMessageType
                self.Message = PaxosMessage
            else:
                raise ValueError(f"Unknown algorithm: {self.algorithm}")
        except Exception as e:
            print(f"[CRITICAL ERROR] Failed to initialize {self.algorithm}: {e}")

            if self.algorithm != "raft":
                print("[System] Falling back to RAFT due to error.")
                self.algorithm = "raft"
                self._initialize_node()

    def add_log(self, message: str, level: str = "INFO"):
        print(f"[{level}] {message}")
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "node_id": self.node_id,
            "level": level,
            "message": message,
            "algorithm": self.algorithm,
        }
        self.consensus_logs.append(log_entry)
        if len(self.consensus_logs) > 100:
            self.consensus_logs.pop(0)

    async def reinitialize_node(self):
        print(f"[Node {self.node_id}] Switching to {self.algorithm.upper()}")
        self._initialize_node()

    async def _raft_election_loop(self):
        while True:
            await asyncio.sleep(0.1)
            if self.algorithm != "raft": continue
            if not hasattr(self.node, 'role'): continue
            
            if self.node.role == "leader": continue
            
            now = self.node._now()
            if now >= self.node.election_deadline:
                print(f"[Election] Timeout! Starting election.")
                await self.start_election_raft()

    async def _raft_heartbeat_loop(self):
        while True:
            await asyncio.sleep(0.3)
            if self.algorithm != "raft": continue
            if not hasattr(self.node, 'role'): continue
            
            if self.node.role == "leader":
                msg_pool = []
                all_ips = [p["ip"] for p in self.peers] + [self.ip_addr]
                
                if hasattr(self.node, 'broadcast_append_entries'):
                    self.node.broadcast_append_entries(msg_pool, all_ips)
                
                for msg in msg_pool:
                    peer = next((p for p in self.peers if p["ip"] == msg.to_ip), None)
                    if peer:
                        asyncio.create_task(self.send_tcp_message(peer["ip"], peer["tcp_port"], msg))

    async def start_election_raft(self):
        if not hasattr(self.node, 'current_term'): return
        self.node.current_term += 1
        self.node.role = "candidate"
        self.node.voted_for = self.ip_addr
        self.node.votes_received = {self.ip_addr}
        if hasattr(self.node, '_reset_election_deadline'):
            self.node._reset_election_deadline()
        
        last_idx = self.node.get_last_log_index()
        last_term = self.node.get_last_log_term()
        
        self.add_log(f"Starting Election (Term {self.node.current_term})", "ELECTION")
        
        content = {
            "candidate_id": self.ip_addr,
            "last_log_index": last_idx,
            "last_log_term": last_term
        }
        
        for peer in self.peers:
            msg = self.Message(self.ip_addr, peer["ip"], self.MessageType.REQUEST_VOTE, self.node.current_term, content)
            asyncio.create_task(self.send_tcp_message(peer["ip"], peer["tcp_port"], msg))

    # HTTP SERVER
    async def handle_http_request(self, reader, writer):
        try:
            line = await reader.readline()
            if not line: return
            request_line = line.decode('utf-8').strip()
            if not request_line: return
            parts = request_line.split(" ")
            if len(parts) < 2: return
            method, path = parts[0], parts[1]

            headers = {}
            content_length = 0
            while True:
                line = await reader.readline()
                line_str = line.decode('utf-8').strip()
                if not line_str: break
                if ": " in line_str:
                    k, v = line_str.split(": ", 1)
                    headers[k.lower()] = v
            
            if "content-length" in headers:
                content_length = int(headers["content-length"])

            if method == "OPTIONS":
                await self.send_cors_response(writer)
                return

            body_str = ""
            if content_length > 0:
                body_bytes = await reader.readexactly(content_length)
                body_str = body_bytes.decode('utf-8')

            response_data = await self.route_http_request(method, path, body_str)
            await self.send_json_response(writer, response_data)

        except Exception as e:
            print(f"[HTTP Error] {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except: pass

    async def send_cors_response(self, writer):
        response = (
            "HTTP/1.1 204 No Content\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Methods: POST, GET, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(response.encode('utf-8'))
        await writer.drain()

    async def send_json_response(self, writer, data):
        body_bytes = json.dumps(data).encode('utf-8')
        response = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Access-Control-Allow-Methods: POST, GET, OPTIONS\r\n"
            f"Access-Control-Allow-Headers: Content-Type\r\n"
            f"Connection: close\r\n\r\n"
        )
        writer.write(response.encode('utf-8'))
        writer.write(body_bytes)
        await writer.drain()

    async def route_http_request(self, method, path, body) -> dict:
        data = json.loads(body) if body else {}

        if path == "/status" and method == "GET":
            if self.algorithm == "raft":
                return {
                    "node_id": self.node_id,
                    "algorithm": "raft",
                    "role": getattr(self.node, 'role', 'unknown'),
                    "term": getattr(self.node, 'current_term', 0),
                    "leader": getattr(self.node, 'leader_id', None),
                    "log_size": len(self.node.log.entries),
                    "commit_index": getattr(self.node, 'commit_index', -1)
                }
            else:
                promised = getattr(self.node, 'highest_promised_id', (0,0))
                return {
                    "node_id": self.node_id,
                    "algorithm": "paxos",
                    "promised_id": f"{promised[0]}.{promised[1]}",
                    "log_size": len(self.node.log.entries),
                }

        elif path == "/switch_algorithm" and method == "POST":
            new_algo = data.get("algorithm", "").lower()
            if new_algo not in ["raft", "paxos"]:
                return {"success": False, "error": "Invalid algorithm"}
            
            try:
                if new_algo != self.algorithm:
                    self.add_log(f"SWITCHING ALGORITHM TO {new_algo.upper()}", "SYSTEM")
                    self.algorithm = new_algo
                    await self.reinitialize_node()
                return {"success": True, "algorithm": self.algorithm}
            except Exception as e:
                return {"success": False, "error": str(e)}

        elif path == "/propose" and method == "POST":
            operation = data.get("operation", "")
            if self.algorithm == "raft":
                if self.node.role != "leader":
                    return {"success": False, "error": "Not the leader", "leader": self.node.leader_id}
                
                self.node.log.append((self.node.current_term, self.node.get_last_log_index() + 1), datetime.now(), operation)
                
                msg_pool = []
                all_ips = [p["ip"] for p in self.peers] + [self.ip_addr]
                if hasattr(self.node, 'broadcast_append_entries'):
                    self.node.broadcast_append_entries(msg_pool, all_ips)
                    
                for msg in msg_pool:
                     peer = next((p for p in self.peers if p["ip"] == msg.to_ip), None)
                     if peer: asyncio.create_task(self.send_tcp_message(peer["ip"], peer["tcp_port"], msg))
                
                await asyncio.sleep(1.0)
                current_accounts = getattr(self.node, 'accounts', {})
                return {
                    "success": True, 
                    "operation": operation, 
                    "term": self.node.current_term,
                    "new_state": current_accounts 
                }
            else:
                # PAXOS
                try:
                    await self.propose_operation_paxos(operation)
                    await asyncio.sleep(2.0)
                    current_accounts = getattr(self.node, 'accounts', {})
                    return {"success": True, "algorithm": "paxos", "new_state": current_accounts}
                except Exception as e:
                    return {"success": False, "error": str(e)}

        elif path == "/log" and method == "GET":
            return {"node_id": self.node_id, "algorithm": self.algorithm, "log": self.node.log.entries}
        
        elif path == "/consensus_logs" and method == "GET":
             return {"node_id": self.node_id, "logs": self.consensus_logs}

        elif path == "/reset" and method == "POST":
            self.add_log("!!! SYSTEM RESET TRIGGERED !!!", "SYSTEM")
            await self.reinitialize_node()
            return {"success": True}
        
        elif path == "/accounts" and method == "GET":
            # Zwracamy aktualny stan kont z pamięci węzła
            return getattr(self.node, 'accounts', {})

        return {"error": "Not found"}

    # TCP SERVER
    async def handle_tcp_message(self, reader, writer):
        try:
            while True:
                try:
                    length_bytes = await reader.readexactly(4)
                except asyncio.IncompleteReadError: break 
                
                length = struct.unpack('>I', length_bytes)[0]
                data = await reader.readexactly(length)
                message_dict = json.loads(data.decode("utf-8"))
                await self.process_consensus_message(message_dict)
        except Exception: pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def send_tcp_message(self, ip: str, port: int, message: Any):
        try:
            reader, writer = await asyncio.open_connection(ip, port)
            
            msg_dict = {
                "from_ip": message.from_ip,
                "to_ip": message.to_ip,
                "message_type": message.message_type.name,
                "message_content": message.message_content,
            }
            if self.algorithm == "raft":
                msg_dict["term"] = message.term
            else:
                rid = getattr(message, "round_identyfier", getattr(message, "round_identifier", "0.0"))
                msg_dict["round_identifier"] = rid

            json_data = json.dumps(msg_dict).encode("utf-8")
            writer.write(struct.pack('>I', len(json_data)))
            writer.write(json_data)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except Exception: pass

    async def process_consensus_message(self, message_dict):
        msg_type_str = message_dict["message_type"]
        is_raft_msg = msg_type_str in ["REQUEST_VOTE", "VOTE", "APPEND_ENTRIES", "APPEND_RESPONSE"]
        
        if self.algorithm == "raft" and not is_raft_msg: return
        if self.algorithm == "paxos" and is_raft_msg: return

        if self.algorithm == "raft":
            message = self.Message(
                from_ip=message_dict["from_ip"],
                to_ip=message_dict["to_ip"],
                message_type=self.MessageType[msg_type_str],
                term=message_dict["term"],
                message_content=message_dict.get("message_content"),
            )
        else:
            rid = message_dict.get("round_identifier", message_dict.get("round_identyfier"))
            message = self.Message(
                from_ip=message_dict["from_ip"],
                to_ip=message_dict["to_ip"],
                message_type=self.MessageType[msg_type_str],
                round_identifier=rid,
                message_content=message_dict.get("message_content"),
            )

        response_pool = []
        all_peer_ips = [p["ip"] for p in self.peers] + [self.ip_addr]
        quorum = len(all_peer_ips) // 2 + 1

        if hasattr(self.node, 'receive_message'):
            self.node.receive_message(message, response_pool, quorum, all_peer_ips)
        else:
            self.node.recieve_message(message, response_pool, quorum, all_peer_ips)

        for response in response_pool:
            await self._deliver_outgoing(response, all_peer_ips, quorum)

    async def _deliver_outgoing(self, message, all_peer_ips, quorum):
        if message.to_ip == self.ip_addr:
            local_response_pool = []
            self.node.receive_message(message, local_response_pool, quorum, all_peer_ips)
            for r in local_response_pool:
                await self._deliver_outgoing(r, all_peer_ips, quorum)
            return

        peer = next((p for p in self.peers if p["ip"] == message.to_ip), None)
        if peer:
            asyncio.create_task(self.send_tcp_message(peer["ip"], peer["tcp_port"], message))
    
    # LOGIC - PAXOS
    async def propose_operation_paxos(self, operation: str):
        self.paxos_round_counter += 1
        round_id = f"{self.node_id}.{self.paxos_round_counter}"
        self.add_log(f"Proposing: {operation} (round {round_id})", "PROPOSE")
        self.node.message_content = operation

        all_peer_ips = [p["ip"] for p in self.peers] + [self.ip_addr]
        quorum = len(all_peer_ips) // 2 + 1

        for peer in self.peers:
            msg = self.Message(self.ip_addr, peer["ip"], self.MessageType.PREPARE, round_id, operation)
            asyncio.create_task(self.send_tcp_message(peer["ip"], peer["tcp_port"], msg))

        local_msg = self.Message(self.ip_addr, self.ip_addr, self.MessageType.PREPARE, round_id, operation)
        local_response_pool = []
        self.node.receive_message(local_msg, local_response_pool, quorum, all_peer_ips)
        for r in local_response_pool:
            await self._deliver_outgoing(r, all_peer_ips, quorum)

    async def run(self):
        http_server = await asyncio.start_server(self.handle_http_request, "0.0.0.0", self.http_port)
        tcp_server = await asyncio.start_server(self.handle_tcp_message, "0.0.0.0", self.tcp_port)
        
        asyncio.create_task(self._raft_election_loop())
        asyncio.create_task(self._raft_heartbeat_loop())
        
        await asyncio.gather(
            http_server.serve_forever(),
            tcp_server.serve_forever()
        )

async def main():
    node_id = int(os.getenv("NODE_ID", "1"))
    http_port = int(os.getenv("HTTP_PORT", "8000"))
    tcp_port = int(os.getenv("TCP_PORT", "5000"))
    algorithm = os.getenv("ALGORITHM", "raft")
    
    peers = []
    if os.getenv("PEERS"):
        for p in os.getenv("PEERS").split(";"):
            if ":" in p:
                ip, port = p.split(":")
                peers.append({"ip": ip, "tcp_port": int(port)})

    server = ConsensusServer(node_id, http_port, tcp_port, peers, algorithm)
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())