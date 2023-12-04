import config
from rich import print

from napalm import get_network_driver

driver = get_network_driver("ios")

with driver(config.SOURCE, config.USERNAME, config.PASSWORD) as device:
    results = device.traceroute(destination=config.DEST, source=config.SOURCE)

print(results)
