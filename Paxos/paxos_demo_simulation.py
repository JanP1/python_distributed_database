import time
from paxos_messages import PaxosMessageType
from paxos_nodes import Node

ACCOUNT_A = 'ACCOUNT_A'
ACCOUNT_B = 'ACCOUNT_B'

ips = ["192.168.1.10", "192.168.1.11", "192.168.1.12", "192.168.1.14"]

node1 = Node(ips[0], True, 8)
node2 = Node(ips[1], True, 1)
node3 = Node(ips[2], True, 2)
node4 = Node(ips[3], True, 4)

node2.highiest_accepted_id = (25, 1)
node2.accepted_value = f"TRANSFER;{ACCOUNT_B};{ACCOUNT_A};50.00;TX_ID:T2" # Wartość z T2


pool = []
next_pool = []
quorum = 3 # wymagana liczba węzłów do kworum

# --- Scenerio risk of deadlock ---
# T1 (node1): A -> B (tries to lock A then B)
# T2 (node2): B -> A (tries to lock B then A) - node2 already has higher ID/priority

# Send T1 (node1 - Proposer)
tx_id_1 = "T1"
# Format: TX_TYPE;FROM_ACCOUNT;TO_ACCOUNT;AMOUNT;TX_ID:ID
message_t1 = f"TRANSFER;{ACCOUNT_A};{ACCOUNT_B};150.00;TX_ID:{tx_id_1}" 
node1.set_new_proposal(message_t1, (26, 1))
node1.send_message(pool, ips, message_t1, PaxosMessageType.PREPARE, "26.1")

# Send T2 (node2 - Proposer node2)
# node2 has higher ID, so it will dominate PREPARE/PROMISE for slot, but T1 will locked ACCOUNT_A first if it be faster
tx_id_2 = "T2"
message_t2 = f"TRANSFER;{ACCOUNT_B};{ACCOUNT_A};50.00;TX_ID:{tx_id_2}"
node2.set_new_proposal(message_t2, (26, 2))
node2.send_message(pool, ips, message_t2, PaxosMessageType.PREPARE, "26.2")

while True:
    next_pool = []
    
    # ------------------- Account balance -------------------
    print(f"\n--- Account balance step by step ---")
    print(f"A1: {node1.accounts['ACCOUNT_A']} | B1: {node1.accounts['ACCOUNT_B']}")
    print(f"A2: {node2.accounts['ACCOUNT_A']} | B2: {node2.accounts['ACCOUNT_B']}")
    print(f"A3: {node3.accounts['ACCOUNT_A']} | B3: {node3.accounts['ACCOUNT_B']}")
    print(f"A4: {node4.accounts['ACCOUNT_A']} | B4: {node4.accounts['ACCOUNT_B']}")
    print(f"---------------------------\n")

    if not pool:
        print("No message in pool. Stopping the simulation.")
        break
    
    for message in pool:
        match message.to_ip:
            case node1.ip_addr:
                print(f"ID - {node1.ID}\n recieved a {str(message.message_type)} message from {message.from_ip}")
                node1.receive_message(message, next_pool, 3, ips)
            case node2.ip_addr:
                print(f"ID - {node1.ID}\n recieved a {str(message.message_type)} message from {message.from_ip}")
                node2.receive_message(message, next_pool, 3, ips)
            case node3.ip_addr:
                print(f"ID - {node3.ID}\n recieved a {str(message.message_type)} message from {message.from_ip}")
                node3.receive_message(message, next_pool, 3, ips)
            case node4.ip_addr:
                print(f"ID - {node4.ID}\n recieved a {str(message.message_type)} message from {message.from_ip}")
                node4.receive_message(message, next_pool, 3, ips)
 
    print(f"Log1 {node1.log.entries}")
    print(f"Log2 {node2.log.entries}")
    print(f"Log3 {node3.log.entries}")
    print(f"Log4 {node4.log.entries}")
    print("Step", 20*"--")
    pool = next_pool
    time.sleep(0.5)

