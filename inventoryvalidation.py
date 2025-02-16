import yaml
import csv
import re

# File paths
efsservers_file = "efsservers.txt"
inventory_file = "inventory-lab.yaml"
report_file = "efs_comparison_report.txt"

def parse_efsservers(file_path):
    """Parse efsservers.txt and return a dictionary of servers, their cells, and host types."""
    efs_servers = {}

    with open(file_path, "r") as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            if len(row) < 4:
                continue  # Skip incomplete lines
            server_name, cell_name, host_type, fqdn = row
            if server_name not in efs_servers:
                efs_servers[server_name] = {"cells": set(), "fqdn": fqdn, "host_type": host_type.strip()}
            efs_servers[server_name]["cells"].add(cell_name.strip())  # Remove extra spaces

    return efs_servers

def parse_inventory(file_path):
    """Parse inventory-lab.yaml and return a dictionary of servers, their cells, relevant host groups, and control groups."""
    try:
        with open(file_path, "r") as file:
            inventory = yaml.safe_load(file)
            if not inventory or "all" not in inventory:
                raise ValueError("Invalid YAML structure: Missing 'all' key.")
    except Exception as e:
        print(f"Error parsing inventory file: {e}")
        return {}

    inventory_servers = {}
    server_to_group = {}
    valid_groups = {}
    server_type_dev = set()
    server_type_prod = set()
    control_groups = {}

    def extract_hosts(group, group_name=""):
        """Recursively extract hosts from relevant groups in YAML"""
        if not isinstance(group, dict):
            return

        # Only consider groups matching l_*_<region_code>
        if re.match(r"l_[a-zA-Z0-9_-]+_[a-zA-Z0-9]+", group_name):
            valid_groups[group_name] = True  # Track valid groups

            if "hosts" in group and isinstance(group["hosts"], dict):
                for host, attributes in group["hosts"].items():
                    if host not in inventory_servers:
                        inventory_servers[host] = {"cells": set()}
                    if isinstance(attributes, dict) and "cells" in attributes:
                        inventory_servers[host]["cells"].update(map(str.strip, attributes["cells"]))
                    server_to_group[host] = group_name  # Map server to valid host group

        # Extract servers from servertype_dev and servertype_prod groups
        if group_name == "servertype_dev" and "hosts" in group:
            server_type_dev.update(group["hosts"].keys())
        if group_name == "servertype_prod" and "hosts" in group:
            server_type_prod.update(group["hosts"].keys())

        # Extract control groups
        if group_name.startswith("controlgroup_") and "hosts" in group:
            control_groups[group_name] = group["hosts"].keys()

        if "children" in group and isinstance(group["children"], dict):
            for child_name, child_group in group["children"].items():
                extract_hosts(child_group, child_name)

    extract_hosts(inventory.get("all", {}))
    return inventory_servers, server_to_group, valid_groups, server_type_dev, server_type_prod, control_groups

def construct_expected_group(server_name, valid_groups):
    """Find the actual expected host group for the given server name."""
    try:
        base_name = server_name.split("server")[0]  # Extract part before "server"
        region_code = base_name[1:]  # Remove the first letter
        expected_pattern = re.compile(f"l_[a-zA-Z0-9_-]+_{region_code}")

        # Find the actual matching group name from valid_groups
        for group in valid_groups:
            if expected_pattern.match(group):
                return group  # Return the actual matching group

        return "Unknown"  # If no match found
    except Exception:
        return "Unknown"

def validate_control_groups(control_groups, efs_servers):
    control_group_issues = {}
    
    # For each control group, calculate the dev and prod counts
    for group_name, servers in control_groups.items():
        dev_count = 0
        prod_count = 0
        for s in servers:
            host_type = efs_servers.get(s, {}).get("host_type")
            if host_type == "dev":
                dev_count += 1
            elif host_type == "prod":
                prod_count += 1
        if dev_count != prod_count:
            control_group_issues[group_name] = f"Dev/Prod count mismatch (Dev: {dev_count}, Prod: {prod_count})"
    
    # Identify servers in efs_servers that do not belong to any control group.
    # (In our YAML parsing, only control groups start with "controlgroup_".)
    all_control_servers = set(s for servers in control_groups.values() for s in servers)
    missing_servers = []
    for server, details in efs_servers.items():
        if server not in all_control_servers:
            missing_servers.append(f"{server} ({details['host_type']})")
    
    # Now create the final formatted output. For each control group with a mismatch,
    # append the missing server names (if any) to the same line.
    formatted_issues = []
    for group, issue in control_group_issues.items():
        line = f"- {group}: {issue}"
        if missing_servers:
            # Append all missing server entries separated by a space.
            line += " missed servers: " + " / ".join(missing_servers)
        formatted_issues.append(line)
    
    return formatted_issues



def generate_report(efs_servers, inventory_servers, server_to_group, valid_groups, server_type_dev, server_type_prod, control_groups):
    """Compare efsservers.txt with inventory-lab.yaml and generate a report"""
    with open(report_file, "w") as report:
        report.write("EFS Inventory vs Ansible Inventory Comparison Report\n")
        report.write("=" * 60 + "\n\n")

        missing_in_inventory = set(efs_servers.keys()) - set(inventory_servers.keys())
        missing_in_efs_db = set(inventory_servers.keys()) - set(efs_servers.keys())

        if missing_in_inventory:
            report.write("Servers in efsservers.txt but missing in inventory-lab.yaml:\n")
            for server in sorted(missing_in_inventory):
                report.write(f"- {server} \n  Cells: {', '.join(sorted(efs_servers[server]['cells']))}\n")
            report.write("\n")

        if missing_in_efs_db:
            report.write("Servers in inventory-lab.yaml but missing in efsservers.txt:\n")
            for server in sorted(missing_in_efs_db):
                report.write(f"- {server} (Cells: {', '.join(sorted(efs_servers[server]['cells']))})\n")
            report.write("\n")

        mismatched_cells = {}
        incorrect_group_servers = []
        mismatched_server_types = []

        for server in efs_servers.keys() & inventory_servers.keys():
            efs_cells = efs_servers[server]["cells"]
            inv_cells = inventory_servers[server]["cells"]
            if efs_cells != inv_cells:
                mismatched_cells[server] = (efs_cells, inv_cells)

            # Validate server placement in the correct host group
            expected_group = construct_expected_group(server, valid_groups)
            found_group = server_to_group.get(server, "Unknown")

            # Only check against valid groups
            if expected_group != "Unknown" and found_group != expected_group:
                incorrect_group_servers.append((server, found_group, expected_group))

            # Validate server type (prod/dev)
            host_type = efs_servers[server]["host_type"]
            if host_type == "prod":
                if server not in server_type_prod:
                    if server in server_type_dev:
                        mismatched_server_types.append((server, "servertype_prod", "servertype_dev (incorrectly placed in servertype_dev)"))
                    else:
                        mismatched_server_types.append((server, None, "servertype_prod"))
            elif host_type == "dev":
                if server not in server_type_dev:
                    if server in server_type_prod:
                        mismatched_server_types.append((server, "servertype_prod", "servertype_dev"))
                    else:
                        mismatched_server_types.append((server, None, "servertype_dev"))

        # Validate control groups
        control_group_issues = validate_control_groups(control_groups, efs_servers)

        if mismatched_cells:
            report.write("Servers with mismatched cell assignments:\n")
            for server, (efs_cells, inv_cells) in mismatched_cells.items():
                report.write(f"- {server}\n")
                report.write(f"  - Expected (EFS DB): {', '.join(sorted(efs_cells))}\n")
                report.write(f"  - Found (Inventory): {', '.join(sorted(inv_cells)) if inv_cells else 'None'}\n\n")

        if incorrect_group_servers:
            report.write("Servers placed under incorrect host groups:\n")
            for server, found_group, expected_group in incorrect_group_servers:
                report.write(f"- {server}\n")
                report.write(f"  - Found in: {found_group}\n")
                report.write(f"  - Expected in: {expected_group}\n\n")

        if mismatched_server_types:
            report.write("Servers placed under incorrect servertype groups:\n")
            for server, found_group, expected_group in mismatched_server_types:
                report.write(f"- {server}\n")
                if found_group:
                    report.write(f"  - Found in: {found_group}\n")
                report.write(f"  - Expected in: {expected_group} (Host type: {efs_servers[server]['host_type']})\n\n")

        if control_group_issues:
            report.write("Control Group Validation Issues:\n")
            for issue in control_group_issues:
                report.write(issue + "\n")
            report.write("\n")

        if not (missing_in_inventory or missing_in_efs_db or mismatched_cells or incorrect_group_servers or mismatched_server_types or control_group_issues):
            report.write("All servers, cell mappings, and control groups match!\n")

    print(f"Comparison report generated: {report_file}")

if __name__ == "__main__":
    efs_servers = parse_efsservers(efsservers_file)
    inventory_servers, server_to_group, valid_groups, server_type_dev, server_type_prod, control_groups = parse_inventory(inventory_file)
    generate_report(efs_servers, inventory_servers, server_to_group, valid_groups, server_type_dev, server_type_prod, control_groups)
