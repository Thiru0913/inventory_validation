import yaml
import re
import os
import subprocess
import rich

# Define the pattern-to-group mapping 
PATTERN_TO_GROUP = {
    r"lauau2pefs.*": "l_aja_ausy01sr1",
    r"lauau1cefs.*": "l_aja_ausy02sr1",
    r"lcnhk01efs.*": "l_aja_cnhk01",
    r"lcnhk02efs.*": "l_aja_cnhk02",
    r"linch07efs.*": "l_aja_inch07sr1",
    r"linin0cefs.*": "l_aja_inmu02sr1",
    r"linin8pefs.*": "l_aja_inmu01sr1",
    r"linmu08efs.*": "l_aja_inmu08sr1",
    r"ljpsa01efs.*": "l_aja_jpsa01",
    r"ljpnz01efs.*": "l_aja_jpnz01",
    r"ljptk01efs.*": "l_aja_jptk01",
    r"lkrkr0pefs.*": "l_aja_kray01sr1",
    r"lkrkr0cefs.*": "l_aja_krse01sr2",
    r"lsgsg01efs.*": "l_aja_sgsg01",
    r"lsgsg02efs.*": "l_aja_sgsg02",
    r"ltwtp04efs.*": "l_aja_twtp04",
    r"ltwtw0pefs.*": "l_aja_twty01sr1",
    r"lukcm01efs.*": "l_emea_ukcm01",
    r"lukwg01efs.*": "l_emea_ukwg01",
    r"lusaz01efs.*": "l_amrs_usaz01",
    r"lusaz07efs.*": "l_amrs_usaz07",
    r"lusil05efs.*": "l_amrs_usil05",
    r"luspa01efs.*": "l_amrs_uspa01",
    r"lustx02efs.*": "l_amrs_ustx02",
    r"lusva01efs.*": "l_amrs_usva01",
}

# Define script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
efs_file = os.path.join(script_dir, 'efsservers.txt')


# Generate efsservers.txt dynamically in the script folder
cmd = f"efs display efsservers | sed -e '1,/^==*/d' | awk '{{print $2 \",\" $1 \",\" $3}}' > {efs_file}"
subprocess.run(cmd, shell=True, check=True)

# Load inventory yaml
inventory_file = os.path.join(script_dir, 'inventory.prod.yaml')
with open(inventory_file, 'r') as file:
    inventory1 = yaml.safe_load(file)

# Extract control group hosts
controlgroup_a1 = inventory1['all']['children']['controlgroup_a']['hosts']
controlgroup_b1 = inventory1['all']['children']['controlgroup_b']['hosts']

# Extract server group hosts
servertype_dev = set(inventory1['all']['children']['servertype_dev']['hosts'])
servertype_prod = set(inventory1['all']['children']['servertype_prod']['hosts'])

def load_efs_unique_servers(efs_file):
    """ Load unique EFS servers from the text file """
    servers = {}
    with open(efs_file, 'r') as file:
        for line in file:
            parts = line.strip().split(',')
            if len(parts) < 3:
                continue  # Skip malformed lines
            server_name, cell_name, host_type = parts
            servers[server_name] = (cell_name, host_type)  # Ensure uniqueness
    return servers

def load_efs_servers(efs_file):
    """ Load EFS servers from the text file """
    with open(efs_file, 'r') as file:
        return [line.strip().split(',') for line in file.readlines()]

# Load EFS servers
efs_servers1 = load_efs_unique_servers(efs_file)
efs_servers = load_efs_servers(efs_file)


# Set to store unique mismatches
mismatches_servergroup = set()

# Validate server placement
for server_nm in efs_servers:
    if len(server_nm) < 3:
        continue  # Skip malformed lines
    
    server_name_1, _, host_type = server_nm
    if server_name_1 in servertype_dev and host_type != 'dev':
        mismatches_servergroup.add(f"Mismatch: {server_name_1} {host_type} in servertype_dev but it should be in servertype_prod")
    elif server_name_1 in servertype_prod and host_type != 'prod':
        mismatches_servergroup.add(f"Mismatch: {server_name_1} {host_type} in servertype_prod but it should be in servertype_dev")

# Dictionaries to store server names under each group and type
group_counts = {
    'controlgroup_a': {'dev': [], 'prod': []},
    'controlgroup_b': {'dev': [], 'prod': []}
}

# Dictionary to track pairs by data center
data_center_pairs = {}

# Track assigned servers
assigned_servers = set()

# Check placement of each unique server
for server_name1, (cell_name, host_type) in efs_servers1.items():
    # Identify control group
    if server_name1 in controlgroup_a1:
        control_group = 'controlgroup_a'
    elif server_name1 in controlgroup_b1:
        control_group = 'controlgroup_b'
    else:
        continue  # Skip if the server is not part of any control group

# Track in the respective control group
    group_counts[control_group][host_type].append((server_name1, cell_name))
    assigned_servers.add(server_name1)

    # Track pairs by data center (cell_name)
    if cell_name not in data_center_pairs:
        data_center_pairs[cell_name] = {'controlgroup_a': {'dev': [], 'prod': []}, 
                                        'controlgroup_b': {'dev': [], 'prod': []}}

    data_center_pairs[cell_name][control_group][host_type].append(server_name1)

# Identify mismatches
mismatches = []

# Validate pairing per data center
for cell_name, groups in data_center_pairs.items():
    controlgroup_a_dev = groups['controlgroup_a']['dev']
    controlgroup_a_prod = groups['controlgroup_a']['prod']
    controlgroup_b_dev = groups['controlgroup_b']['dev']
    controlgroup_b_prod = groups['controlgroup_b']['prod']

    if len(controlgroup_a_dev) != len(controlgroup_a_prod) or len(controlgroup_b_dev) != len(controlgroup_b_prod):
        mismatches.append(f"\nMismatch in data center {cell_name}:")
        mismatches.append(f"controlgroup_a: {' '.join([f'{s} (dev)' for s in controlgroup_a_dev])} {' '.join([f'{s} (prod)' for s in controlgroup_a_prod])}")
        mismatches.append(f"controlgroup_b: {' '.join([f'{s} (dev)' for s in controlgroup_b_dev])} {' '.join([f'{s} (prod)' for s in controlgroup_b_prod])}")

# Validate total count of assigned servers (considering unique server names)
total_efs_count = len(efs_servers1)  # Unique servers
total_assigned_count = len(assigned_servers)

if total_assigned_count != total_efs_count:
    mismatches.append(f"Total server count mismatch: expected {total_efs_count}, but assigned {total_assigned_count}")
    
    unassigned_servers = [server for server in efs_servers1.keys() if server not in assigned_servers]
    mismatches.append(f"Unassigned servers: {' '.join(unassigned_servers)}")
# Function to load the YAML inventory file
def load_inventory(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)



# Function to determine the group for a new server based on its name using the pattern-to-group mapping
def determine_group_from_pattern(server_name):
    for pattern, group in PATTERN_TO_GROUP.items():
        if re.match(pattern, server_name):
            return group
    return "Unknown Group"  # Default if no match found

def parse_efsservers(file_path):
    """Parse efsservers.txt to extract server names and their expected cells."""
    server_data = {}
    with open(file_path, "r") as file:
        for line in file:
            parts = line.strip().split(",")
            if len(parts) >= 3:
                server, cell, _ = parts
                if server not in server_data:
                    server_data[server] = set()
                server_data[server].add(cell)
    return server_data

def parse_inventory(file_path):
    """Parse inventory-prod.yaml to extract actual cells for servers."""
    with open(file_path, "r") as file:
        inventory = yaml.safe_load(file)

    inventory_data = {}
    all_groups = inventory.get('all', {}).get('children', {})

    # Only process groups that match PATTERN_TO_GROUP
    for group, group_data in all_groups.items():
        if group in PATTERN_TO_GROUP.values() and "hosts" in group_data and isinstance(group_data["hosts"], dict):        
            for server, server_info in group_data["hosts"].items():
                if isinstance(server_info, dict):
                    inventory_data[server] = set(server_info.get("cells", []))

    return inventory_data

def compare_cells(efsservers_data, inventory_data):
    """Compare expected and actual cells and print discrepancies to console."""
    missing_servers = list(set(efsservers_data.keys()) - set(inventory_data.keys()))
    extra_servers = list(set(inventory_data.keys()) - set(efsservers_data.keys()))
    
    if missing_servers:
        print("Missing servers in inventory:")
        print("========================================================")
        for server in missing_servers:
            print(f"  {server}")

    if extra_servers:
        print("\nExtra servers in inventory:")
        print("========================================================")
        for server in extra_servers:
            print(f"  {server}")

    for server, expected_cells in efsservers_data.items():
        group = determine_group_from_pattern(server)
        if not group:
            print(f"Server {server} does not match any known group.")
            continue
        
        actual_cells = inventory_data.get(server, set())
        if not actual_cells:  # If actual is empty, mark it as a new server
            print("\nMismatch for server:")
            print("========================================================")
            print(f"{server} in group {group}:")
            print(f"  Efs Database: {expected_cells}")
            print(f"  Ax inventory:   (New Server)")
        elif expected_cells != actual_cells:
            print(f"{server} in group {group}:")
            print(f"  Efs Database: {expected_cells}")
            print(f"  Ax inventory:   {actual_cells}")

    if mismatches_servergroup:
        print("\nServers group validation:")
        print("========================================================")
        print("\n".join(mismatches_servergroup))
    else:
        print("========================================================")
        print("All servers are in the correct groups.\n")

    if mismatches:
        print("\nControl Group Validation:")
        print("========================================================")
        print("\n".join(mismatches))
    else:
        print("========================================================")
        print("Controlgroup A and B are correctly balanced for high availability.\n")

def validate_inventory_with_efs(inventory_file, efs_file):
    """Wrapper function to parse files and compare inventory with EFS."""
    efsservers_data = parse_efsservers(efs_file)
    inventory_data = parse_inventory(inventory_file)    
    compare_cells(efsservers_data, inventory_data)

# Call the function
validate_inventory_with_efs(inventory_file, efs_file)
