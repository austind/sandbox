from socket import gethostbyaddr

import config
from rich import print

from icmplib import Hop, traceroute

trace = traceroute(config.TRACE_DEST)
hosts = []
for hop in trace:
    hop: Hop = hop
    # gethostbyaddr returns a 3-tuple (hostname, aliaslist, ipaddrlist)
    # https://docs.python.org/3/library/socket.html#socket.gethostbyaddr
    interface = gethostbyaddr(hop.address)[0]
    host = interface.split("--")[0]
    hosts.append((host, interface, hop.address))
print(hosts)
