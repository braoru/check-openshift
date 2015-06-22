# check-openshift
Shinken/Nagios Openshift check

#Install check
```Bash

git clone..
pyvenv check-openshift
cd check-openshift
source bin/activate
pip install --upgrade pip
pip install -r requirements.txt

```


##check_nodes_openshift.py
```Bash
python check_nodes_openshift.py --broker-hostname mybroker.com --broker-ssh-user root --broker-ssh-key 'xxxx.rsa' --broker-passphrase 'hello-world-lalala' --mongo-hostname 'mdb1:27017 mdb2:27017 mdb3:27017' --mongo-user admin --mongo-password 'XXXX' --mongo-replicaset 'ZZZZ' --mongo-openshift-database-name 'openshift_XXX' --openshift-district-name 'my_district' -w 3 -c 4
```

