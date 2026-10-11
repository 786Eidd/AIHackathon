# app/discovery/scanner.py

"""
Finds video sources the box can reach without being told about them:

  * IP cameras / NVRs / DVRs on the local network (RTSP on 554 or 8554,
    named via ONVIF WS-Discovery when the device answers it)
  * phones running a camera app that serves MJPEG (DroidCam, IP Webcam)
  * capture devices attached to this machine (USB / built-in webcams)

Scanning only looks at the subnets this machine is directly attached to, and
only at a handful of camera ports. Working out *which* streams a device
offers needs its login, so that step lives in `resolve_streams`.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from app.discovery import rtsp_probe

logger = logging.getLogger("nexgen.discovery")

RTSP_PORTS = (554, 8554)
MJPEG_PORTS = (4747, 8080)

# Open on the device but not streamed from; only used to guess the vendor.
_VENDOR_HINT_PORTS = {8000: "Hikvision", 37777: "Dahua"}

_CONNECT_TIMEOUT = 0.5
_SCAN_WORKERS = 128
_MAX_WEBCAM_INDEX = 4


# -----------------------------
# Network helpers
# -----------------------------
def local_networks() -> List[ipaddress.IPv4Network]:
    """The /24 around each private IPv4 address this machine holds."""
    addresses = set()

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass

    # The route the OS would actually use to reach the LAN; covers hosts
    # whose hostname does not resolve to their LAN address.
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("192.168.255.255", 9))
        addresses.add(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass

    networks = []

    for address in sorted(addresses):
        ip = ipaddress.ip_address(address)

        if not ip.is_private or ip.is_loopback or ip.is_link_local:
            continue

        network = ipaddress.ip_network(f"{address}/24", strict=False)

        if network not in networks:
            networks.append(network)

    return networks[:4]


def _safe_addrinfo() -> list:
    try:
        return socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=_CONNECT_TIMEOUT):
            return True
    except OSError:
        return False


def _is_mjpeg(host: str, port: int) -> bool:
    """True when GET /video answers with a multipart JPEG stream."""
    try:
        with socket.create_connection((host, port), timeout=2.0) as sock:
            sock.settimeout(2.0)
            sock.sendall(
                f"GET /video HTTP/1.1\r\nHost: {host}:{port}\r\n"
                "Connection: close\r\n\r\n".encode()
            )

            data = b""

            while b"\r\n\r\n" not in data and len(data) < 8192:
                chunk = sock.recv(2048)

                if not chunk:
                    break

                data += chunk

    except OSError:
        return False

    head = data.split(b"\r\n\r\n", 1)[0].lower()

    return b" 200" in head.split(b"\r\n", 1)[0] and b"multipart/x-mixed-replace" in head


# -----------------------------
# ONVIF WS-Discovery (device names)
# -----------------------------
_WS_DISCOVERY_PROBE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" '
    'xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
    'xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
    'xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
    "<e:Header><w:MessageID>uuid:{message_id}</w:MessageID>"
    "<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>"
    "<w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>"
    "</e:Header><e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types>"
    "</d:Probe></e:Body></e:Envelope>"
)


def onvif_names(wait_seconds: float = 2.0) -> Dict[str, str]:
    """Maps IP -> advertised device name for ONVIF devices that answer."""
    names: Dict[str, str] = {}

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(0.5)

        message = _WS_DISCOVERY_PROBE.format(message_id=uuid.uuid4()).encode()
        sock.sendto(message, ("239.255.255.250", 3702))

    except OSError as e:
        logger.info(f"ONVIF discovery unavailable: {e}")
        return names

    deadline = time.monotonic() + wait_seconds

    try:
        while time.monotonic() < deadline:
            try:
                data, (address, _) = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break

            text = data.decode("utf-8", errors="replace")

            name = re.search(r"onvif://www\.onvif\.org/name/([^\s<]+)", text)
            hardware = re.search(r"onvif://www\.onvif\.org/hardware/([^\s<]+)", text)

            label = " ".join(
                part.group(1).replace("%20", " ")
                for part in (name, hardware)
                if part is not None
            )

            names[address] = label or "ONVIF camera"
    finally:
        sock.close()

    return names


# -----------------------------
# Local capture devices
# -----------------------------
def local_webcams(skip: Optional[set] = None) -> List[int]:
    """
    Indexes of attached capture devices. Indexes in `skip` are already
    streaming here; reopening one would fail or steal it from its pipeline.
    """
    import cv2

    backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
    found = []

    for index in range(_MAX_WEBCAM_INDEX):
        if skip and index in skip:
            found.append(index)
            continue

        capture = cv2.VideoCapture(index, backend)

        try:
            if capture.isOpened() and capture.read()[0]:
                found.append(index)
            elif index > 0:
                # Device indexes are contiguous; no point probing further.
                break
        finally:
            capture.release()

    return found


# -----------------------------
# Scan
# -----------------------------
def scan(webcams_in_use: Optional[set] = None) -> List[dict]:
    """
    Returns one entry per discovered source:

        {"kind": "rtsp" | "mjpeg" | "webcam", "host", "port", "label",
         "vendor", "needs_login", "url"}

    `url` is set when the source can be registered as-is (webcam, phone app);
    RTSP devices need `resolve_streams` with a login first.
    """
    started = time.monotonic()
    devices: List[dict] = []

    for index in local_webcams(webcams_in_use):
        devices.append(
            {
                "kind": "webcam",
                "host": "this device",
                "port": index,
                "label": "Built-in / USB camera" if index == 0 else f"USB camera {index}",
                "vendor": "Local",
                "needs_login": False,
                "url": f"webcam://{index}",
            }
        )

    networks = local_networks()
    own = {info[4][0] for info in _safe_addrinfo()}

    hosts = [
        str(host)
        for network in networks
        for host in network.hosts()
        if str(host) not in own
    ]

    ports = RTSP_PORTS + MJPEG_PORTS + tuple(_VENDOR_HINT_PORTS)
    targets = [(host, port) for host in hosts for port in ports]

    with ThreadPoolExecutor(max_workers=_SCAN_WORKERS) as pool:
        names_future = pool.submit(onvif_names)
        open_flags = list(pool.map(lambda target: _port_open(*target), targets))
        names = names_future.result()

    open_ports: Dict[str, set] = {}

    for (host, port), is_open in zip(targets, open_flags):
        if is_open:
            open_ports.setdefault(host, set()).add(port)

    for host in sorted(open_ports, key=lambda value: tuple(int(p) for p in value.split("."))):
        host_ports = open_ports[host]

        vendor = next(
            (name for port, name in _VENDOR_HINT_PORTS.items() if port in host_ports),
            "",
        )

        for port in RTSP_PORTS:
            if port not in host_ports:
                continue

            probe = rtsp_probe.describe(host, port, "/")

            if probe.status == rtsp_probe.UNREACHABLE:
                continue

            devices.append(
                {
                    "kind": "rtsp",
                    "host": host,
                    "port": port,
                    "label": names.get(host) or (f"{vendor} camera / recorder" if vendor else "IP camera / recorder"),
                    "vendor": vendor or _vendor_from_server(probe.server),
                    "needs_login": True,
                    "url": None,
                }
            )

        for port in MJPEG_PORTS:
            if port in host_ports and _is_mjpeg(host, port):
                devices.append(
                    {
                        "kind": "mjpeg",
                        "host": host,
                        "port": port,
                        "label": "Phone camera (DroidCam)" if port == 4747 else "Phone camera (IP Webcam)",
                        "vendor": "Mobile",
                        "needs_login": False,
                        "url": f"http://{host}:{port}/video",
                    }
                )

    logger.info(
        f"Discovery scanned {len(hosts)} host(s) on "
        f"{', '.join(str(n) for n in networks) or 'no network'} in "
        f"{time.monotonic() - started:.1f}s: {len(devices)} source(s) found."
    )

    return devices


def _vendor_from_server(server: str) -> str:
    lowered = (server or "").lower()

    for needle, vendor in (("hik", "Hikvision"), ("dahua", "Dahua"), ("app-webs", "Hikvision")):
        if needle in lowered:
            return vendor

    return ""


# -----------------------------
# Stream resolution (needs the device login)
# -----------------------------
# (vendor, path template, multi-channel). Sub streams are listed because the
# box analyses a downscaled frame anyway; main streams only cost CPU.
_STREAM_PATTERNS: List[Tuple[str, str, bool]] = [
    ("Hikvision", "/Streaming/Channels/{channel}02", True),
    ("Dahua", "/cam/realmonitor?channel={channel}&subtype=1", True),
    ("Camera", "/live", False),
    ("Camera", "/stream1", False),
    ("Camera", "/h264", False),
    ("Camera", "/11", False),
    ("Camera", "/", False),
]


def _stream_url(host: str, port: int, path: str, username: str, password: str) -> str:
    auth = f"{quote(username, safe='')}:{quote(password, safe='')}@" if username else ""

    return f"rtsp://{auth}{host}:{port}{path}"


def _delivers_video(url: str, timeout_seconds: float = 8.0) -> bool:
    """
    Opens the stream and waits for one real frame. Recorders answer DESCRIBE
    for every channel they have a socket for, including the empty ones, so
    this is what separates connected cameras from blank inputs.
    """
    import cv2

    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

    timeout_ms = int(timeout_seconds * 1000)

    capture = cv2.VideoCapture(
        url,
        cv2.CAP_FFMPEG,
        [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            timeout_ms,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            timeout_ms,
        ],
    )

    try:
        if not capture.isOpened():
            return False

        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            ok, frame = capture.read()

            if ok and frame is not None and frame.size:
                return True

        return False
    finally:
        capture.release()


def resolve_streams(
    host: str,
    port: int,
    username: str,
    password: str,
    max_channels: int = 16,
) -> dict:
    """
    Works out which streams a device serves for the given login.

    Returns {"status": "ok" | "auth_failed" | "no_streams" | "unreachable",
             "vendor": str, "streams": [{"channel", "url"}]}
    """
    reachable = False

    for vendor, template, multi_channel in _STREAM_PATTERNS:
        first = rtsp_probe.describe(
            host, port, template.format(channel=1), username, password
        )

        # A device that does not answer at all will not answer the next
        # pattern either; give up now instead of timing out on each one.
        if first.status == rtsp_probe.UNREACHABLE and not reachable:
            break

        if first.status == rtsp_probe.UNREACHABLE:
            continue

        reachable = True

        # Stop at the first rejected login. Trying the remaining patterns
        # with the same bad password would trip the camera's lock-out.
        if first.status == rtsp_probe.AUTH_REQUIRED:
            return {"status": "auth_failed", "vendor": "", "streams": []}

        if first.status != rtsp_probe.OK:
            continue

        channels = [1]

        if multi_channel:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(
                    pool.map(
                        lambda channel: rtsp_probe.describe(
                            host,
                            port,
                            template.format(channel=channel),
                            username,
                            password,
                        ).status,
                        range(2, max_channels + 1),
                    )
                )

            channels += [
                channel
                for channel, status in zip(range(2, max_channels + 1), results)
                if status == rtsp_probe.OK
            ]

        candidates = [
            (
                channel,
                _stream_url(
                    host, port, template.format(channel=channel), username, password
                ),
            )
            for channel in channels
        ]

        with ThreadPoolExecutor(max_workers=4) as pool:
            alive = list(pool.map(lambda item: _delivers_video(item[1]), candidates))

        streams = [
            {"channel": channel, "url": url}
            for (channel, url), is_alive in zip(candidates, alive)
            if is_alive
        ]

        if streams:
            return {"status": "ok", "vendor": vendor, "streams": streams}

    return {
        "status": "no_streams" if reachable else "unreachable",
        "vendor": "",
        "streams": [],
    }
