import time
from paxos_messages import PaxosMessageType
from paxos_nodes import Node

ips = ["192.168.1.10", "192.168.1.11", "192.168.1.12", "192.168.1.14"]
node1 = Node(ips[0], True, 8)
node2 = Node(ips[1], True, 1)
node3 = Node(ips[2], True, 2)
node4 = Node(ips[3], True, 4)

node2.highiest_accepted_id = (21, 1)
node2.accepted_value = "test"


pool = []
next_pool = []

node1.send_message(pool, ips, "Change name to Alice", PaxosMessageType.PREPARE, "23.8")

while True:
    next_pool = []
    for message in pool:
        match message.to_ip:
            case node1.ip_addr:
                print(f"ID - {node1.ID}\n recieved a {str(message.message_type)} message from {message.from_ip}")
                node1.recieve_message(message, next_pool, 3, ips)
            case node2.ip_addr:
                print(f"ID - {node1.ID}\n recieved a {str(message.message_type)} message from {message.from_ip}")
                node2.recieve_message(message, next_pool, 3, ips)
            case node3.ip_addr:
                print(f"ID - {node3.ID}\n recieved a {str(message.message_type)} message from {message.from_ip}")
                node3.recieve_message(message, next_pool, 3, ips)
            case node4.ip_addr:
                print(f"ID - {node4.ID}\n recieved a {str(message.message_type)} message from {message.from_ip}")
                node4.recieve_message(message, next_pool, 3, ips)
 
    print(f"Log1 {node1.log.entries}")
    print(f"Log2 {node2.log.entries}")
    print(f"Log3 {node3.log.entries}")
    print(f"Log4 {node4.log.entries}")
    print("Step", 20*"--")
    pool = next_pool
    time.sleep(0.5)

