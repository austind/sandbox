from panos.panorama import Panorama
import config
import ipdb

pano = Panorama(hostname=config.HOST, api_username=config.USERNAME, api_password=config.PASSWORD)
import httpx
from httpx import URL
import xml.etree.ElementTree as ET
import re

tree = ET.parse("sample.xml")
xml = ET.tostring(tree.getroot(), encoding="utf-8").decode()
cmd = re.sub(r"\s{2,}+", "", xml).replace("\n", "")

# cmd = '<request-batch><op-command><device><entry name="016401016351"><vsys><list><<member>vsys1</member></list></vsys></entry></device><test><security-policy-match><source>10.1.1.1</source><destination>1.1.1.1</destination><destination-port>1</destination-port><protocol>1</protocol></security-policy-match></test></op-command></request-batch>'
response = httpx.get(
    f"https://{config.HOST}/api/?type=op&cmd={cmd}&key={config.API_KEY}", verify=False
)
# status = httpx.get(f'https://{config.HOST}/api/?key={config.API_KEY}&type=log&action=get&job-id=')
# response = httpx.get(f'https://{config.HOST}/api/?type=keygen&user={config.USERNAME}&password={config.PASSWORD}', verify=False)
ipdb.set_trace()
