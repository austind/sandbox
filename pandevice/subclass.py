import xml.etree.ElementTree as ET

import config
import ipdb
from panos.panorama import Panorama as OriginalPanorama


class Panorama(OriginalPanorama):
    def test_security_policy_match(
        self,
        source: str,
        destination: str,
        protocol: int,
        application=None,
        category=None,
        port=None,
        user=None,
        from_zone=None,
        to_zone=None,
        show_all=False,
    ):
        root = ET.Element("request-batch")
        op = ET.SubElement(root, "op-command")
        device = ET.SubElement(op, "device")
        ET.SubElement(device, "entry", {"name": "016401016351"})
        test = ET.SubElement(op, "test")
        policy_match = ET.SubElement(test, "security-policy-match")
        ET.SubElement(policy_match, "source").text = source
        ET.SubElement(policy_match, "destination").text = destination
        ET.SubElement(policy_match, "destination-port").text = str(port)
        ET.SubElement(policy_match, "protocol").text = str(protocol)

        return self.op(cmd=ET.tostring(root), cmd_xml=False)


if __name__ == "__main__":
    pano = Panorama(
        hostname=config.HOST, api_username=config.USERNAME, api_password=config.PASSWORD
    )
    result = pano.test_security_policy_match(
        source="10.1.1.1", destination="8.8.8.8", protocol=6, port=80
    )
    ipdb.set_trace()
