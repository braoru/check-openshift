#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2013:
#     Sébastien Pasche, sebastien.pasche@leshop.ch
#     Benoit Chalot, benoit.chalut@leshop.ch
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
import os

try:
    from pymongo import MongoClient
except ImportError:
    print("ERROR : this plugin needs the python-pymongo module. Please install it")
    sys.exit(2)

try:
    import paramiko
except ImportError:
    print("ERROR : this plugin needs the python-paramiko module. Please install it")
    sys.exit(2)


class MongoDBHelper(object):

    @classmethod
    def get_mongodb_connection_to_db(
            cls,
            mongodb_servers=[],
            replicaset = None
    ):
        """

        :param mongodb_servers:
        :param replicaset:
        :return:
        """
        if mongodb_servers is None:
            raise Exception("You must specify at least one mongodb server host")
        if isinstance(mongodb_servers, str):
            mongodb_servers = [mongodb_servers]
        if len(mongodb_servers) == 0:
            raise Exception("You must specify at least one mongodb server host")
        try:
            mongodb_client = MongoClient(
                mongodb_servers,
                replicaset=replicaset
            )

            return mongodb_client
        except Exception as e:
            raise Exception("Could not connect to mongodb database")

    @classmethod
    def get_mongodb_auth_db(
            cls,
            mongodb_client=None,
            database_name=None,
            username=None,
            password=None,
            source='admin'
    ):
        """

        :param mongodb_client:
        :param database_name:
        :param username:
        :param password:
        :param source:
        :return:
        """

        if mongodb_client is None:
            raise Exception("You must have a database connection before authenticate to a DB")
        if database_name is None:
            raise Exception("You must specify at leart one openshift database")
        if username is None:
            raise Exception("You must specify at least one mongodb username")
        if password is None:
            raise Exception("You must specify at least one mongodb password")

        try:
            mongodb_db_connection = mongodb_client[database_name]
            mongodb_db_connection.authenticate(
                username,
                password,
                source=source
            )

            return mongodb_db_connection
        except Exception as e:
            raise Exception("Could not connect and authenticate to mongodb database")

    @classmethod
    def close_mongodb_connection(
            cls,
            mongodb_client
    ):
        try:
            mongodb_client.close()
        except Exception as e:
            raise Exception(e)

class OutputFormatHelpers(object):

    @classmethod
    def perf_data_string(
            cls,
            label,
            value,
            warn='',
            crit='',
            UOM='',
            min='',
            max=''

    ):
        """
        Generate perf data string from perf data input
        http://docs.icinga.org/latest/en/perfdata.html#formatperfdata
        :param label: Name of the measured data
        :type label: str
        :param value: Value of the current measured data
        :param warn: Warning level
        :param crit: Critical level
        :param UOM: Unit of the value
        :param min: Minimal value
        :param max: maximal value
        :return: formated perf_data string
        """
        if UOM:
            perf_data_template = "'{label}'={value}[{UOM}];{warn};{crit};{min};{max};"
        else:
            perf_data_template = "'{label}'={value};{warn};{crit};{min};{max};"

        return perf_data_template.format(
            label=label,
            value=value,
            warn=warn,
            crit=crit,
            UOM=UOM,
            min=min,
            max=max
        )

    @classmethod
    def check_output_string(
            cls,
            state,
            message,
            perfdata
    ):
        """
        Generate check output string with perf data
        :param state: State of the check in  ['Critical', 'Warning', 'OK', 'Unknown']
        :type state: str
        :param message: Output message
        :type message: str
        :param perfdata: Array of perf data string
        :type perfdata: Array
        :return: check output formated string
        """
        if state not in  ['Critical', 'Warning', 'OK', 'Unknown']:
            raise Exception("bad check output state")

        if not message:
            message = '-'

        if perfdata is not None:
            if not hasattr(perfdata, '__iter__'):
                raise Exception("Submited perf data list is not iterable")

            perfdata_string = ''.join(' {s} '.format(s=data) for data in perfdata)
            output_template = "{s}: {m} |{d}"
        else:
            output_template = "{s}: {m} "
            perfdata_string = ''

        return output_template.format(
            s=state,
            m=message,
            d=perfdata_string
        )

class SSHHelper(object):

    @classmethod
    def get_client(
            cls,
            opts
    ):
        hostname = opts.hostname
        port = opts.port
        ssh_key_file = opts.ssh_key_file
        user = opts.user
        passphrase = opts.passphrase

        # Ok now connect, and try to get values for memory
        client = cls.connect(hostname, port, ssh_key_file, passphrase, user)
        return client

    @classmethod
    def connect(
            cls,
            hostname,
            port,
            ssh_key_file,
            passphrase,
            user
    ):
        """

        :param cls:
        :param hostname:
        :param port:
        :param ssh_key_file:
        :param passphrase:
        :param user:
        :return:
        """
        # Maybe paramiko is missing, but now we relly need ssh...
        if paramiko is None:
            print("ERROR : this plugin needs the python-paramiko module. Please install it")
            sys.exit(2)

        if not os.path.exists(os.path.expanduser(ssh_key_file)):
            raise Exception("Error : missing ssh key file. please specify it with -i parameter")

        ssh_key_file = os.path.expanduser(ssh_key_file)
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh_config = paramiko.SSHConfig()
        user_config_file = os.path.expanduser("~/.ssh/config")
        if os.path.exists(user_config_file):
            with open(user_config_file) as f:
                ssh_config.parse(f)

        cfg = {
            'hostname': hostname,
            'port': port,
            'username': user,
            'key_filename': ssh_key_file,
            'password': passphrase
        }

        user_config = ssh_config.lookup(cfg['hostname'])
        for k in ('hostname', port, 'username', 'key_filename', 'password'):
            if k in user_config:
                cfg[k] = user_config[k]

        if 'proxycommand' in user_config:
            cfg['sock'] = paramiko.ProxyCommand(user_config['proxycommand'])

        try:
            client.connect(**cfg)
        except Exception as e:
            print("Error : connexion to {h} failed '{m}'".format(
                m=e,
                h=hostname
            ))
            sys.exit(2)
        return client

    def close(client):
        try:
            client.close()
        except Exception as e:
            raise Exception(e)

if __name__ == '__main__':
    pass
