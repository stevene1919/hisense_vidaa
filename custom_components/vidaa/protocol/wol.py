"""Wake-on-LAN magic packet utilities for Hisense VIDAA TV."""

from __future__ import annotations

import ipaddress
import logging
import socket

_LOGGER = logging.getLogger(__name__)


def send_wake_on_lan(
    mac: str | list[str] | tuple[str, ...],
    broadcast_ip: str | None = None,
    port: int = 9,
    ip: str | None = None,
    num_packets: int = 3,
) -> bool:
    """Sends standard Wake-on-LAN magic packet UDP broadcasts for one or multiple MACs."""
    if not mac:
        return False

    mac_list = [mac] if isinstance(mac, str) else list(mac)
    success = False
    ports = (port, 7) if port == 9 else (port,)

    for single_mac in mac_list:
        if not single_mac or not isinstance(single_mac, str):
            continue
        cleaned_mac = single_mac.replace(":", "").replace("-", "").replace(".", "").strip()
        if len(cleaned_mac) != 12:
            continue
        try:
            mac_bytes = bytes.fromhex(cleaned_mac)
            magic_packet = b"\xff" * 6 + mac_bytes * 16

            broadcast_targets = set()
            if broadcast_ip:
                broadcast_targets.add(broadcast_ip)
            else:
                broadcast_targets.add("255.255.255.255")
                if ip:
                    try:
                        ip_obj = ipaddress.ip_address(ip)
                        if isinstance(ip_obj, ipaddress.IPv4Address):
                            subnet_broadcast = f"{ip.rsplit('.', 1)[0]}.255"
                            broadcast_targets.add(subnet_broadcast)
                            broadcast_targets.add(ip)
                    except ValueError:
                        pass

            for p in ports:
                for target in broadcast_targets:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                        for _ in range(num_packets):
                            sock.sendto(magic_packet, (target, p))
                    _LOGGER.debug(
                        "Sent Wake-on-LAN packet burst (%dx) for MAC %s to %s:%d",
                        num_packets,
                        cleaned_mac,
                        target,
                        p,
                    )
            success = True
        except Exception as e:
            _LOGGER.error("Failed to send Wake-on-LAN packet for MAC %s: %s", single_mac, e)

    return success
