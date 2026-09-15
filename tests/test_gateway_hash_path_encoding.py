"""Gateway must forward a decoded-but-special-character path correctly.

Flask/Werkzeug percent-decodes the incoming path before the route handler
runs. If that decoded string (e.g. containing a literal '#') were passed
straight to `requests.request(url=...)`, the '#' would be interpreted as a
URL fragment delimiter and everything after it silently dropped before the
request ever reached the upstream target — the upstream would receive a
different, truncated path than the client actually asked for. This was
discovered while building scenarios/JS-P2-008 (Missing Encoding), whose
target asset filename contains a literal '#' once decoded.
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from werkzeug.serving import make_server

from tempera.core.sequence import SequenceAllocator
from tempera.observe.gateway import create_app


def test_path_with_hash_reaches_upstream_undamaged():
    received_paths = []

    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            received_paths.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            self.wfile.write(b"\xff\xd8\xff")

        def log_message(self, *_):
            pass

    target = ThreadingHTTPServer(("127.0.0.1", 0), Target)
    target_thread = threading.Thread(target=target.serve_forever, daemon=True)
    target_thread.start()
    events = []
    app = create_app(
        f"http://127.0.0.1:{target.server_port}", "run-1", "agent", events.append,
        sequence_allocator=SequenceAllocator(),
    )
    gateway = make_server("127.0.0.1", 0, app)
    gateway_thread = threading.Thread(target=gateway.serve_forever, daemon=True)
    gateway_thread.start()
    try:
        client = app.test_client()
        # Werkzeug's test client percent-encodes this the same way a real
        # HTTP client would when sending the request line; the gateway
        # handler then receives it already decoded by Flask's routing,
        # exactly like a live request would.
        response = client.get(
            "/assets/uploads/%E1%93%9A%E1%98%8F%E1%97%A2-%23zatschi.jpg"
        )
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/jpeg"
        # The upstream target must see the FULL path, not a copy truncated
        # at the '#'.
        assert len(received_paths) == 1
        assert "%23zatschi" in received_paths[0] or "#zatschi" in received_paths[0]
        assert received_paths[0].endswith(".jpg") or received_paths[0].endswith(
            "%2Ejpg"
        )
        assert events[0].attributes["status"] == 200
    finally:
        gateway.shutdown()
        gateway.server_close()
        target.shutdown()
        target.server_close()
