"""Tests for the loopback forwarder proxy and Basic Auth / HTTPS support."""

from __future__ import annotations

import http.server
import threading
import urllib.request

import pytest

from comfy_mcp import proxy, server, target


class _MockAuthServer(http.server.ThreadingHTTPServer):
    def __init__(self, bind_address: tuple[str, int]) -> None:
        super().__init__(bind_address, _MockAuthHandler)
        self.received_headers: dict[str, str] = {}
        self.received_body: bytes = b""


class _MockAuthHandler(http.server.BaseHTTPRequestHandler):
    server: _MockAuthServer

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        self.server.received_headers = dict(self.headers.items())
        auth = self.headers.get("Authorization", "")
        if auth != "Basic dGVzdHVzZXI6dGVzdHBhc3M=":
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Test"')
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "auth": true}')

    def do_POST(self) -> None:
        self.server.received_headers = dict(self.headers.items())
        content_len = int(self.headers.get("Content-Length", 0))
        self.server.received_body = self.rfile.read(content_len) if content_len > 0 else b""

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "posted"}')


def test_extract_auth_from_url():
    url = "https://myuser:mypassword@comfy.crushing.xyz:8443/view"
    cleaned, auth = proxy.extract_auth_from_url_or_env(url)
    assert cleaned == "https://comfy.crushing.xyz:8443"
    assert auth == "Basic bXl1c2VyOm15cGFzc3dvcmQ="


def test_extract_auth_from_env_auth(monkeypatch):
    monkeypatch.setenv("COMFYUI_AUTH", "admin:secret123")
    cleaned, auth = proxy.extract_auth_from_url_or_env("https://comfy.crushing.xyz")
    assert cleaned == "https://comfy.crushing.xyz"
    assert auth == "Basic YWRtaW46c2VjcmV0MTIz"


def test_extract_auth_from_env_user_pass(monkeypatch):
    monkeypatch.setenv("COMFYUI_USER", "alice")
    monkeypatch.setenv("COMFYUI_PASSWORD", "wonderland")
    cleaned, auth = proxy.extract_auth_from_url_or_env("https://comfy.crushing.xyz")
    assert cleaned == "https://comfy.crushing.xyz"
    assert auth == "Basic YWxpY2U6d29uZGVybGFuZA=="


def test_proxy_forwards_http_with_basic_auth():
    # Spin up mock upstream server requiring basic auth
    mock_server = _MockAuthServer(("127.0.0.1", 0))
    thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
    thread.start()
    mock_port = mock_server.server_port

    try:
        # Start proxy pointing to mock server with credentials testuser:testpass
        proxy_host, proxy_port = proxy.get_or_start_proxy(
            f"http://testuser:testpass@127.0.0.1:{mock_port}"
        )
        assert proxy_host == "127.0.0.1"

        # Client makes plain GET to proxy with no Auth header
        req = urllib.request.Request(f"http://127.0.0.1:{proxy_port}/prompt")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = resp.read()
            assert resp.status == 200
            assert b'"auth": true' in data

        # Check mock server received the Authorization header
        assert "Authorization" in mock_server.received_headers
        assert mock_server.received_headers["Authorization"] == "Basic dGVzdHVzZXI6dGVzdHBhc3M="

        # Client makes POST to proxy
        post_req = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/prompt",
            data=b'{"prompt": "cat"}',
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(post_req, timeout=5.0) as resp:
            assert resp.status == 200

        assert mock_server.received_body == b'{"prompt": "cat"}'
    finally:
        mock_server.shutdown()


def test_target_proxy_activated_for_real_domain(monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "https://comfy.crushing.xyz")
    host, port, source = target._comfy_target()
    assert host == "127.0.0.1"
    assert port > 0
    assert source == "COMFYUI_URL"
    assert target._get_active_proxy_upstream() == "https://comfy.crushing.xyz"


def test_target_proxy_activated_with_credentials(monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "https://admin:pwd@comfy.crushing.xyz")
    host, port, source = target._comfy_target()
    assert host == "127.0.0.1"
    assert port > 0
    assert source == "COMFYUI_URL"


def test_target_proxy_inactive_for_plain_http(monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "http://gpu.example:9001")
    assert target._comfy_target() == ("gpu.example", 9001, "COMFYUI_URL")


def test_target_proxy_inactive_for_test_dummy_https(monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "https://gpu.example:8188")
    with pytest.raises(server.ComfyCliError, match="scheme"):
        target._comfy_target()
