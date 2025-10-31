from Sandbox.Paxos.paxos_messages import MessageBox, PaxosMessage



class Node:
    def __init__(self, ip_addr, up_to_date) -> None:
        self.message_box: MessageBox = MessageBox()
        self.ip_addr: str = ip_addr
        self.log: Log = Log() 
        self.up_to_date: bool = up_to_date # does the log contain all accepted values


    def get_ip(self):
        return self.ip_addr


    def change_ip(self, ip_addr: str):
        self.ip_addr = ip_addr

    
    def send_message(self, message: PaxosMessage):
        pass
        


    # If a node wants to go back online it needs to catch up 
    # with the log
    def send_log_recovery(self, last_saved_index):
        for entry in self.log.replay(last_saved_index):
            pass

    
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
