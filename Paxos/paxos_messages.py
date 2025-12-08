from enum import Enum
from typing import Any

class PaxosMessageType(Enum):
    PREPARE = 1
    PROMISE = 2
    ACCEPT = 3
    ACCEPTED = 4

class PaxosMessage:
    def __init__(
        self,
        from_ip: str,
        to_ip: str,
        message_type: PaxosMessageType,
        round_identifier: str,
        message_content: Any,
    ):
        self.from_ip = from_ip
        self.to_ip = to_ip
        self.message_type = message_type
        
        self.round_identifier = round_identifier
        self.message_content = message_content

    def to_dict(self) -> dict:
        return {
            "from_ip": self.from_ip,
            "to_ip": self.to_ip,
            "message_type": self.message_type.name,
            "round_identifier": self.round_identifier,
            "message_content": self.message_content,
        }