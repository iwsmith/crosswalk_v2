Ansible Configuration Playbooks
===============================

Ansible provides SSH-based configuration management for remote hosts.

```
$ ansible-playbook site.yml -i inventory.ini
```


## Bootstrapping

After bringing up a new host, perform the following steps to prepare the node
for ansible management:

```shell
sudo echo 'IPQoS cs0 cs0' >> /etc/ssh/sshd_config
sudo apt-get update
sudo apt-get upgrade
```
