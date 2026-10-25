#!/usr/bin/env python3
"""Mininet topology: 1 switch, 1 server, 2 normal clients, 1 attacker.
Run:  sudo python3 topology.py   (start the Ryu controller first)
"""
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel


def run():
    net = Mininet(controller=None, switch=OVSKernelSwitch, autoSetMacs=True)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
    s1 = net.addSwitch('s1', protocols='OpenFlow13')

    server = net.addHost('h1', ip='10.0.0.1/24')    # TCP server
    client1 = net.addHost('h2', ip='10.0.0.2/24')   # normal user
    client2 = net.addHost('h3', ip='10.0.0.3/24')   # normal user
    attacker = net.addHost('h4', ip='10.0.0.4/24')  # misbehaving host

    for h in (server, client1, client2, attacker):
        net.addLink(h, s1)

    net.start()
    print("\nTopology ready. Example commands in the CLI:")
    print("  h1 python3 server.py &")
    print("  h2 python3 client.py 10.0.0.1 &")
    print("  h4 python3 attacker.py 10.0.0.1\n")
    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
