from collections import defaultdict
from datetime import datetime
from paxos_messages import MessageBox, PaxosMessage, PaxosMessageType


"""

            A Node is the representation of a single server

            
             __________                     __________
            |          |                   |          |
            |  []      |                   |  []      |
            | -------- |       ------>     | -------- | 
            | -------- |                   | -------- |
            | -------- |                   | -------- |
            L__________|                   L__________|

               Node()                         Node()


"""

class Node:
    def __init__(self, ip_addr: str, up_to_date: bool, ID: int) -> None:
        self.ID = ID
        self.accept_sent = False
        # # Message Box - for now instead of per-node message box, a message pool is used storing 
        # # all current messages and acting unpon them per step of the while loop
        #
        # self.message_box: MessageBox = MessageBox()

        self.ip_addr: str = ip_addr
        self.log: Log = Log() 

        self.up: bool = True # is the server working
        self.up_to_date: bool = up_to_date # does the log contain all accepted values

        self.highiest_promised_id: tuple[int, int] = (0, 0)

        # Not equal (0,0) if we previously accepted a request, but it didnt finish
        self.highiest_accepted_id: tuple[int, int] = (0, 0) 

        # Not equal "" if we proviously accepted a value at id == highiest_accepted_id
        self.accepted_value = ""

        self.promises_recieved = {}

        self.message_content = ""
        # self.current_phase = None

        # In the ACCEPTED phase every node receives values. It has to count which value reaches quorum to apply it
        # therefore a defaultdict is used to store {id: (value, count)}
        self.accepted_phase_values_id = 0
        self.accepted_phase_values = defaultdict(lambda: AcceptedValue())


    def reset_paxos_state(self):
        self.highiest_accepted_id = (0,0)
        self.highiest_promised_id = (0,0) 

        self.accepted_value = ""
        self.promises_recieved = {}
        self.message_content = ""
        self.accepted_phase_values_id = 0
        self.accepted_phase_values = defaultdict(lambda: AcceptedValue())

    def get_ip(self):
        return self.ip_addr


    def change_ip(self, ip_addr: str):
        self.ip_addr = ip_addr


    def send_message(self, message_pool: list, target_ip: list, message: str, message_type: PaxosMessageType, round_identifier):
        """
            A method to add messages to the specified message_pool

            For simplisity it only appends the message.
            In the simulation the message is added to the message_box of the recieving node.
            Args:
                message_pool (list): a list to which we append the messages.
                target_ip (set): a set of ips to which the message has to be sent.
        """

        for ip in target_ip:
            message_pool.append(PaxosMessage(self.ip_addr, ip, message_type, round_identifier, message))



    def recieve_message(self, message: PaxosMessage, message_pool: list, quorum: int, nodes_ips: list):
        """
            A method to simulate recieving a message

            For simplisity if it needs to send a message in responce it is added to a specified message_pool.
            
            Note: The message pool needs to be a separate pool than the pool it was taken from to simulate steps of the process.
            
            Args:
                message (PaxosMessage): a message sent to the current node.
                message_pool (list): a list to which we append the messages.
                nodes_ips (set): a set of all the ips in use, needed for broadcasting the ACCEPTED message
        """

        match message.message_type:

            case PaxosMessageType.PREPARE: # ---------------------------------------------------- recieving a PREPARE message

                round_id: tuple[int, int] = tuple(int(n) for n in message.round_identyfier.split("."))

                if round_id > self.highiest_promised_id:
                    self.highiest_promised_id = round_id
                    print(f"==PROMISE_ID_UPDATE== Node || {self.ID} || updated highiest promised ID to {round_id[0]}.{round_id[1]}")

                    return_message = f"{self.highiest_accepted_id[0]}.{self.highiest_accepted_id[1]};{message.message_content}"

                    if self.highiest_accepted_id != (0,0):
                        return_message = f"{self.highiest_accepted_id[0]}.{self.highiest_accepted_id[1]};{self.accepted_value}"                   

                    # If the proposed round_id is bigger, send an PROMISE message
                    self.send_message(
                            message_pool,
                            [message.from_ip],
                            return_message,
                            PaxosMessageType.PROMISE,
                            message.round_identyfier)
                
            case PaxosMessageType.PROMISE: # ---------------------------------------------------- recieving a PROMISE message

                self.promises_recieved[message.from_ip] = message.message_content
                
                accept_message_content = self.message_content
                
                # we have to make sure we dont sent accepts multiple times
                if len(self.promises_recieved) >= quorum and not self.accept_sent:

                    # if we reach quorum we need to check if any response came with an already accepted value
                    # and if yes i need to see which is the biggest

                    # if any delivered message contains an alraedy accepted value bigger
                    # than that we change the highiest accepted
                    highiest_accepted_number = (-1, -1)  


                    for promise in self.promises_recieved:
                        if self.promises_recieved[promise] == "":
                            continue

                        # we take the message from the current promise -> we split(";") and take the first el. "num1.num2" -> we split(".") and put in (num1, num2)
                        promise_accepted_id = tuple(int(acc) for acc in self.promises_recieved[promise].split(";")[0].split("."))

                        if promise_accepted_id > highiest_accepted_number:
                            highiest_accepted_number = promise_accepted_id

                            # if none will change this then accept_message_content will stay the message we first wanted to send -> slef.message_content
                            accept_message_content = self.promises_recieved[promise].split(";")[1]

                    self.accept_sent = True
                    # if we reach quorum we send an ACCEPT message to all nodes 
                    self.send_message(
                            message_pool,
                            nodes_ips,
                            accept_message_content,
                            PaxosMessageType.ACCEPT,
                            message.round_identyfier)


            case PaxosMessageType.ACCEPT: # ---------------------------------------------------- recieving an ACCEPT message

                # checking if the recieved message contains a round id bigger or equal to the one we store (the one promised in the PROMISE phase)
                if tuple(int(num) for num in message.round_identyfier.split(".")) >= self.highiest_promised_id:
                    self.highiest_accepted_number = message.round_identyfier
                    self.accepted_value = message.message_content
                    
                    self.send_message(
                            message_pool,
                            nodes_ips,
                            self.accepted_value,
                            PaxosMessageType.ACCEPTED,
                            self.highiest_accepted_number)

            case PaxosMessageType.ACCEPTED: # ---------------------------------------------------- recieving an ACCEPTED message

                # self.accepted_phase_values: dict[int, AcceptedValue]
                value_id = self.find_id_by_value(self.accepted_phase_values, message.message_content)

                if value_id is None:
                    self.accepted_phase_values_id += 1
                    value_id = self.accepted_phase_values_id
                    # create a new AcceptedValue instance
                    self.accepted_phase_values[value_id] = AcceptedValue(message.message_content, 0)

                # increment count
                self.accepted_phase_values[value_id].count += 1

                # check quorum
                if self.accepted_phase_values[value_id].count >= quorum:
                    # ------------------- apply to log here -------------------
                    self.log.append(self.highiest_promised_id,
                                    self.accepted_phase_values[value_id].value,
                                    datetime.now())
                    print(f"ID - {self.ID}\nQuorum reached for value: {self.accepted_phase_values[value_id].value}\n")

                    # ------------------- clear variables for next slot -------------------
                    self.reset_paxos_state()
                

    def find_id_by_value(self, accepted_dict, value_to_find):
        for id_, accepted_value_obj in accepted_dict.items():
            if accepted_value_obj.value == value_to_find:
                return id_
        return None

    def send_log_recovery(self, last_saved_index):
        # If a node wants to go back online it needs to catch up 
        # with the log
        return [entry for entry in self.log.replay(last_saved_index)]
    

    def request_log_recovery(self):
        pass



from dataclasses import dataclass

@dataclass
class AcceptedValue:
    value: str = ""
    count: int = 0

    def reset(self):
        """Reset fields to default values."""
        self.value = ""
        self.count = 0



class Log:
    def __init__(self):
        self.entries = []


    def append(self, request_number, message, timestamp):
        self.entries.append({
            "request_number": request_number,
            "timestamp": str(timestamp),
            "message": message
        })


    def replay(self, start_index=0):
        for entry in self.entries[start_index:]:
            yield entry

