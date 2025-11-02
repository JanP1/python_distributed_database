from re import split
from Sandbox.Paxos.paxos_messages import MessageBox, PaxosMessage, PaxosMessageType


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
    def __init__(self, ip_addr, up_to_date) -> None:
        self.ID = int

        # # Message Box - for now instead of per-node message box, a message pool is used storing 
        # # all current messages and acting unpon them per step of the while loop
        #
        # self.message_box: MessageBox = MessageBox()

        self.ip_addr: str = ip_addr
        self.log: Log = Log() 

        self.up: bool = True # is the server working
        self.up_to_date: bool = up_to_date # does the log contain all accepted values

        self.highiest_promised_id = (0, 0)

        # Not equal (0,0) if we previously accepted a request, but it didnt finish
        self.highiest_accepted_id = (0, 0) 

        # Not equal "" if we proviously accepted a value at id == highiest_accepted_id
        self.accepted_value = ""

        self.promises_recieved = {}

        self.message_content = ""
        # self.current_phase = None


    def get_ip(self):
        return self.ip_addr


    def change_ip(self, ip_addr: str):
        self.ip_addr = ip_addr


    def send_message(self, message_pool: list, target_ip: set, message: str, message_type: PaxosMessageType, round_identifier):
        """
            A method to add messages to the specified message_pool

            For simplisity it only appends the message.
            In the simulation the message is added to the message_box of the recieving node.
            Args:
                message_pool (list): a list to which we append the messages.
                target_ip (set): a set of ips to which the message has to be sent.
        """

        for ip in target_ip:
            if ip != self.ip_addr:
                message_pool.append(PaxosMessage(self.ip_addr, ip, message_type, round_identifier, message))



    def recieve_message(self, message: PaxosMessage, message_pool: list, num_of_nodes: int, nodes_ips: set = {None}):
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

                round_id = tuple(int(n) for n in message.round_identyfier.split("."))

                if round_id > self.highiest_promised_id:
                    self.highiest_promised_id = round_id
                    print(f"==PROMISE_ID_UPDATE== Node || {self.ID} || updated highiest promised ID to {round_id[0]}.{round_id[1]}")

                    return_message = ""

                    if self.highiest_accepted_id != (0,0):
                        return_message = f"{self.highiest_accepted_id[0]}.{self.highiest_accepted_id[1]};{self.accepted_value}"                   

                    # If the proposed round_id is bigger, send an PROMISE message
                    self.send_message(
                            message_pool,
                            set(message.from_ip),
                            return_message,
                            PaxosMessageType.PROMISE,
                            message.round_identyfier)
                
            case PaxosMessageType.PROMISE: # ---------------------------------------------------- recieving a PROMISE message

                self.promises_recieved[message.from_ip] = message.message_content
                
                quorum = num_of_nodes // 2 + 1

                accept_message_content = self.message_content
                
                if len(self.promises_recieved) >= quorum:

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


                    # if we reach quorum we send an ACCEPT message to all nodes 
                    for node_ip in nodes_ips:
                        self.send_message(
                                message_pool,
                                node_ip,
                                accept_message_content,
                                PaxosMessageType.ACCEPT,
                                message.round_identyfier)


            case PaxosMessageType.ACCEPT: # ---------------------------------------------------- recieving an ACCEPT message
                pass
            case PaxosMessageType.ACCEPTED: # ---------------------------------------------------- recieving an ACCEPTED message
                pass


    def send_log_recovery(self, last_saved_index):
        # If a node wants to go back online it needs to catch up 
        # with the log
        return [entry for entry in self.log.replay(last_saved_index)]
    

    def request_log_recovery(self):
        pass



class Log:
    def __init__(self):
        self.entries = []


    def append(self, request_number, message, timestamp):
        self.entries.append({
            "request_number": request_number,
            "timestamp": timestamp,
            "message": message
        })


    def replay(self, start_index=0):
        for entry in self.entries[start_index:]:
            yield entry
