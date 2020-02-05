import argparse
from collections import defaultdict
import logging
import os
import random
from datetime import datetime
from spinterface import SimulatorAction
from common.common_functionalities import normalize_scheduling_probabilities, create_input_file
from siminterface.simulator import Simulator
from shutil import copyfile
from pathlib import Path

log = logging.getLogger(__name__)
DATETIME = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def copy_input_files(target_dir, network_path, service_path, sim_config_path):
    """Create the results directory and copy input files"""
    new_network_path = f"{target_dir}/{os.path.basename(network_path)}"
    new_service_path = f"{target_dir}/{os.path.basename(service_path)}"
    new_sim_config_path = f"{target_dir}/{os.path.basename(sim_config_path)}"

    os.makedirs(target_dir, exist_ok=True)
    copyfile(network_path, new_network_path)
    copyfile(service_path, new_service_path)
    copyfile(sim_config_path, new_sim_config_path)


def get_ingress_nodes(network):
    """
    Gets a NetworkX DiGraph and returns a list of ingress nodes in the network
    Parameters:
        network: NetworkX Digraph
    Returns:
        ing_nodes : a list of Ingress nodes in the Network
    """
    ing_nodes = []
    for node in network.nodes(data=True):
        if node[1]["type"] == "Ingress":
            ing_nodes.append(node[0])
    return ing_nodes


def get_project_root():
    """Returns project's root folder."""
    return str(Path(__file__).parent.parent.parent)


def get_placement(nodes_list, sf_list):
    """  places each sf in each node of the network

    Parameters:
        nodes_list
        sf_list

    Returns:
        a Dictionary with:
            key = nodes of the network
            value = list of all the SFs in the network
    """
    placement = defaultdict(list)
    for node in nodes_list:
        placement[node] = sf_list
    return placement


def get_schedule(nodes_list, sf_list, sfc_list):
    """  return a dict of schedule for each node of the network
       '''
        Schedule is of the following form:
            schedule : dict
                {
                    'node id' : dict
                    {
                        'SFC id' : dict
                        {
                            'SF id' : dict
                            {
                                'node id' : float (Inclusive of zero values)
                            }
                        }
                    }
                }
        '''
    Parameters:
        nodes_list
        sf_list
        sfc_list

    Returns:
         schedule of the form shown above
    """
    schedule = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(float))))
    for outer_node in nodes_list:
        for sfc in sfc_list:
            for sf in sf_list:
                # all 0's list
                uniform_prob_list = [0 for _ in range(len(nodes_list))]
                # Uniformly distributing the schedules between all nodes
                uniform_prob_list = normalize_scheduling_probabilities(uniform_prob_list)
                for inner_node in nodes_list:
                    schedule[outer_node][sfc][sf][inner_node] = uniform_prob_list.pop()
    return schedule


def parse_args():
    parser = argparse.ArgumentParser(description="Load Balance Algorithm")
    parser.add_argument('-i', '--iterations', required=False, default=10, dest="iterations", type=int)
    parser.add_argument('-s', '--seed', required=False, dest="seed", type=int)
    parser.add_argument('-n', '--network', required=True, dest='network')
    parser.add_argument('-sf', '--service_functions', required=True, dest="service_functions")
    parser.add_argument('-c', '--config', required=True, dest="config")
    return parser.parse_args()


def main():
    # Parse arguments
    args = parse_args()
    if not args.seed:
        args.seed = random.randint(1, 9999)
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(filename="logs/{}_{}_{}.log".format(os.path.basename(args.network),
                                                            DATETIME, args.seed), level=logging.INFO)
    logging.getLogger("coordsim").setLevel(logging.WARNING)

    # Creating the results directory variable where the simulator result files will be written
    network_stem = os.path.splitext(os.path.basename(args.network))[0]
    service_function_stem = os.path.splitext(os.path.basename(args.service_functions))[0]
    simulator_config_stem = os.path.splitext(os.path.basename(args.config))[0]

    results_dir = f"{get_project_root()}/results/{network_stem}/{service_function_stem}/{simulator_config_stem}" \
                  f"/{DATETIME}_seed{args.seed}"

    # creating the simulator
    simulator = Simulator(os.path.abspath(args.network),
                          os.path.abspath(args.service_functions),
                          os.path.abspath(args.config), test_mode=True, test_dir=results_dir)
    init_state = simulator.init(args.seed)
    log.info("Network Stats after init(): %s", init_state.network_stats)
    nodes_list = [node['id'] for node in init_state.network.get('nodes')]
    sf_list = list(init_state.service_functions.keys())
    sfc_list = list(init_state.sfcs.keys())
    ingress_nodes = get_ingress_nodes(simulator.network)
    # we place every sf in each node of the network, so placement is calculated only once
    placement = get_placement(nodes_list, sf_list)
    # Uniformly distributing the schedule for all Nodes
    schedule = get_schedule(nodes_list, sf_list, sfc_list)
    action = SimulatorAction(placement, schedule)
    # iterations define the number of time we wanna call apply()
    for i in range(args.iterations):
        apply_state = simulator.apply(action)
        log.info("Network Stats after apply() # %s: %s", i + 1, apply_state.network_stats)
    copy_input_files(results_dir, os.path.abspath(args.network), os.path.abspath(args.service_functions),
                     os.path.abspath(args.config))
    create_input_file(results_dir, len(ingress_nodes), "LoadBalance")


if __name__ == '__main__':
    main()
