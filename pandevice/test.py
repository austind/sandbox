import config
import ipdb
from panos.panorama import Panorama

pano = Panorama(
    hostname=config.HOST, api_username=config.USERNAME, api_password=config.PASSWORD
)
import re
import xml.etree.ElementTree as ET

import httpx
from httpx import URL

root = ET.Element("request-batch")
op = ET.SubElement(root, "op-command")
device = ET.SubElement(op, "device")
ET.SubElement(device, "entry", {"name": "016401016351"})
test = ET.SubElement(op, "test")
policy_match = ET.SubElement(test, "security-policy-match")
ET.SubElement(policy_match, "source").text = "10.1.1.1"
ET.SubElement(policy_match, "destination").text = "8.8.8.8"
ET.SubElement(policy_match, "destination-port").text = "80"
ET.SubElement(policy_match, "protocol").text = "6"
ET.tostring(root)
ipdb.set_trace()

# cmd = '<request-batch><op-command><device><entry name="016401016351"><vsys><list><<member>vsys1</member></list></vsys></entry></device><test><security-policy-match><source>10.1.1.1</source><destination>1.1.1.1</destination><destination-port>1</destination-port><protocol>1</protocol></security-policy-match></test></op-command></request-batch>'
# response = httpx.get(
#     f"https://{config.HOST}/api/?type=op&cmd={cmd}&key={config.API_KEY}", verify=False
# )
# status = httpx.get(f'https://{config.HOST}/api/?key={config.API_KEY}&type=log&action=get&job-id=')
# response = httpx.get(f'https://{config.HOST}/api/?type=keygen&user={config.USERNAME}&password={config.PASSWORD}', verify=False)
