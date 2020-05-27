from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info


class butterflyTopo(Topo):
    def __init__(self, n=4, **kwargs):
        Topo.__init__(self, n, **kwargs)

        s1 = self.addSwitch( 's1' )
        s2 = self.addSwitch( 's2' )

        for h in range(n):
            host_1 = self.addHost('h%s' % (h))
            host_2 = self.addHost('h%s' % (h + 4))
            self.addLink(host_1, s1)
            self.addLink(host_2, s2)
        self.addLink(s1, s2)


def createNet():

    topo = butterflyTopo()
    net = Mininet(topo)

    info( "*** Starting network\n" )
    net.start()

    info("Dump host connections")
    dumpNodeConnections(net.hosts)
    info("Test connectivity")
    net.pingAll()
    info( "*** Stopping network\n" )
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    createNet()