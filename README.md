# EFS Inventory Validation Script

## Overview
This Python script validates the EFS server inventory against a predefined YAML inventory file. It ensures that servers are assigned to the correct groups, checks cell name mismatches, and verifies the balance of control groups for high availability.

## Features
- Dynamically generates `efsservers.txt` from live data.
- Validates server placement in `servertype_dev` and `servertype_prod`.
- Ensures correct control group assignments (`controlgroup_a` and `controlgroup_b`).
- Checks for missing or extra servers in the inventory.
- Validates expected vs. actual cell names.
- Generates a validation report in `validation_output.txt`.

## Prerequisites
- Python 3.x
- Required dependencies: `pyyaml`
- Access to the `efs display efsservers` command.
- YAML inventory file (`inventory-prod.yaml`) in the same directory.

## Installation
```sh
pip install pyyaml
```

## Usage
Run the script with:
```sh
python prodinventory_validation.py
```
The validation results will be stored in `validation_report.html`.

## Output Details
The script produces the following validation checks:
- **Missing Servers**: Lists servers present in EFS but missing from the inventory.
- **Extra Servers**: Lists servers in the inventory but not found in EFS.
- **Cell Name Mismatches**: Identifies discrepancies between expected and actual cell assignments.
- **Server Group Validation**: Ensures `dev` and `prod` servers are correctly assigned.
- **Control Group Validation**: Ensures `controlgroup_a` and `controlgroup_b` are balanced.

## File Structure
```
project-folder/
│── prodinventory_validation.py     # The main validation script
│── efsservers.txt                  # Dynamically generated server list
│── inventory-prod.yaml             # YAML inventory file
│── validation_report.html           # Validation results
│── README.md                       
```

## Troubleshooting
- If `efsservers.txt` is empty, verify access to `efs display efsservers`.
- If the script fails due to missing dependencies, install `pyyaml`.
- Ensure the YAML inventory file exists and is correctly formatted.




