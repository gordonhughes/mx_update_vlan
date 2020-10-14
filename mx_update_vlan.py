#!/usr/bin/python3.6

READ_ME = '''
=== PREREQUISITES ===
Run in Python 3.6+

Install Meraki v1 Python library:
pip[3] install --upgrade meraki

Have input CSV file with network name, second octet, and third octet specified.
Bind those networks to template that has VLANs configured.

=== DESCRIPTION ===
This script iterates through a dashboard org's MX networks, optionally filtered
on a given tag, and configures the VLANs' IP addressing according to the
template and input octets.

=== USAGE ===
python[3] configure_vlans.py -f <input_file> -k <api_key> -o <org_id>
    [-t <tag>] [-m <mode>]
Mode defaults to "simulate" unless "commit" is specified.

'''


import csv
from datetime import datetime
import getopt
import sys
import meraki


# Prints READ_ME help message for user to read
def print_help():
    lines = READ_ME.split('\n')
    for line in lines:
        print('# {0}'.format(line))


# Helper function
def update_vlan(dashboard, net_name, net_id, vlan_id, subnet, mx_ip, relay, csv_writer):
    global arg_mode
    #print("Trying:", dashboard, net_name, net_id, vlan_id, subnet, mx_ip, relay)
    #print("Global arg_mode:", arg_mode)
    
    try:
        if relay == '' or relay is None:  # no DHCP relay for VLAN
            # print("no relay")
            if arg_mode == 'commit':
                result = dashboard.appliance.updateNetworkApplianceVlan(
                    networkId=net_id,
                    vlanId=vlan_id,
                    subnet=subnet,
                    applianceIp=mx_ip,
                )
                vlan_name = result['name']
            else:
                print("Simulated networkId=", net_id, "vlan_id=", vlan_id,\
                      "subnet=", subnet, "applianceIp=",mx_ip)
            vlan_name = 'Simulated'
        else:
            # print("relay =", relay)
            if arg_mode == 'commit':
                result = dashboard.appliance.updateNetworkApplianceVlan(
                    networkId=net_id,
                    vlanId=vlan_id,
                    subnet=subnet,
                    applianceIp=mx_ip,
                    dhcpHandling='Relay DHCP to another server',
                    dhcpRelayServerIps=[relay],
                )
                vlan_name = result['name']
            else:
                print("Simulated networkId=", net_id, "vlan_id=", vlan_id,\
                      "subnet=", subnet, "applianceIp=", mx_ip, "dhcpHandling='Relay DHCP to another server",\
                      "dhcpRelayServerIps=", relay)
                vlan_name = 'Simulated'

        result = 'SUCCESS!'
    except meraki.APIError as e:
        vlan_name = 'ERROR'
        result = e

    # Output to CSV
    csv_writer.writerow(
        {
            'Network': net_name,
            'VLAN Name': vlan_name,
            'VLAN ID': vlan_id,
            'Subnet': subnet,
            'MX IP': mx_ip,
            'Result': result,
        }
    )


def main(inputs, csv_writer):
    # Process inputs
    arg_file = inputs['arg_file']
    api_key = inputs['api_key']
    org_id = inputs['org_id']
    arg_tag = inputs['arg_tag']
    arg_mode = inputs['arg_mode']

    # Read and process input file
    mappings = {}
    with open(arg_file, newline='') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',', quotechar='"')
        next(csv_reader, None)  # skip headers
        line_count = 0
        for data in csv_reader:
            print("data=",data)
            network_name = data[0]
            vlan_id = data[1]
            subnet = data[2]
            mx_ip = data[3]
            relay = data[4]
            network_data = {
                'network_name': network_name,
                'vlan_id': vlan_id,
                'subnet':subnet,
                'mx_ip': mx_ip,
                'relay': relay
            }
            # mappings[network_name] = [1].append(network_data)
            if network_name not in mappings:
                mappings[network_name] = []
                mappings[network_name].append(network_data.copy())
                print("added ", mappings[network_name])
            else:
                mappings[network_name].append(network_data.copy())
            line_count += 1
        print(f'Processed {line_count} rows from input CSV')
        #print("mappings:", mappings)

        # Get networks in org
        dashboard = meraki.DashboardAPI(api_key)
        networks = dashboard.organizations.getOrganizationNetworks(org_id, total_pages='all')

        # Filter on optional tag
        if arg_tag:
            target_networks = [network for network in networks if network['tags'] and arg_tag in network['tags']]
        else:
            target_networks = networks

        # Iterate through all networks
        print(f'Iterating through {len(target_networks)} networks:')
        for network in target_networks:
            name = network['name']

            # Network not in input file
            if name not in mappings:
                print(f'Did not find network {name} within input CSV file, so skipping!')
                continue

        # Configure VLANs for network
            print(f'Configuring VLANs for network {name}...')
            net_id = network['id']
            for vlan in mappings[name]:
                print("vlan =", vlan)
                update_vlan(dashboard, name, net_id, vlan['vlan_id'], vlan['subnet'], vlan['mx_ip'], vlan['relay'], csv_writer)

    print('Script complete!')


if __name__ == '__main__':
    args = sys.argv[1:]
#   if len(args) == 0:
#        print("debug adding args.")
#        args = ['-f', 'siteinfo2.csv', '-k', 'api_key', '-o', 'org']
#        print("len=",len(args))

    if len(args) == 0:
        print_help()
        sys.exit(2)

    #print("continue 1. args=",args)
    # Set default values for command line arguments
    arg_file = api_key = org_id = arg_tag = arg_mode = None

    # Get command line arguments
    try:
        opts, args = getopt.getopt(args, 'hf:k:o:t:m:')
    except getopt.GetoptError:
        print_help()
        sys.exit(2)

    #print("continue 2.")

    for opt, arg in opts:
        if opt == '-h':
            print_help()
            sys.exit()
        elif opt == '-f':
            arg_file = arg
        elif opt == '-k':
            api_key = arg
        elif opt == '-o':
            org_id = arg
        elif opt == '-t':
            arg_tag = arg
        elif opt == '-m':
            arg_mode = arg

    #print("continue 3.")
    #print(arg_file, api_key, org_id)

    # Check if all required parameters have been input
    if arg_file == None or api_key == None or org_id == None:
        print_help()
        sys.exit(2)

    #print("continue 4.")

    # Assign default mode to "simulate" unless "commit" specified
    if arg_mode != 'commit':
        arg_mode = 'simulate'
    
    inputs = {
        'arg_file': arg_file,
        'api_key': api_key,
        'org_id': org_id,
        'arg_tag': arg_tag,
        'arg_mode': arg_mode,
    }
    
    # Set the CSV output file
    script_file = sys.argv[0].split('.')[0]
    time_now = f'{datetime.now():%Y%m%d_%H%M%S}'
    file_name = f'{script_file}_results_{time_now}.csv'
    output_file = open(file_name, mode='w', newline='\n')

    # Write the header row
    field_names = ['Network', 'VLAN Name', 'VLAN ID', 'Subnet', 'MX IP', 'Result']
    csv_writer = csv.DictWriter(output_file, field_names, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
    csv_writer.writeheader()
    
    # Call main function
    main(inputs, csv_writer)

    output_file.close()
