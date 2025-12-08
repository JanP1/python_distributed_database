# raft_messages.py
from enum import Enum
from typing import Any


class RaftMessageType(Enum):
    REQUEST_VOTE = 1
    VOTE = 2
    APPEND_ENTRIES = 3
    APPEND_RESPONSE = 4


class RaftMessage:
    """
    Uniwersalna wiadomość używana między węzłami Raft, zgodna z JSON payloadem:

    {
        "from_ip": "...",
        "to_ip": "...",
        "message_type": "REQUEST_VOTE",
        "term": 5,
        "message_content": {...}
    }
    """

    def __init__(
        self,
        from_ip: str,
        to_ip: str,
        message_type: RaftMessageType,
        term: int,
        message_content: Any,
    ):
        self.from_ip = from_ip
        self.to_ip = to_ip
        self.message_type = message_type
        self.term = term
        self.message_content = message_content

    def to_dict(self) -> dict:
        """Konwersja do formatu, który można wrzucić do JSON."""
        return {
            "from_ip": self.from_ip,
            "to_ip": self.to_ip,
            "message_type": self.message_type.name,
            "term": self.term,
            "message_content": self.message_content,
        }

    @staticmethod
    def from_dict(d: dict) -> "RaftMessage":
        """Konwersja z obiektu JSON z powrotem na RaftMessage."""
        return RaftMessage(
            from_ip=d["from_ip"],
            to_ip=d["to_ip"],
            message_type=RaftMessageType[d["message_type"]],
            term=d["term"],
            message_content=d.get("message_content"),
        )

    def __repr__(self) -> str:
        return (
            f"RaftMessage({self.from_ip} -> {self.to_ip}, "
            f"type={self.message_type.name}, term={self.term}, content={self.message_content})"
        )
