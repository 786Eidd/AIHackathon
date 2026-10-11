# app/discovery/rtsp_probe.py

"""
Minimal RTSP client used only to ask "does this stream exist, and do these
credentials open it?".

A DESCRIBE round trip answers that in a few milliseconds, where opening the
stream through FFmpeg takes seconds per attempt. Discovery has to try many
candidate paths and channels per device, so the cheap check runs first and
only the survivors are opened for real.
"""

from __future__ import annotations

import base64
import hashlib
import re
import socket
from dataclasses import dataclass
from typing import Dict, Optional

OK = "ok"
AUTH_REQUIRED = "auth_required"
NOT_FOUND = "not_found"
UNREACHABLE = "unreachable"


@dataclass
class ProbeResult:
    status: str
    code: int = 0
    server: str = ""


def _read_response(sock: socket.socket) -> Optional[Dict[str, object]]:
    data = b""

    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)

        if not chunk:
            break

        data += chunk

        if len(data) > 65536:
            break

    head = data.split(b"\r\n\r\n", 1)[0].decode("latin-1", errors="replace")
    lines = head.split("\r\n")

    match = re.match(r"RTSP/\d\.\d\s+(\d{3})", lines[0]) if lines else None

    if match is None:
        return None

    headers: Dict[str, list] = {}

    for line in lines[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers.setdefault(name.strip().lower(), []).append(value.strip())

    return {"code": int(match.group(1)), "headers": headers}


def _digest_header(
    challenge: str,
    username: str,
    password: str,
    method: str,
    uri: str,
) -> str:
    fields = dict(re.findall(r'(\w+)="?([^",]+)"?', challenge))

    realm = fields.get("realm", "")
    nonce = fields.get("nonce", "")

    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()

    return (
        f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
        f'uri="{uri}", response="{response}"'
    )


def _authorization(
    challenges: list,
    username: str,
    password: str,
    method: str,
    uri: str,
) -> Optional[str]:
    # Prefer Digest when the camera offers both.
    for challenge in challenges:
        if challenge.lower().startswith("digest"):
            return _digest_header(challenge, username, password, method, uri)

    for challenge in challenges:
        if challenge.lower().startswith("basic"):
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            return f"Basic {token}"

    return None


def describe(
    host: str,
    port: int,
    path: str,
    username: str = "",
    password: str = "",
    timeout: float = 3.0,
) -> ProbeResult:
    """
    Sends DESCRIBE for rtsp://host:port/path, answering one auth challenge
    if credentials were supplied.
    """
    uri = f"rtsp://{host}:{port}{path}"

    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError:
        return ProbeResult(UNREACHABLE)

    try:
        sock.settimeout(timeout)

        def request(cseq: int, authorization: Optional[str]) -> Optional[dict]:
            lines = [
                f"DESCRIBE {uri} RTSP/1.0",
                f"CSeq: {cseq}",
                "User-Agent: NexGen-Discovery",
                "Accept: application/sdp",
            ]

            if authorization:
                lines.append(f"Authorization: {authorization}")

            sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())

            return _read_response(sock)

        reply = request(1, None)

        if reply is None:
            return ProbeResult(UNREACHABLE)

        server = (reply["headers"].get("server") or [""])[0]

        if reply["code"] == 401 and username:
            authorization = _authorization(
                reply["headers"].get("www-authenticate", []),
                username,
                password,
                "DESCRIBE",
                uri,
            )

            if authorization:
                reply = request(2, authorization) or reply

        code = reply["code"]
        server = server or (reply["headers"].get("server") or [""])[0]

        if code == 200:
            return ProbeResult(OK, code, server)

        if code in (401, 403):
            return ProbeResult(AUTH_REQUIRED, code, server)

        return ProbeResult(NOT_FOUND, code, server)

    except OSError:
        return ProbeResult(UNREACHABLE)

    finally:
        try:
            sock.close()
        except OSError:
            pass
