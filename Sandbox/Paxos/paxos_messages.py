from collections import defaultdict
import queue
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
        A class to represent a Message Box.

        Attributes:
            message_slots (defaultdict): a dictionary containing slots and corresponding messages.
    """


    def __init__(self):

        """
            Initialize a MessageBox instance with an empty message_slots dictionary.

            message_slots is a defaultdict where each key maps to a queue.Queue instance.
        """

        self.message_slots = defaultdict(queue.Queue)
    

    def put(self, slot_id, message):

        """
            Put a message into the queue corresponding to the given slot_id.

            Args:
                slot_id (hashable): The key identifying the message slot.
                message (any): The message to store.
        """

        self.message_slots[slot_id].put(message)

    
    def get(self, slot_id):

        """
            Retrieve a message from the queue of the given slot_id, if available.

            Args:
                slot_id (hashable): The key identifying the message slot.

            Returns:
                any or None: The next message from the queue, or None if the queue is empty.
        """

        try:
            return self.message_slots[slot_id].get_nowait()
        except queue.Empty:
            return None



@dataclass
class PaxosMessage:
    from_id: str
    to_id: str
    message_type: PaxosMessageType
    proposal_number: int
    message_content: Any = None


    def __str__(self) -> str:
        return (f"{self.from_id}|{self.to_id}|{self.message_type}|{self.proposal_number}|{self.message_content}")


    @classmethod
    def message_from_string(cls, paxos_message_string: str):
        parts = paxos_message_string.split("|", 4)

        if len(parts) < 4:
            raise ValueError(f"Invalid message format: {paxos_message_string}")

        from_id, to_id, message_type, proposal_number, *content = parts
        message_content = content[0] if content else None
        message_type = PaxosMessageType[message_type]

        return cls(from_id, to_id, message_type, int(proposal_number), message_content)


