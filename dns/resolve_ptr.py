from config import traceroute_results
from rich import print


import re
import socket
import ipaddress

def resolve_ptr(ip_address: ipaddress.IPv4Address | str) -> str:
    """Resolve an IP address to a PTR record, if possible.
    
    Args:
        ip_address: IPv4 address to reverse-resolve to hostname.

    Returns:
        Hostname if resolved, or original IP address if not resolved.

    Raises:
        N/A
    """
    try:
        return socket.gethostbyaddr(str(ip_address))[0]
    except Exception:
        return ip_address

def resolve_traceroute_ptrs(traceroute_results: dict) -> dict:
    """Resolves PTR (reverse DNS) records for traceroute results.
    
    Args:
        traceroute_results: Dict of traceroute results.
        
    Returns:
        Same dict, but with host_name keys resolved to hostnames,
        if possible.
        
    """
    IP_ADDRESS_PATTERN = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
    
    # As each hop has multiple probes, the same IP address will be
    # resolved more than once. Caching these values may save a few ms.
    cache = {}

    # If the results dict has an error key, there's nothing to do
    if traceroute_results.get('error'):
        return traceroute_results
    
    for probes in traceroute_results['success'].values():
        for result in probes['probes'].values():
            if re.match(IP_ADDRESS_PATTERN, result['host_name']):
                hostname = cache.get(result['host_name']) or resolve_ptr(ip_address=result['host_name'])
                cache.update({result['host_name']: hostname})
                result['host_name'] = hostname
        
    return traceroute_results

if __name__ == '__main__':
    print(resolve_traceroute_ptrs(traceroute_results=traceroute_results))