import docker
import time
import os
import subprocess
import sqlite3
import math
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
import csv
import datetime

def distribute_new_followers(leaders, num_of_followers):
    follower_to_leader = []
    leader_index = 0

    for i in range(num_of_followers):
        leader = leaders[leader_index]
        follower_to_leader.append(leader)
        leader_index = (leader_index + 1) % len(leaders)
    return follower_to_leader

def create_node(index, leader, formula):
    if index == 0:
        command = f"--leader --leader-formula {formula}"
    else:
        command = f"-C {leader} --leader-formula {formula}"
    container = docker_client.containers.run(
        'fogmon',
        detach=True,
        name=f"node{index}",
        network=network_name,
        remove=True,
        command=command
    )
    return container

def create_nodes(n, nodes, delta_nodes, leaders, formula):
    if(leaders is not None and len(leaders)>1):
        num_of_leaders = len(leaders)
        l = list(leaders)
        leader_distribution = distribute_new_followers(l, delta_nodes)
    else:
        leader_distribution = ["node0"] * delta_nodes
    formulas = [formula] * delta_nodes
    #leader_distribution = ["node0"] * delta_nodes
    with ThreadPoolExecutor() as executor:
        containers = executor.map(create_node, range(n, n + delta_nodes), leader_distribution, formulas)
    nodes.extend(list(containers))
    print(f"Containers with image {image} created successfully!")
    return nodes


def copy_db_file(container, db_file_paths, output_dir):
    try:
        for db_file_path in db_file_paths:
            command = ["docker", "cp", f"{container.id}:{db_file_path}", f"{output_dir}/{container.name}_{db_file_path.split('/')[-1]}"]
            subprocess.run(command, check=True)
            #print(f"Successfully copied {db_file_path} from {container.id} to {output_dir}/{container.name}_{db_file_path.split('/')[-1]}")
    except Exception as e:
        print(f"Error while copying file from {container.id}: {e}")

def copy_db_files(db_file_paths, output_dir, nodes):
    with ThreadPoolExecutor() as executor:
        futures = []
        for container in nodes:
            futures.append(executor.submit(copy_db_file, container, db_file_paths, output_dir))
        for future in futures:
            future.result()



def get_start_timestamp_rows(number_of_nodes, target_leaders, path, run_before_timestamp):
    all_rows = []
    x = 0
    try:
        for i in range(number_of_nodes):
            db_path = f"{path}/node{i}_leader_node.db"
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT *, ? as node_id FROM Test", (f"node{i}",))  # Add 'node{i}' as a column
                rows_with_node_id = cursor.fetchall()
                if len(rows_with_node_id) == 0:
                    x = x + 1
                all_rows.extend(rows_with_node_id)
                conn.close()
            else:
                print(f"Database file {db_path} not found")
                x = x + 1
    except Exception as e:
        x = x + 1

    all_rows.sort(key=lambda x: x[3])

    leader_count = 0
    timestamp = None
    unique_nodes = set()
    leader_nodes = set()

    all_rows_after_last_convergence = []

    if run_before_timestamp:
        for row in all_rows:
            if str(row[3]) >= str(run_before_timestamp):
                all_rows_after_last_convergence.append(row)
    else:
        all_rows_after_last_convergence = all_rows

    
   
    for row in all_rows_after_last_convergence:
        if row[4] == 'True':  # isLeader = True
            unique_nodes.add(row[1])
            leader_nodes.add(row[5])
            if len(unique_nodes) >= target_leaders:
                timestamp = str(row[3])
                print("Precondition for Leader Count is matched")
                break
    all_rows_after_timestamp = []
    if timestamp:
        for row in all_rows_after_last_convergence:
            if str(row[3]) >= timestamp:
                all_rows_after_timestamp.append(row)
    else: 
        print("Precondition for Leader Count is not matched: no enough Leaders in the System")

    return timestamp, all_rows_after_timestamp, unique_nodes, leader_nodes, x


def get_message_to_converge_count(all_rows_after_timestamp, number_of_nodes, x):
    node_knowledge = {}
    message_count = 0
    leaders = set()
    for row in all_rows_after_timestamp:
        _, sender, receiver, timestamp, is_leader, _ = row
        message_count += 1
        if sender not in node_knowledge:
            node_knowledge[sender] = {sender}
        if receiver not in node_knowledge:
            node_knowledge[receiver] = {receiver} 
           
        sender_knowledge = node_knowledge[sender]
        receiver_knowledge = node_knowledge[receiver]
        receiver_knowledge.update(sender_knowledge)
        node_knowledge[receiver] = receiver_knowledge 
        treshold = n - x
        if is_leader == 'True':
            leaders.add(sender)
        if all(len(node_knowledge[leader]) >= treshold for leader in leaders):
            print(f"All leaders have complete knowledge: mc={message_count}")
            return message_count, timestamp
    return -1, -1


def stop_container(container):
    container.stop()
    container.remove()

def delete_nodes(nodes):
    with ThreadPoolExecutor() as executor:
        executor.map(stop_container, nodes)

def write_new_csv_file(n, leader_count,x, message_count, start_time, convergence_timestamp, i, output_dir, current_time):
    headers = ['node_count', 'leader_count', 'x', 'message_count', 'start_time', 'convergence_timestamp', 'run', 'current_time']
    data = {
        'node_count': n,
        'leader_count': leader_count,
        'x': x,
        'message_count': message_count,
        'start_time': start_time,
        'convergence_timestamp': convergence_timestamp,
        'run': i,
        'current_time': current_time
    }
    filename = f"{output_dir}/short_data_n_{n}_r_{i}.csv"
    with open(filename, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames = headers)
        writer.writeheader()
        writer.writerow(data)

def delete_all_containers():
    subprocess.call('sudo docker stop $(sudo docker ps -a -q)', shell=True)


def remove_container_by_name(container_name):
    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        container.remove(force=True)
        print(f"Container '{container_name}' removed successfully.")
    except docker.errors.NotFound:
        print(f"Container '{container_name}' not found.")



docker_client = docker.from_env()
network_name = "mynetwork"
db_file_path = ["leader_node.db", "leader_node.db-shm", "leader_node.db-wal"]


delta_nodes = [10]
leaders = None
run_before_timestamp = None

ns = [10,20,30,40,50,60,70,80]
ts = [3000,3000,3000,3000,3000,3000,3000,3000]
leader_formulas = ['0']
output_dirs = ["data_sqrt_fogmon"]
runs = 3


for index, formula in enumerate(leader_formulas):
    for r in range(0,runs): 
        nodes = []
        leaders = None
        run_before_timestamp = None
        for d, (n, t) in enumerate(zip(ns, ts)):
            create_nodes(len(nodes), nodes, delta_nodes[d], leaders, formula)
            #leader_counts = [math.floor((n**0.5)/2),math.floor(n**0.5),math.floor((n**0.5)*2)]
            #leader_count = leader_counts[index]
            leader_count = math.floor(n**0.5)
            print(f"leader_count: {leader_count}")
            print(f"n = {n}, t = {t}, formula = {leader_formulas[index]}")
            current_time = datetime.datetime.now()
            o_dir = output_dirs[index]
            if not os.path.exists(o_dir):
                os.mkdir(o_dir)
            path = f"{o_dir}/n_{n}run_{r}"
            os.mkdir(path)
            time.sleep(t)
            print(f"n = {n}, t = {t}")
            copy_db_files(db_file_path,path, nodes)
            print(f"Checking timestamp for Leadercount {leader_count}")
            start_timestamp, all_rows_after_start_timestamp, leaders_container_id, leaders, x = get_start_timestamp_rows(n, leader_count, path, run_before_timestamp)
            print("Start timestamp:", start_timestamp)
            convergence_message_count, convergence_timestamp = get_message_to_converge_count(all_rows_after_start_timestamp, n, x)
            print("Convergence message count:", convergence_message_count)
            print("Convergence timestamp:", convergence_timestamp)
            if convergence_timestamp and convergence_timestamp != -1:
                run_before_timestamp = convergence_timestamp
            else:
                run_before_timestamp = start_timestamp
            write_new_csv_file(n, len(leaders), x, convergence_message_count, start_timestamp, convergence_timestamp, r, o_dir, current_time)
            time.sleep(10)

        delete_nodes(nodes)
        time.sleep(30)
        delete_all_containers()
        time.sleep(30)
        
       






