from enum import Enum
from dataclasses import dataclass
from typing import Any


class RaftMessageType(Enum):
    REQUEST_VOTE = 1
    VOTE = 2
    APPEND_ENTRIES = 3
    APPEND_RESPONSE = 4

    def __str__(self):
        return f"{self.name}"


@dataclass
class RaftMessage:
    from_ip: str
    to_ip: str
    message_type: RaftMessageType
    term: int
    message_content: Any = None

    def to_string(self) -> str:
        return f"{self.from_ip}|{self.to_ip}|{self.message_type}|{self.term}|{self.message_content}"

    def __str__(self) -> str:
        return (
            f"\n-----------------------\n"
            f"From ip: {self.from_ip}\nTo ip: {self.to_ip}| Type: {self.message_type}| Term: {self.term}\n"
            f"-----------------------\n"
            f"{self.message_content}\n"
        )
