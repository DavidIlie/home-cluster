# Home Cluster

cute description will be written soon

# copy paste

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    enp6s18:
      dhcp4: no
      addresses:
        - 192.168.100.x/24
      gateway4: 192.168.100.1
      nameservers:
        addresses: [192.168.100.1]
    enp6s19:
      dhcp4: no
      addresses:
        - 192.168.56.x/24
      gateway4: 192.168.56.1
      nameservers:
        addresses: [1.1.1.1]
```
