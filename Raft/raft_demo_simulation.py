import time
from raft_messages import RaftMessageType
from raft_nodes import Node


ips = ["192.168.1.10", "192.168.1.11", "192.168.1.12", "192.168.1.14"]
node1 = Node(ips[0], True, 1)
node2 = Node(ips[1], True, 2)
node3 = Node(ips[2], True, 3)
node4 = Node(ips[3], True, 4)

nodes = {
    node1.ip_addr: node1,
    node2.ip_addr: node2,
    node3.ip_addr: node3,
    node4.ip_addr: node4,
}

pool = []
next_pool = []

# Start election: node1 becomes candidate for term 1
node1.current_term = 1
node1.role = "candidate"
node1.votes_received = set()
# request votes from others
node1.send_message(
    pool,
    [ip for ip in ips if ip != node1.ip_addr],
    RaftMessageType.REQUEST_VOTE,
    node1.current_term,
    node1.ip_addr,
)

# after leader emerges we'll have it append a new entry proposing the change
added_proposal = False

while True:
    next_pool = []
    for message in pool:
        target = nodes.get(message.to_ip)
        if not target:
            continue
        print(
            f"Node target {target.ID} ({target.ip_addr}) received {message.message_type} from {message.from_ip}"
        )
        target.receive_message(message, next_pool, 3, ips)

    # If a leader exists and hasn't proposed an entry yet, leader will propose one
    for n in nodes.values():
        if n.role == "leader" and not added_proposal:
            # leader proposes a client change
            proposal = "Change name to Alice"
            n.log.append((n.current_term, len(n.log.entries)), None, proposal)
            # send append entries with the new entry
            n.send_message(
                next_pool,
                ips,
                RaftMessageType.APPEND_ENTRIES,
                n.current_term,
                {"entries": [proposal], "leader": n.ip_addr},
            )
            added_proposal = True

    # Print logs
    print(f"Log1 {node1.log.entries}")
    print(f"Log2 {node2.log.entries}")
    print(f"Log3 {node3.log.entries}")
    print(f"Log4 {node4.log.entries}")
    print("Step", 20 * "--")
    pool = next_pool
    time.sleep(0.5)
