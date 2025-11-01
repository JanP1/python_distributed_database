from enum import Enum
from dataclasses import dataclass
from typing import Any



class PaxosMessageType(Enum):
    PREPARE = 1
    PROMISE = 2
    ACCEPT = 3
    ACCEPTED = 4



class MessageBox:
    """
    A simple MessageBox storing messages in a list.
    """

    def __init__(self):
        self.messages = []

    def put(self, message):
        self.messages.append(message)

    def pop(self):
        if self.messages:
            return self.messages.pop(0)
        return None



@dataclass
class PaxosMessage:
    from_ip: str
    to_ip: str
    timestamp: str 
    message_type: PaxosMessageType
    proposal_number: str
    message_content: Any = None


    def __str__(self) -> str:
        return (f"{self.from_ip}|{self.to_ip}|{self.message_type}|{self.proposal_number}|{self.message_content}")


    @classmethod
    def message_from_string(cls, paxos_message_string: str):
        parts = paxos_message_string.split("|", 5)

        if len(parts) < 4:
            raise ValueError(f"Invalid message format: {paxos_message_string}")

        from_ip, to_ip, timestamp, message_type, proposal_number, *content = parts
        message_content = content[0] if content else None
        message_type = PaxosMessageType[message_type]

        return cls(from_ip, to_ip, timestamp, message_type, proposal_number, message_content)


