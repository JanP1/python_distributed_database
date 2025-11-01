import datetime
from Sandbox.Paxos.paxos_messages import MessageBox, PaxosMessage, PaxosMessageType



class Node:
    def __init__(self, ip_addr, up_to_date) -> None:
        self.ID = int
        self.message_box: MessageBox = MessageBox()
        self.ip_addr: str = ip_addr
        self.log: Log = Log() 
        self.up_to_date: bool = up_to_date # does the log contain all accepted values

        self.highiest_promised_id = (0, 0)
        self.highiest_accepted_id = (0, 0)

        accepted_value = ""


    def get_ip(self):
        return self.ip_addr


    def change_ip(self, ip_addr: str):
        self.ip_addr = ip_addr

    
    def send_message(self, message_pool: list, target_ip: set, message: str, message_type: PaxosMessageType, round_identifier):
        """
            A method to add messages to the specified message_pool

            For simplisity it only appends the message.
            in the simulation the message is added to the current message_pool list,
            every step the current traffic list is checked and messages are 
            acted upon by nodes

            Args:
                message_pool (list): a list to which we append the messages.
        """
        current_time = str(datetime.datetime.now())

        for ip in target_ip:
            if ip != self.ip_addr:
                message_pool.append(PaxosMessage(self.ip_addr, ip, current_time, message_type, round_identifier, message))



    def recieve_message(self, message: PaxosMessage, message_pool: list):
        """
            A method to simulate recieving a message

            For simplisity if it needs to send a message in responce it is added to a specified message_pool.
            
            Note: The message pool needs to be a separate pool than the pool it was taken from to simulate steps of the process.
            
            Args:
                message (PaxosMessage): a message sent to the current node.
                message_pool (list): a list to which we append the messages.
        """

        match message.message_type:
            case PaxosMessageType.PREPARE:

                round_id = tuple(int(n) for n in message.proposal_number.split("."))

                if round_id > self.highiest_promised_id:
                    self.highiest_promised_id = round_id
                    print(f"==PROMISE_ID_UPDATE== Node || {self.ID} || updated highiest promised ID to {round_id[0]}.{round_id[1]}")
                
            case PaxosMessageType.PROMISE:
                pass
            case PaxosMessageType.ACCEPT:
                pass
            case PaxosMessageType.ACCEPTED:
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
