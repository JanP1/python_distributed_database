from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from raft_messages import RaftMessage, RaftMessageType


class Node:
    def __init__(self, ip_addr: str, up_to_date: bool, ID: int) -> None:
        self.ID = ID
        self.ip_addr: str = ip_addr
        self.up: bool = True
        self.up_to_date: bool = up_to_date

        # Raft state
        self.current_term: int = 0
        self.voted_for: str | None = None
        self.log: Log = Log()

        self.commit_index: int = -1
        self.last_applied: int = -1

        # volatile leader state (on leaders)
        self.next_index = {}
        self.match_index = {}

        # election state
        self.role: str = "follower"  # follower, candidate, leader
        self.votes_received = set()
        self.leader_id: str | None = None

    def get_ip(self):
        return self.ip_addr

    def send_message(
        self,
        message_pool: list,
        target_ips: list,
        message_type: RaftMessageType,
        term: int,
        content: Any = None,
    ):
        for ip in target_ips:
            message_pool.append(
                RaftMessage(self.ip_addr, ip, message_type, term, content)
            )

    def receive_message(
        self, message: RaftMessage, message_pool: list, quorum: int, nodes_ips: list
    ):
        # Basic Raft message handling: vote requests, votes, append entries and responses
        if message.message_type == RaftMessageType.REQUEST_VOTE:
            # content: candidate_id
            candidate_id = message.message_content
            if message.term > self.current_term:
                self.current_term = message.term
                self.voted_for = None
                self.role = "follower"

            granted = False
            if message.term >= self.current_term and (
                self.voted_for is None or self.voted_for == candidate_id
            ):
                self.voted_for = candidate_id
                granted = True
                self.current_term = message.term

            # reply with VOTE
            reply = {"granted": granted, "voter": self.ip_addr}
            self.send_message(
                message_pool,
                [message.from_ip],
                RaftMessageType.VOTE,
                self.current_term,
                reply,
            )

        elif message.message_type == RaftMessageType.VOTE:
            # content: {granted: bool, voter: ip}
            if self.role != "candidate":
                return
            if message.term > self.current_term:
                self.current_term = message.term
                self.role = "follower"
                self.votes_received = set()
                return

            if message.message_content and message.message_content.get("granted"):
                self.votes_received.add(message.from_ip)

            if len(self.votes_received) + 1 >= quorum and self.role == "candidate":
                # become leader
                self.role = "leader"
                self.leader_id = self.ip_addr
                # init leader volatile state
                for ip in nodes_ips:
                    self.next_index[ip] = len(self.log.entries)
                    self.match_index[ip] = -1
                print(
                    f"Node {self.ID} ({self.ip_addr}) became leader for term {self.current_term}"
                )
                # send initial empty append entries (heartbeat)
                self.send_message(
                    message_pool,
                    nodes_ips,
                    RaftMessageType.APPEND_ENTRIES,
                    self.current_term,
                    {"entries": [], "leader": self.ip_addr},
                )

        elif message.message_type == RaftMessageType.APPEND_ENTRIES:
            # content: {entries: [message], leader: ip}
            if message.term >= self.current_term:
                self.current_term = message.term
                self.role = "follower"
                self.leader_id = message.message_content.get("leader")

                entries = message.message_content.get("entries", [])
                # append entries simply
                for e in entries:
                    self.log.append((message.term, e), datetime.now())

                # reply success
                reply = {
                    "success": True,
                    "follower": self.ip_addr,
                    "appended": len(entries),
                }
                self.send_message(
                    message_pool,
                    [message.from_ip],
                    RaftMessageType.APPEND_RESPONSE,
                    self.current_term,
                    reply,
                )

        elif message.message_type == RaftMessageType.APPEND_RESPONSE:
            # leader will receive responses
            if self.role != "leader":
                return
            # count successful acks
            success = message.message_content.get("success", False)
            if success:
                # simple quorum check: when leader receives quorum responses for the last append, commit
                # we'll store ack count in match_index by using match_index as counter for simplicity
                self.match_index[message.from_ip] = self.match_index.get(
                    message.from_ip, -1
                ) + message.message_content.get("appended", 0)

                # count nodes with some positive match
                acks = sum(1 for v in self.match_index.values() if v >= 0)
                if acks + 1 >= quorum:
                    # commit leader's last entries
                    if self.log.entries:
                        last = self.log.entries[-1]
                        self.commit_index = len(self.log.entries) - 1
                        print(f"Leader {self.ID} committed value: {last['message']}")
                        # notify all nodes by sending a heartbeat with no entries (to simulate commit propagation)
                        self.send_message(
                            message_pool,
                            nodes_ips,
                            RaftMessageType.APPEND_ENTRIES,
                            self.current_term,
                            {"entries": [], "leader": self.ip_addr},
                        )


from dataclasses import dataclass


@dataclass
class Log:
    def __init__(self):
        self.entries = []

    def append(self, request_number, timestamp, message=None):
        # The Paxos Log appended dict is kept similar so demo prints match style
        # request_number for raft we'll store term and message tuple
        if message is None:
            message = request_number
            request_number = (0, 0)
        self.entries.append(
            {
                "request_number": request_number,
                "timestamp": str(timestamp),
                "message": message,
            }
        )

    def replay(self, start_index=0):
        for entry in self.entries[start_index:]:
            yield entry
