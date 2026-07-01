# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""mDNS hostname advertising for the on-device config/web server.

Advertises ``<hostname>.local`` plus a service record so the device is reachable
by name on the LAN without knowing its IP. CircuitPython only — a no-op on desktop
(and harmless if the ``mdns`` module is unavailable), so callers never need a
platform check.

IMPORTANT: the caller MUST retain the returned ``mdns.Server`` for as long as it
wants ``.local`` to resolve. If it is garbage-collected the responder stops and
name resolution fails (intermittently — after the first cached query expires)::

    from scrollkit.network import mdns

    # keep a reference alive for the lifetime of the app
    self._mdns = mdns.advertise(self.settings.get("hostname", "scrollkit"))
"""
from __future__ import annotations


__all__ = ['advertise']

def advertise(hostname, *, port=80, service_type="_http", protocol="_tcp"):
    """Advertise ``<hostname>.local`` over mDNS and register a service.

    Returns the live ``mdns.Server`` on success (the caller MUST keep a reference
    to it — see the module docstring), or ``None`` on desktop / when the ``mdns``
    module or radio is unavailable. Never raises — mDNS must never block boot.
    """
    try:
        import wifi
        import mdns
    except ImportError:
        return None  # desktop / no CircuitPython mdns
    try:
        server = mdns.Server(wifi.radio)
        server.hostname = hostname
        server.advertise_service(service_type=service_type, protocol=protocol,
                                 port=port)
        print("mDNS advertising %s.local" % hostname)
        return server
    except Exception as e:  # never block boot on mDNS
        print("mDNS setup failed:", e)
        return None
