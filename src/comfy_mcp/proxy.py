"""Transparent loopback forwarder proxy for remote HTTPS and Basic Auth ComfyUI targets.

This module provides a local proxy server that enables comfy-cli (which only speaks
plain HTTP/ws to local host/port) to connect seamlessly to remote ComfyUI instances
requiring HTTPS, custom ports, or HTTP Basic Authentication (such as Cloudflare Access
or reverse proxies).
"""

from __future__ import annotations

import base64
import http.client
import http.server
import logging
import os
import select
import socket
import ssl
import threading
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Active proxy cache: key -> ComfyProxyServer
_ACTIVE_PROXIES: dict[str, ComfyProxyServer] = {}
_PROXY_LOCK = threading.Lock()
_ACTIVE_UPSTREAM_URL: str | None = None


def get_active_proxy_upstream() -> str | None:
    """Return the upstream URL currently being proxied, if any."""
    return _ACTIVE_UPSTREAM_URL


def get_active_proxy_port() -> int | None:
    """Return the active proxy port if any proxy is currently running."""
    with _PROXY_LOCK:
        if _ACTIVE_PROXIES:
            return next(iter(_ACTIVE_PROXIES.values())).server_port
        return None


def extract_auth_from_url_or_env(url: str) -> tuple[str, str | None]:
    """Extract cleaned URL and Authorization header from URL or environment."""
    parsed = urlparse(url if "://" in url else f"//{url}")
    username = parsed.username
    password = parsed.password

    auth_header: str | None = None
    if username is not None:
        user_pass = f"{username}:{password or ''}"
        token = base64.b64encode(user_pass.encode("utf-8")).decode("ascii")
        auth_header = f"Basic {token}"
    else:
        env_auth = os.environ.get("COMFYUI_AUTH") or os.environ.get("COMFY_BASIC_AUTH")
        if env_auth:
            if env_auth.startswith("Basic "):
                auth_header = env_auth
            elif ":" in env_auth:
                token = base64.b64encode(env_auth.encode("utf-8")).decode("ascii")
                auth_header = f"Basic {token}"
            else:
                token = base64.b64encode(f"{env_auth}:".encode("utf-8")).decode("ascii")
                auth_header = f"Basic {token}"
        else:
            env_user = os.environ.get("COMFYUI_USER") or os.environ.get("COMFY_AUTH_USER")
            env_pass = (
                os.environ.get("COMFYUI_PASSWORD")
                or os.environ.get("COMFYUI_PASS")
                or os.environ.get("COMFY_AUTH_PASS")
            )
            if env_user:
                user_pass = f"{env_user}:{env_pass or ''}"
                token = base64.b64encode(user_pass.encode("utf-8")).decode("ascii")
                auth_header = f"Basic {token}"

    # Reconstruct cleaned URL without username/password
    scheme = parsed.scheme or "https"
    host = parsed.hostname or ""
    port_str = f":{parsed.port}" if parsed.port else ""
    cleaned_url = f"{scheme}://{host}{port_str}"
    return cleaned_url, auth_header


class ComfyProxyHandler(http.server.BaseHTTPRequestHandler):
    """Handles HTTP and WebSocket forwarding to remote ComfyUI."""

    server: ComfyProxyServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        """Route access logs to debug-level logger instead of stderr."""
        logger.debug("%s - - [%s] " + format, self.address_string(), self.log_date_time_string(), *args)

    def do_GET(self) -> None:
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self._handle_websocket()
        else:
            self._handle_http()

    def do_POST(self) -> None:
        self._handle_http()

    def do_PUT(self) -> None:
        self._handle_http()

    def do_DELETE(self) -> None:
        self._handle_http()

    def do_HEAD(self) -> None:
        self._handle_http()

    def do_OPTIONS(self) -> None:
        self._handle_http()

    def do_PATCH(self) -> None:
        self._handle_http()

    def _handle_http(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req_headers: dict[str, str] = {}
        for k, v in self.headers.items():
            k_lower = k.lower()
            if k_lower not in ("host", "connection", "keep-alive"):
                req_headers[k] = v

        upstream_host = self.server.target_host
        if (self.server.target_scheme == "https" and self.server.target_port != 443) or (
            self.server.target_scheme == "http" and self.server.target_port != 80
        ):
            req_headers["Host"] = f"{upstream_host}:{self.server.target_port}"
        else:
            req_headers["Host"] = upstream_host

        # Avoid default Python-urllib user agent being blocked by Cloudflare (error 1010)
        ua = req_headers.get("User-Agent", "")
        if not ua or "Python-urllib" in ua:
            req_headers["User-Agent"] = "comfy-mcp"

        if self.server.auth_header and not any(k.lower() == "authorization" for k in req_headers):
            req_headers["Authorization"] = self.server.auth_header

        max_redirects = 5
        curr_scheme = self.server.target_scheme
        curr_host = self.server.target_host
        curr_port = self.server.target_port
        curr_path = self.path

        try:
            for _ in range(max_redirects):
                if curr_scheme == "https":
                    conn: http.client.HTTPConnection = http.client.HTTPSConnection(
                        curr_host,
                        curr_port,
                        context=self.server.ssl_context,
                        timeout=120.0,
                    )
                else:
                    conn = http.client.HTTPConnection(
                        curr_host,
                        curr_port,
                        timeout=120.0,
                    )
                try:
                    conn.request(self.command, curr_path, body=body, headers=req_headers)
                    resp = conn.getresponse()
                    if resp.status in (301, 302, 303, 307, 308):
                        loc = resp.getheader("Location")
                        if loc:
                            parsed_loc = urlparse(loc)
                            if parsed_loc.scheme:
                                curr_scheme = parsed_loc.scheme
                            if parsed_loc.hostname:
                                curr_host = parsed_loc.hostname
                            if parsed_loc.port:
                                curr_port = parsed_loc.port
                            else:
                                curr_port = 443 if curr_scheme == "https" else 80
                            curr_path = parsed_loc.path or "/"
                            if parsed_loc.query:
                                curr_path += f"?{parsed_loc.query}"
                            resp.read()
                            continue
                    resp_body = resp.read()
                    break
                finally:
                    conn.close()
            else:
                self.send_error(502, "Too many redirects from upstream ComfyUI")
                return

            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                k_lower = k.lower()
                if k_lower not in ("transfer-encoding", "content-encoding", "content-length", "connection"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp_body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(resp_body)
        except Exception as exc:  # noqa: BLE001 - catch network/proxy failure to report 502
            logger.error("HTTP proxy error forwarding to %s:%s%s: %s", curr_host, curr_port, curr_path, exc)
            self.send_error(502, f"ComfyUI upstream proxy error: {exc}")

    def _handle_websocket(self) -> None:
        upstream_sock = None
        try:
            raw_sock = socket.create_connection(
                (self.server.target_host, self.server.target_port),
                timeout=15.0,
            )
            if self.server.target_scheme == "https":
                upstream_sock = self.server.ssl_context.wrap_socket(
                    raw_sock,
                    server_hostname=self.server.target_host,
                )
            else:
                upstream_sock = raw_sock

            upstream_host = self.server.target_host
            if (self.server.target_scheme == "https" and self.server.target_port != 443) or (
                self.server.target_scheme == "http" and self.server.target_port != 80
            ):
                host_val = f"{upstream_host}:{self.server.target_port}"
            else:
                host_val = upstream_host

            lines = [
                f"GET {self.path} HTTP/1.1",
                f"Host: {host_val}",
                "Upgrade: websocket",
                "Connection: Upgrade",
            ]
            for k, v in self.headers.items():
                k_lower = k.lower()
                if k_lower not in ("host", "upgrade", "connection", "authorization", "user-agent"):
                    lines.append(f"{k}: {v}")

            ua = self.headers.get("User-Agent", "")
            if not ua or "Python-urllib" in ua:
                ua = "comfy-mcp"
            lines.append(f"User-Agent: {ua}")

            if self.server.auth_header:
                lines.append(f"Authorization: {self.server.auth_header}")

            lines.append("\r\n")
            req_data = "\r\n".join(lines).encode("latin1")
            upstream_sock.sendall(req_data)

            resp_buf = bytearray()
            while b"\r\n\r\n" not in resp_buf:
                chunk = upstream_sock.recv(4096)
                if not chunk:
                    break
                resp_buf.extend(chunk)

            self.request.sendall(resp_buf)

            if resp_buf.startswith((b"HTTP/1.1 101", b"HTTP/1.0 101")):
                sockets = [self.request, upstream_sock]
                while True:
                    r, _, _ = select.select(sockets, [], [], 60.0)
                    if not r:
                        continue
                    for s in r:
                        other = upstream_sock if s is self.request else self.request
                        try:
                            data = s.recv(65536)
                        except OSError:
                            data = None
                        if not data:
                            return
                        try:
                            other.sendall(data)
                        except OSError:
                            return
        except Exception as exc:  # noqa: BLE001 - logged below
            logger.error("WebSocket proxy error to %s: %s", self.server.target_host, exc)
        finally:
            if upstream_sock:
                try:
                    upstream_sock.close()
                except OSError:
                    pass
            self.close_connection = True


class ComfyProxyServer(http.server.ThreadingHTTPServer):
    """Local loopback HTTP + WebSocket proxy server."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        bind_address: tuple[str, int],
        target_scheme: str,
        target_host: str,
        target_port: int,
        auth_header: str | None,
        ssl_context: ssl.SSLContext,
    ) -> None:
        self.target_scheme = target_scheme
        self.target_host = target_host
        self.target_port = target_port
        self.auth_header = auth_header
        self.ssl_context = ssl_context
        super().__init__(bind_address, ComfyProxyHandler)


def get_or_start_proxy(url: str) -> tuple[str, int]:
    """Start or retrieve loopback proxy for the given ComfyUI target URL."""
    global _ACTIVE_UPSTREAM_URL

    cleaned_url, auth_header = extract_auth_from_url_or_env(url)
    parsed = urlparse(cleaned_url)
    scheme = parsed.scheme.lower() or "https"
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if scheme == "https" else 80)

    insecure = os.environ.get("COMFYUI_INSECURE", "").strip().lower() in ("1", "true", "yes") or (
        os.environ.get("COMFYUI_SSL_VERIFY", "1").strip().lower() in ("0", "false", "no")
    )
    if insecure:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
    else:
        ssl_ctx = ssl.create_default_context()

    cache_key = f"{scheme}://{host}:{port}:{auth_header}"

    with _PROXY_LOCK:
        if cache_key in _ACTIVE_PROXIES:
            server_instance = _ACTIVE_PROXIES[cache_key]
            _ACTIVE_UPSTREAM_URL = cleaned_url
            return "127.0.0.1", server_instance.server_port

        server_instance = ComfyProxyServer(
            ("127.0.0.1", 0),
            target_scheme=scheme,
            target_host=host,
            target_port=port,
            auth_header=auth_header,
            ssl_context=ssl_ctx,
        )
        thread = threading.Thread(
            target=server_instance.serve_forever,
            daemon=True,
            name="comfy-mcp-proxy",
        )
        thread.start()

        _ACTIVE_PROXIES[cache_key] = server_instance
        _ACTIVE_UPSTREAM_URL = cleaned_url
        logger.info(
            "Started ComfyUI local proxy on 127.0.0.1:%d forwarding to %s://%s:%d (auth=%s)",
            server_instance.server_port,
            scheme,
            host,
            port,
            bool(auth_header),
        )
        return "127.0.0.1", server_instance.server_port
