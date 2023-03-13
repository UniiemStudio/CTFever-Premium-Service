import asyncio
import socket
import time
from typing import List, Dict

from core import Plugin


def check_range(nums: list, min_val: int, max_val: int):
    for num in nums:
        if num < min_val or num > max_val:
            return True
    return False


class Portscan(Plugin):

    def __init__(self):
        super().__init__()
        self.cfg = None
        self.PORT_SERVICES = None
        self.HOST_BLACKLIST = None

    def load(self):
        self.cfg = self.ConfigUtil(self.data_dir(), 'config.json', {
            'port_services': {},
            'host_blacklist': []
        })
        self.PORT_SERVICES = self.cfg.get_cfg('port_services')
        self.HOST_BLACKLIST = self.cfg.get_cfg('host_blacklist')

    def unload(self):
        pass

    def activate(self):
        super().activate()

    def __getmethods__(self, exclude: List[str] = None):
        return super().__getmethods__(['scan_port', 'scan_ports', 'scanner'])

    def params_validater(self, params):
        if not params.get('host'):
            return 'host is required'
        if not params.get('ports'):
            return 'ports is required'
        return super().params_validater(params)

    async def scan_port(self, host: str, port: int, results: Dict[int, dict]) -> None:
        try:
            conn = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(conn, timeout=3)
            results[port] = {
                'address': host,
                'port': port,
                'state': 'open',
                'service': 'unknown'
            }
            service = self.PORT_SERVICES.get(str(port))
            if service:
                results[port]['service'] = service
            writer.close()
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            pass

    async def scan_ports(self, ip: str, ports: List[int]) -> Dict[int, str]:
        results = {}
        tasks = [asyncio.create_task(self.scan_port(ip, port, results))
                 for port in ports]
        await asyncio.gather(*tasks)
        return results

    async def scanner(self, host: str, ports: str) -> Dict[str, dict]:
        port_list = []
        for p in ports.split(","):
            if "-" in p:
                start_port, end_port = map(int, p.split("-"))
                if check_range(list(range(start_port, end_port + 1)), 1, 65535):
                    raise ValueError(f"invalid port range '{p}'")
                if start_port > end_port:
                    start_port, end_port = end_port, start_port
                port_list += list(range(start_port, end_port + 1))
            else:
                if not p.isdigit():
                    raise ValueError(f"invalid port '{p}'")
                if check_range([int(p)], 1, 65535):
                    raise ValueError(f"invalid port '{p}'")
                port_list.append(int(p))
        if len(port_list) > 1000:
            raise ValueError(f"too many ports, max 1000")
        t1 = time.time()
        try:
            addr_info = await asyncio.get_event_loop().getaddrinfo(host, None)
            ip_addr = addr_info[0][4][0]
            results = await self.scan_ports(ip_addr, port_list)
        except socket.gaierror as e:
            raise ValueError(f"can not resolve '{host}'") from e
        self.logger.info(f"scan {host}({ip_addr}) for {len(port_list)} port(s) in {round(time.time() - t1, 3)}s")
        return {
            "host": ip_addr,
            "total": len(port_list),
            "open": len(results),
            "ports": {k: results[k] for k in sorted(results)}
        }

    async def scan(self, params: dict) -> Dict[str, dict]:
        for host in self.HOST_BLACKLIST:
            if host in params.get('host'):
                raise ValueError(f"host '{host}' is not allowed")
        return await self.scanner(params.get('host'), params.get('ports'))
