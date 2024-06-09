import config

from netmiko import ConnectHandler

CMD = f"bash timeout 60 traceroute {config.DEST} -s {config.SOURCE} -m 30 -w 2"

with ConnectHandler(
    host=config.SOURCE,
    username=config.USERNAME,
    password=config.PASSWORD,
    device_type="arista_eos",
) as conn:
    results = conn.send_command(CMD)
