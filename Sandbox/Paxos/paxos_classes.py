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


