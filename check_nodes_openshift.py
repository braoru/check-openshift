#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2013:
#     Sébastien Pasche, sebastien.pasche@leshop.ch
#     Benoit Chalut, benoit.chalut@leshop.ch
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
#

author = "Sebastien Pasche"
maintainer = "Sebastien Pasche"
version = "0.0.1"

import sys
import optparse
import os
import traceback
import json

from pprint import pprint

#TODO : Move to asyncio_mongo

try:
    import paramiko
except ImportError:
    print("ERROR : this plugin needs the python-paramiko module. Please install it")
    sys.exit(2)

#Ok try to load our directory to load the plugin utils.
my_dir = os.path.dirname(__file__)
sys.path.insert(0, my_dir)

try:
    from openshift_checks import MongoDBHelper, OutputFormatHelpers, SSHHelper
except ImportError:
    print("ERROR : this plugin needs the local openshift_checks lib. Please install it")
    sys.exit(2)

#DEFAULT LIMITS
#--------------
DEFAULT_WARNING = 2
DEFAULT_CRITICAL = 3


def is_node_mco_ping(
    client,
    node_identitiy,
    debug=False
):
    """

    :param client:
    :param node_identitiy:
    :return:
    """
    cmd = "oo-mco rpc rpcutil ping -j -I {i}".format(
        i=node_identitiy
    )

    if debug:
        print("Command to execute")
        print(cmd)

    stdin, stdout, stderr = client.exec_command(
        cmd,
        get_pty=True
    )
    lines = [line for line in stdout]
    json_raw = ''.join(lines)
    json_array = json.loads(json_raw)

    if debug:
        print("JSON mco ping output")
        pprint(json_array)

    if len(json_array) == 1:
        mco_ping_status = json.loads(json_raw)[0]
        if mco_ping_status:
            if mco_ping_status['statusmsg'] == 'OK':
                return True
    return False


def nodes_mco_ping_status(
        client,
        mongo_district_dict,
        debug=False
):
    """

    :param client:
    :param mongo_district_dict:
    :return:
    """
    servers_ping = {
        server['name']: is_node_mco_ping(
            client,
            server['name'],
            debug
        )
        for server in mongo_district_dict['servers']
    }

    servers_status = {
        server_name: {
            'unresponsive': not mco_ping,
            'active': mco_ping
        } for server_name, mco_ping in servers_ping.items()
    }

    return servers_status

def openshift_district(
        mongodb_db_connection,
        district_name,
        debug=False
):
    """

    :param mongodb_db_connection:
    :param district_name:
    :return:
    """
    collection = mongodb_db_connection['districts']

    if debug:
        print("The db connection")
        pprint(mongodb_db_connection)
        print("The collection")
        pprint(collection)

    district = collection.find_one(
        {
            'name': district_name
        },
        {
            'servers': 1
        }
    )

    if debug:
        print('The district')
        pprint(district)

    return district


def servers_status(
        mongo_district_dict
):
    """

    :param mongo_district_dict:
    :return:
    """
    servers_status = {
        server['name']: {
            'active': server['active'],
            'unresponsive': server['unresponsive']
        } for server in mongo_district_dict['servers']
    }
    return servers_status

def nb_unresponsive_servers(
        servers_status_dict
):
    """

    :param servers_status_dict:
    :return:
    """
    return sum (
        [
            status['unresponsive'] for server, status in servers_status_dict.items()
            ]
    )

def nb_active_servers(
        servers_status_dict
):
    """

    :param servers_status_dict:
    :return:
    """
    return sum (
        [
            status['active'] for server, status in servers_status_dict.items()
            ]
    )

# OPT parsing
# -----------
parser = optparse.OptionParser(
    "%prog [options]", version="%prog " + version)

#broker ssh param
parser.add_option('--broker-hostname', default='',
                  dest="broker_hostname", help='Broker to connect to')
parser.add_option('--broker-ssh-port',
                  dest="broker_ssh_port", type="int", default=22,
                  help='SSH port to connect to the broker. Default : 22')
parser.add_option('--broker-ssh-key', default=os.path.expanduser('~/.ssh/id_rsa'),
                  dest="broker_ssh_key_file", help='SSH key file to use. By default will take ~/.ssh/id_rsa.')
parser.add_option('--broker-ssh-user', default='shinken',
                  dest="broker_ssh_user", help='remote use to use. By default shinken.')
parser.add_option('--broker-passphrase', default='',
                  dest="broker_ssh_passphrase", help='SSH key passphrase. By default will use void')

#mongodb connection
parser.add_option('--mongo-hostname',
                  dest="mongo_hostnames",
                  help='space separated mongodb hostnames:port list to connect to. '
                       'Example :  "server1:27017 server2:27017" ')
parser.add_option('--mongo-user',
                  dest="mongo_user", default="shinken",
                  help='remote use to use. By default shinken.')
parser.add_option('--mongo-password',
                  dest="mongo_password",
                  help='Password. By default will use void')
parser.add_option('--mongo-source-longon',
                  dest="mongo_source", default='admin',
                  help='Source where to log on. Default: admin')
parser.add_option('--mongo-replicaset',
                  dest="mongo_replicaset",
                  help='openshift current mongodb replicaset')
parser.add_option('--mongo-openshift-database-name',
                  dest="mongo_openshift_database",
                  help='openshift current database')

#openshift relative
parser.add_option('--openshift-district-name',
                  dest="openshift_district",
                  help='openshift district to query')
parser.add_option('-w', '--warning',
                  dest="warning", type="int",default=None,
                  help='Warning value for number of unresponsive nodes. Default : 2')
parser.add_option('-c', '--critical',
                  dest="critical", type="int",default=None,
                  help='Critical value for number of unresponsive nodes. Default : 3')

#generic
parser.add_option('--debug',
                  dest="debug", default=False, action="store_true",
                  help='Enable debug')

if __name__ == '__main__':

    # Ok first job : parse args
    opts, args = parser.parse_args()
    if args:
        parser.error("Does not accept any argument.")

    #Broker ssh args
    #---------------

    # get broker server list
    if opts.broker_hostname is None:
        raise Exception("You must specify a broker server")

    # get broker ssh user
    if opts.broker_ssh_user is None:
        raise Exception("You must specify a broker ssh user")

    broker_ssh_host = opts.broker_hostname
    broker_ssh_port = opts.broker_ssh_port
    broker_ssh_user = opts.broker_ssh_user
    broker_ssh_key_path = opts.broker_ssh_key_file
    broker_ssh_passphrase = opts.broker_ssh_passphrase

    #MongpDB args
    #------------

    # get mongodb server list
    if opts.mongo_hostnames is None:
        raise Exception("You must specify a mongodb servers list")

    # get mongodb user
    if opts.mongo_user is None:
        raise Exception("You must specify a mongodb user")

    # get mongodb user password
    if opts.mongo_password is None:
        raise Exception("You must specify a mongodb user password")

    # get mongodb source logon
    if opts.mongo_source is None:
        raise Exception("You must specify a mongodb source longon")

    # get mongodb openshift database name
    if opts.mongo_openshift_database is None:
        raise Exception("You must specify a mongodb openshift database name")

    # get mongodb database replicaset
    if opts.mongo_replicaset is None:
        raise Exception("You must specify a mongodb database replicaset name")

    mongodb_hostnames_array = opts.mongo_hostnames.split(' ')
    mongodb_user = opts.mongo_user
    mongodb_password = opts.mongo_password
    mongodb_logon_source = opts.mongo_source
    mongodb_openshift_db = opts.mongo_openshift_database
    mongodb_replicaset = opts.mongo_replicaset

    #Openshift related args
    #----------------------

    #Get district name
    if opts.openshift_district is None:
        raise Exception("You must specify a openshift district name")

    openshift_district_name = opts.openshift_district



    # Try to get numeic warning/critical values
    s_warning = opts.warning or DEFAULT_WARNING
    s_critical = opts.critical or DEFAULT_CRITICAL

    debug = opts.debug

    try:
        # Ok now got an object that link to our destination
        client = SSHHelper.connect(
            hostname=broker_ssh_host,
            user=broker_ssh_user,
            ssh_key_file=broker_ssh_key_path,
            passphrase=broker_ssh_passphrase,
            port=broker_ssh_port
        )

        #Connecto to MongoDB
        #-------------------
        mongodb_client = MongoDBHelper.get_mongodb_connection_to_db(
            mongodb_servers=mongodb_hostnames_array,
            replicaset=mongodb_replicaset
        )

        mongodb_db = MongoDBHelper.get_mongodb_auth_db(
            mongodb_client=mongodb_client,
            database_name=mongodb_openshift_db,
            username=mongodb_user,
            password=mongodb_password,
            source=mongodb_logon_source
        )

        #get district
        #------------
        district = openshift_district(
            mongodb_db_connection=mongodb_db,
            district_name=openshift_district_name,
            debug=debug
        )
        if debug:
            pprint(district)

        #get server db status
        #--------------------
        servers_db_status = servers_status(district)
        if debug:
            print("mongodb servers status")
            pprint(servers_db_status)

        #get unresponsive/active count from the db
        db_nb_unresponsive_servers = nb_unresponsive_servers(servers_db_status)
        db_nb_active_servers = nb_active_servers(servers_db_status)

        #get mco ping responce
        #---------------------
        ssh_mco_servers_status = nodes_mco_ping_status(
            client,
            district,
            debug
        )
        if debug:
            print("mco servers status")
            pprint(ssh_mco_servers_status)

        #get unresponsive/active count from remote mco ping
        nb_mco_ping_active_servers = nb_active_servers(ssh_mco_servers_status)
        nb_mco_ping_unresponsive_servers = nb_unresponsive_servers(ssh_mco_servers_status)

        #format perf data
        db_active_servers_data_string = OutputFormatHelpers.perf_data_string(
            label="{d}_mongodb_active_nodes".format(d=openshift_district_name),
            value=db_nb_active_servers,
        )
        db_unresponsive_servers_data_string = OutputFormatHelpers.perf_data_string(
            label="{d}_mongodb_unresponsive_servers".format(d=openshift_district_name),
            value=db_nb_unresponsive_servers,
            warn=s_warning,
            crit=s_critical
        )
        mco_active_servers_data_string = OutputFormatHelpers.perf_data_string(
            label="{d}_mco_active_nodes".format(d=openshift_district_name),
            value=nb_mco_ping_active_servers,
        )
        mco_unresponsive_servers_data_string = OutputFormatHelpers.perf_data_string(
            label="{d}_mco_unresponsive_servers".format(d=openshift_district_name),
            value=nb_mco_ping_unresponsive_servers,
            warn=s_warning,
            crit=s_critical
        )

        #check
        nb_unresponsive_servers = max(db_nb_unresponsive_servers,nb_mco_ping_unresponsive_servers)
        nb_active_servers = max(db_nb_active_servers,nb_mco_ping_active_servers)

        status = "OK"
        state = "active"
        nb = nb_active_servers
        if nb_unresponsive_servers >= s_warning:
            status = "Warning"
            state = "unresponsive"
            nb = nb_unresponsive_servers
        if nb_unresponsive_servers >= s_critical:
            status = "Critical"
            state = "unresponsive"
            nb = nb_unresponsive_servers

        #Format and print check result
        message = "{nb} {state} openshift nodes".format(
            nb=nb,
            state=state
        )
        output = OutputFormatHelpers.check_output_string(
            status,
            message,
            [
                db_active_servers_data_string,
                db_unresponsive_servers_data_string,
                mco_active_servers_data_string,
                mco_unresponsive_servers_data_string
            ]
        )

        print(output)
        

    except Exception as e:
        if debug:
            print(e)
            the_type, value, tb = sys.exc_info()
            traceback.print_tb(tb)
        print("Error: {m}".format(m=e))
        sys.exit(2)

    finally:
        if mongodb_client is not None:
            MongoDBHelper.close_mongodb_connection(mongodb_client)
        if status == "Critical":
            sys.exit(2)
        if status == "Warning":
            sys.exit(1)
        sys.exit(0)