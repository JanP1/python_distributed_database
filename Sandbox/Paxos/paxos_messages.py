from enum import Enum
from dataclasses import dataclass
from typing import Any



class PaxosMessageType(Enum):
    PREPARE = 1
    PROMISE = 2
    ACCEPT = 3
    ACCEPTED = 4


    def __str__(self):
        return f"{self.name}"

# This class is not crutial for now, the program will used two 
# unified message pools for current_messages in network and next_step_messages
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
    message_type: PaxosMessageType
    round_identyfier: str
    message_content: Any = None


    def to_string(self) -> str:
        return (f"{self.from_ip}|{self.to_ip}|{self.message_type}|{self.round_identyfier}|{self.message_content}")


    def __str__(self) -> str:
        
        return (
                f"\n-----------------------\n"
                f"From ip: {self.from_ip}\nTo ip: {self.to_ip}| Type: {self.message_type}| Round: {self.round_identyfier}\n"
                f"-----------------------\n"
                f"{self.message_content}\n"
                )


    @classmethod
    def message_from_string(cls, paxos_message_string: str):
        parts = paxos_message_string.split("|", 4)

        if len(parts) < 4:
            raise ValueError(f"Invalid message format: {paxos_message_string}")

        from_ip, to_ip, message_type, round_identyfier, *content = parts
        message_content = content[0] if content else None
        message_type = PaxosMessageType[message_type]

        return cls(from_ip, to_ip, message_type, round_identyfier, message_content)


