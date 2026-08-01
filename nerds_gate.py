#!/usr/bin/env python3
"""
Nerds Gate v0.8

Public relay for Nerds Portal international mode.

Testing:
  python nerds_gate.py --host 0.0.0.0 --port 15300
  Gate URL in Nerds Portal: ws://PUBLIC_SERVER_IP:15300/ws

Render:
  Render provides PORT. Start command can be: python nerds_gate.py
  Gate URL in Nerds Portal: wss://YOUR-SERVICE.onrender.com/ws

Production:
  Put this behind HTTPS/WSS on port 443 with a reverse proxy.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


NUMBER_RE = re.compile(r"^\+153\d{6}$")
GATE_PROTOCOL = "nerds.gate.v1"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def clean_number(text):
    raw = re.sub(r"[\s\-()]+", "", str(text or ""))
    if re.fullmatch(r"\d{6}", raw):
        return "+153" + raw
    if raw.startswith("153") and re.fullmatch(r"153\d{6}", raw):
        return "+" + raw
    return raw


def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("websocket closed")
        data += chunk
    return data


def recv_frame(sock):
    first, second = recv_exact(sock, 2)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", recv_exact(sock, 8))[0]
    key = recv_exact(sock, 4) if masked else b""
    payload = recv_exact(sock, length) if length else b""
    if masked:
        payload = bytes(b ^ key[i % 4] for i, b in enumerate(payload))
    return opcode, payload


def send_frame(sock, payload, opcode=1):
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    first = 0x80 | opcode
    length = len(payload)
    if length < 126:
        header = bytes([first, length])
    elif length <= 0xFFFF:
        header = bytes([first, 126]) + struct.pack("!H", length)
    else:
        header = bytes([first, 127]) + struct.pack("!Q", length)
    sock.sendall(header + payload)


class GateState:
    def __init__(self):
        self.lock = threading.Lock()
        self.clients = {}
        self.rooms = {}

    def register(self, number, client):
        with self.lock:
            old = self.clients.get(number)
            if old is not None and old is not client:
                old.close()
            self.clients[number] = client

    def unregister(self, client):
        with self.lock:
            if client.number and self.clients.get(client.number) is client:
                self.clients.pop(client.number, None)

    def get(self, number):
        with self.lock:
            return self.clients.get(number)

    def online(self):
        with self.lock:
            return sorted(self.clients.keys())


STATE = GateState()


class GateClient:
    def __init__(self, handler):
        self.handler = handler
        self.sock = handler.connection
        self.lock = threading.Lock()
        self.number = ""
        self.name = ""
        self.device_id = ""
        self.alive = True

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except Exception:
            pass

    def send_json(self, item):
        raw = json.dumps(item, ensure_ascii=False)
        with self.lock:
            send_frame(self.sock, raw)

    def run(self):
        self.send_json({"protocol": GATE_PROTOCOL, "type": "welcome", "server": "Nerds Gate v0.8", "time": now()})
        while self.alive:
            opcode, payload = recv_frame(self.sock)
            if opcode == 8:
                break
            if opcode == 9:
                send_frame(self.sock, payload, opcode=10)
                continue
            if opcode != 1:
                continue
            try:
                item = json.loads(payload.decode("utf-8", "replace"))
            except Exception:
                self.send_json({"protocol": GATE_PROTOCOL, "type": "error", "error": "invalid_json"})
                continue
            self.handle(item)

    def handle(self, item):
        kind = item.get("type", "")
        if kind == "register":
            number = clean_number(item.get("number", ""))
            if not NUMBER_RE.match(number or ""):
                self.send_json({"protocol": GATE_PROTOCOL, "type": "error", "error": "invalid_number"})
                return
            self.number = number
            self.name = item.get("name", "")
            self.device_id = item.get("device_id", "")
            STATE.register(number, self)
            self.send_json({
                "protocol": GATE_PROTOCOL,
                "type": "registered",
                "number": number,
                "online": True,
                "time": now(),
            })
            print(f"[{now()}] online {number} {self.name}")
            return

        if kind == "message":
            target_number = clean_number(item.get("to") or (item.get("payload") or {}).get("to"))
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            if not NUMBER_RE.match(target_number or ""):
                self.send_json({"protocol": GATE_PROTOCOL, "type": "ack", "ok": False, "error": "invalid_target"})
                return
            target = STATE.get(target_number)
            if target is None:
                self.send_json({
                    "protocol": GATE_PROTOCOL,
                    "type": "ack",
                    "ok": False,
                    "to": target_number,
                    "error": "target_offline",
                })
                return
            target.send_json({"protocol": GATE_PROTOCOL, "type": "message", "payload": payload, "via": "nerds_gate"})
            self.send_json({"protocol": GATE_PROTOCOL, "type": "ack", "ok": True, "to": target_number, "time": now()})
            return

        if kind == "who":
            self.send_json({"protocol": GATE_PROTOCOL, "type": "online", "numbers": STATE.online(), "time": now()})
            return

        if kind == "room_create":
            code = item.get("code") or ("NRD-" + base64.b32encode(os.urandom(4)).decode("ascii").rstrip("="))
            STATE.rooms[code] = {"host": self.number, "created_at": now(), "private": bool(item.get("private", True))}
            self.send_json({"protocol": GATE_PROTOCOL, "type": "room_created", "code": code, "host": self.number})
            return

        if kind == "room_join":
            code = item.get("code", "")
            room = STATE.rooms.get(code)
            if not room:
                self.send_json({"protocol": GATE_PROTOCOL, "type": "room_joined", "ok": False, "error": "room_not_found"})
                return
            host = STATE.get(room.get("host", ""))
            if host is not None:
                host.send_json({"protocol": GATE_PROTOCOL, "type": "room_join_request", "code": code, "from": self.number})
            self.send_json({"protocol": GATE_PROTOCOL, "type": "room_joined", "ok": True, "code": code, "host": room.get("host")})
            return

        self.send_json({"protocol": GATE_PROTOCOL, "type": "error", "error": "unknown_type"})


class GateHandler(BaseHTTPRequestHandler):
    server_version = "NerdsGate/0.8"

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path.startswith("/ws"):
            return self.websocket()
        payload = {
            "ok": True,
            "server": "Nerds Gate v0.8",
            "protocol": GATE_PROTOCOL,
            "online_count": len(STATE.online()),
            "time": now(),
        }
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def websocket(self):
        key = self.headers.get("Sec-WebSocket-Key", "")
        if not key:
            self.send_error(400, "Missing Sec-WebSocket-Key")
            return
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        client = GateClient(self)
        try:
            client.run()
        except Exception:
            pass
        finally:
            STATE.unregister(client)
            if client.number:
                print(f"[{now()}] offline {client.number}")
            client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "15300")))
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), GateHandler)
    print(f"Nerds Gate v0.8 listening on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
