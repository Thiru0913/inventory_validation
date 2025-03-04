import yaml
import re

# Define the pattern-to-group mapping (same as before)
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

inventory_file = 'inventory-prod.yaml'  # Replace with your YAML inventory file path
efs_file = 'efsservers.txt'  # Replace with your EFS server file path
output_file = 'validation_output.txt'  # Path to save the output file

# Load inventory yaml
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
        mismatches.append(f"Mismatch in data center {cell_name}:")
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

# Function to extract all server names and their cells from the YAML inventory
def extract_servers_and_cells_from_inventory(inventory):
    server_cells = {}
    server_groups = {}  # To store the group name for each server
    try:
        # Check if 'all' key exists and loop through the children groups
        all_groups = inventory.get('all', {}).get('children', {})
        for group, group_data in all_groups.items():
            if isinstance(group_data, dict):  # Ensure group_data is a dictionary
                hosts = group_data.get('hosts', {})
                for host, data in hosts.items():
                    cells = data.get('cells', [])
                    server_cells[host] = cells
                    server_groups[host] = group  # Store the group for each server
            else:
                print(f"Skipping invalid group {group}: {group_data}")
    except Exception as e:
        print(f"Error extracting servers and cells: {e}")
    return server_cells, server_groups

# Function to determine the group for a new server based on its name using the pattern-to-group mapping
def determine_group_from_pattern(server_name):
    for pattern, group in PATTERN_TO_GROUP.items():
        if re.match(pattern, server_name):
            return group
    return "Unknown Group"  # Default if no match found

# Function to validate the inventory with efsservers.txt and write results to a file
def validate_inventory_with_efs(inventory_file, efs_file, output_file):
    inventory = load_inventory(inventory_file)
    efs_servers = load_efs_servers(efs_file)
    server_cells_in_inventory, server_groups_in_inventory = extract_servers_and_cells_from_inventory(inventory)

    missing_servers = []
    extra_servers_in_inventory = []
    cell_mismatches = {}
    incorrect_group_servers = []
    controlgroup_mismatches = []

    # Aggregate cells from efsservers.txt for each server
    expected_cells_by_server = {}
    controlgroup_a_servers = {'dev': [], 'prod': []}
    controlgroup_b_servers = {'dev': [], 'prod': []}

    for efs_server in efs_servers:
        server_name, cell_name, hosttype = efs_server
        if server_name not in expected_cells_by_server:
            expected_cells_by_server[server_name] = set()
        expected_cells_by_server[server_name].add(cell_name)

        # Group validation for prod/dev based on hosttype
        group = server_groups_in_inventory.get(server_name, "Unknown Group")  # Default to "Unknown Group"
        
        if hosttype == 'prod' and group != 'servertype_prod':
            if group == 'servertype_dev':  # If it's found in 'servertype_dev' but expected in 'servertype_prod'
                incorrect_group_servers.append((server_name, f'Expected: servertype_prod, Found: {group}'))
        elif hosttype == 'dev' and group != 'servertype_dev':
            if group == 'servertype_prod':  # If it's found in 'servertype_prod' but expected in 'servertype_dev'
                incorrect_group_servers.append((server_name, f'Expected: servertype_dev, Found: {group}'))

        # Now, check control group distribution based on hosttype (dev/prod)
        controlgroup = server_groups_in_inventory.get(server_name, 'Unknown Group')

        # Add servers to appropriate controlgroup_a or controlgroup_b
        if 'controlgroup_a' in controlgroup:
            if hosttype == 'dev':
                controlgroup_a_servers['dev'].append(server_name)
            elif hosttype == 'prod':
                controlgroup_a_servers['prod'].append(server_name)
        elif 'controlgroup_b' in controlgroup:
            if hosttype == 'dev':
                controlgroup_b_servers['dev'].append(server_name)
            elif hosttype == 'prod':
                controlgroup_b_servers['prod'].append(server_name)

    # Validate EFS servers against the inventory
    for server_name, expected_cells in expected_cells_by_server.items():
        if server_name not in server_cells_in_inventory:
            # If the server is missing, suggest it might be a new server and infer the group
            suggested_group = determine_group_from_pattern(server_name)
            missing_servers.append((server_name, f"New server, should be under group: {suggested_group}"))
        else:
            inventory_cells = set(server_cells_in_inventory.get(server_name, []))
            # Check if there are mismatches between expected and actual cells
            if expected_cells != inventory_cells:
                if server_name not in cell_mismatches:
                    cell_mismatches[server_name] = {
                        'group': server_groups_in_inventory.get(server_name, 'Unknown Group'),
                        'expected_cells': expected_cells,
                        'actual_cells': inventory_cells,
                        'missing_cells': expected_cells - inventory_cells,
                        'extra_cells': inventory_cells - expected_cells
                    }

    # Check for extra servers in the inventory that are not in efsservers.txt
    for server_name in server_cells_in_inventory:
        if server_name not in expected_cells_by_server:
            extra_servers_in_inventory.append((server_name, server_groups_in_inventory.get(server_name, 'Unknown Group')))

    # Check control group validation: ensure both controlgroup_a and controlgroup_b have equal numbers of dev and prod servers
    total_dev_a = len(controlgroup_a_servers['dev'])
    total_prod_a = len(controlgroup_a_servers['prod'])
    total_dev_b = len(controlgroup_b_servers['dev'])
    total_prod_b = len(controlgroup_b_servers['prod'])

    if total_dev_a + total_dev_b != total_prod_a + total_prod_b:
        controlgroup_mismatches.append(f"Total dev servers do not match total prod servers. Found: {total_dev_a + total_dev_b} dev, {total_prod_a + total_prod_b} prod.")

    # Ensure controlgroup_a and controlgroup_b have an equal number of dev and prod servers
    if total_dev_a != total_prod_a or total_dev_b != total_prod_b:
        controlgroup_mismatches.append(f"Imbalance detected. Controlgroup A has {total_dev_a} dev and {total_prod_a} prod. Controlgroup B has {total_dev_b} dev and {total_prod_b} prod.")

    # Write results to the output file
    with open(output_file, 'w') as output:
        if missing_servers:
            output.write("Missing servers in inventory:\n")
            output.write("========================================================\n")
            for server, suggestion in missing_servers:
                output.write(f"{server} ({suggestion})\n")
        else:
            output.write("All EFS servers are present in the inventory.\n")
        
        if extra_servers_in_inventory:            
            output.write("=========================================================\n")
            for server, group in extra_servers_in_inventory:
                output.write(f"{server} (Group: {group})\n")

        if cell_mismatches:            
            output.write("========================================================\n")
            for server, details in cell_mismatches.items():
                group = details['group']
                missing_cells = details['missing_cells']
                extra_cells = details['extra_cells']
                expected_cells = details['expected_cells']
                actual_cells = details['actual_cells']
                output.write(f"\nServer: {server} (Group: {group})\n")
                output.write(f"  Expected Cells: {', '.join(sorted(expected_cells))}\n")
                output.write(f"  Actual Cells: {', '.join(sorted(actual_cells))}\n")
                
                if missing_cells:
                    output.write(f"  Missing Cells: {', '.join(sorted(missing_cells))}\n")
                if extra_cells:
                    output.write(f"  Extra Cells: {', '.join(sorted(extra_cells))}\n")
        else:
            output.write("Cell Names validation:\n")             
            output.write("========================================================\n")
            output.write("All cell names match.\n")
        
        if mismatches_servergroup:
            output.write("Server Groups validation:\n")       
            output.write("========================================================\n")
            output.write("\n".join(mismatches_servergroup))
        else:            
            output.write("========================================================\n")
            output.write("All servers are in the correct groups.\n")

        if mismatches:                     
            output.write("========================================================\n")            
            output.write("\n".join(mismatches))
        else:            
            output.write("========================================================\n")
            output.write("Controlgroup A and B are correctly balanced for high availability.\n")

def parse_validation_output(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    
    sections = re.split(r'={20,}', content)
    
    validation_titles = [
        "Missing servers in inventory (yaml):",
        "Extra servers in inventory (not found in efsservers.txt):",
        "Cell Names validation:",
        "Servers group validation:",
        "Control Group Validation:"
    ]
    
    validation_data = []
    
    for i, title in enumerate(validation_titles):
        if i < len(sections) - 1:
            validation_data.append((title.strip(), sections[i + 1].strip()))
    
    return validation_data

def format_cells(cells):
    return "\n      ".join(sorted(cells))

def generate_html_report(file_path, output_html="validation_report.html"):
    validation_data = parse_validation_output(file_path)
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Validation Report</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 20px; }
            h2 { text-align: center; color: #333; }
            table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1); }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; vertical-align: top; }
            th { background-color: #007bff; color: white; font-size: 16px; text-align: center; }
            td { font-size: 14px; }
            pre { white-space: pre-wrap; font-family: monospace; font-size: 13px; margin: 0; padding: 5px; background-color: #f4f4f4; border-radius: 5px; }
            tr:nth-child(even) { background-color: #f2f2f2; }
            .details-column { white-space: pre-wrap; font-family: monospace; padding-left: 10px; }
        </style>
    </head>
    <body>
        <h2>Ansible Inventory Validation Report</h2>
        <table>
            <tr>
                <th style="width: 30%;">Validations</th>
                <th style="width: 70%;">Details</th>
            </tr>
    """
    
    for validation, details in validation_data:
        formatted_details = "\n                  ".join(details.split(", "))  # Proper indentation for multiline cells
        html_content += f"<tr><td>{validation}</td><td class='details-column'><pre>{formatted_details}</pre></td></tr>"
    
    html_content += """
        </table>
    </body>
    </html>
    """
    
    with open(output_html, 'w') as file:
        file.write(html_content)
    
validate_inventory_with_efs(inventory_file, efs_file, output_file)
generate_html_report("validation_output.txt")

