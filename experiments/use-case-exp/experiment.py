import csv
import sys

import geopy.distance as distance
from config import settings
import random
import utils
import requests



result = { "fail_rate": settings.failure_rate, 
          "cpu_threshold": settings.cpu_threshold,
          "total_offloading_requests": 0,
          "total_successful_offloads": 0,
          "qos_violations": 0
         }

def _normalize_distance_to_latency_range(dist: float):
    return ((settings.max_latency - settings.min_latency) * (dist - settings.min_dist) / (settings.max_dist - settings.min_dist)) + settings.min_latency


def _compute_minmax_distances(users: list[dict], servers: list[dict]):
    min_dist = sys.maxsize
    max_dist = 0
    for user in users:
        for server in servers:
            user_coordinates = (user['latitude'], user['longitude'])
            server_coordinates = (server['latitude'], server['longitude'])
            dist = distance.distance(user_coordinates, server_coordinates).meters
            if dist > max_dist:
                max_dist = dist
            if dist < min_dist:
                min_dist = dist

    return min_dist, max_dist


def _sort_edge_serves_by_latency(user: dict, edge_servers: list[dict]):
    user_coordinates = (user['latitude'], user['longitude'])

    for server in edge_servers:
        server_coordinates = (server['latitude'], server['longitude'])
        dist = distance.distance(user_coordinates, server_coordinates).meters
        server['distance'] = dist
        server['latency'] = _normalize_distance_to_latency_range(server['distance'])

    return sorted(edge_servers, key=lambda s: s['latency'])


def _perform_offloading(user: dict, ranked_servers: list[dict]):
   
    print(f"### User {user['latitude'], user['longitude']}-  offloading the task")
    offload_status = False
    #Get failed nodes
    fail_nodes = _get_failed_nodes(ranked_servers)
    target_nodes = []
    for node in ranked_servers:
        if node in fail_nodes:
            continue
        target_nodes.append(node)
    
    print("Total Nodes: {} and Failed Nodes: {} and Target Nodes:{}".format(len(ranked_servers), len (fail_nodes), len(target_nodes)))
    # Get the monitoring information
    monitoring_info = _perfrom_remote_query(target_nodes)

    if  bool(monitoring_info) and monitoring_info.ok:
        offload_node_ip = _get_offload_node(monitoring_info.json(), target_nodes)

        if offload_node_ip is not None:
            offload_status = _offload_task(offload_node_ip)
            print ("#### offload status: {}".format(offload_status))
           

        else:
            print ("#### Query failed as no suitable node found to offload")
    return offload_status
    

   

def _perfrom_remote_query(target_nodes: list[dict]):    
    try:    
        monitoring_info = {}
        is_query_done = False
        nearest_query_node = None
        # API call to the nearest node
        while not is_query_done:
            nearest_query_node = next(iter(target_nodes))
            monitoring_info = requests.get("http://{}:{}/get_recent_data_from_node".format(nearest_query_node['ip'],  nearest_query_node["port"]), timeout=120)
            print (f"Monitoring info query to node: {nearest_query_node['ip']}, status: {monitoring_info}")
            if monitoring_info.ok:
                is_query_done = True      

        if is_query_done:
            return monitoring_info
        else:
             print("Monitoring information is not found, exiting the offloading request") 
                     
    except Exception as e:
        print("### Error: {}".format(e.__traceback__))

def _get_offload_node(monitoring_info, target_servers):
    offload_node_ip = None
    count =0 
    for node in target_servers:
        appState = monitoring_info["{}:{}".format(node['ip'], 5000)]['appSate']
        print(f"Node IP: {node ['ip']}, app state: {appState}")
        if float(appState['cpu']) < settings.cpu_threshold:
            offload_node_ip = node['ip']
            break
        else:
            result['qos_violations'] += 1
            count += 1
    print (f"#### Number of skips from nearest node due to QoS violation for the current query: {count}")
    return offload_node_ip             

        
    
def _offload_task(node_ip):
    offload_status = utils.offload_object_detection_task(node_ip)
    return offload_status
   

    
def _get_failed_nodes (ranked_servers: list[dict]):
    number_of_failed_nodes = (int)(len(ranked_servers) * settings.failure_rate)
    print("Number of failed nodes:{}".format(number_of_failed_nodes))
    fail_nodes = random.sample(ranked_servers,  number_of_failed_nodes)

    return fail_nodes



def main():

    if len(sys.argv) != 2:
        raise ValueError("Argument list is wrong. Please use the following format:  {} {}".
                     format("pythone experiment.py", "start_monitoring[True/False]"))

    start_monitoring = str(sys.argv[1])
    users = utils.load_csv_dataset_as_dict(settings.users_dataset_filepath)
    edge_servers = utils.load_csv_dataset_as_dict(settings.edge_servers_dataset_filepath)

    min_dist, max_dist = _compute_minmax_distances(users, edge_servers)
    settings.min_dist = min_dist
    settings.max_dist = max_dist

    # start gossip monitoring inside the Rpis
    if start_monitoring == "True":
        utils.start_all_nodes (edge_servers)
    # prepare for offloading task request
    for user in users:
        
        result['total_offloading_requests'] += 1 
        print(f"###### Query Number: {result['total_offloading_requests']}")
        servers_by_latency = _sort_edge_serves_by_latency(user, edge_servers)

        offload_status = _perform_offloading(user, servers_by_latency)
        if offload_status:
            result['total_successful_offloads'] += 1


    print (f" CPU threshold: {settings.cpu_threshold}, total offload requests: {result['total_offloading_requests']}, successful offloads {result['total_successful_offloads']}, qos violations = {result['qos_violations']}" )
    with open('data/experiment-output.csv', 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        # writer.writeheader()
        writer.writerow(result)

if __name__ == '__main__':
    main()
