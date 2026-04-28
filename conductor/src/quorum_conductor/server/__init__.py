"""Local HTTP server the UI consumes (Phase 5 onward).

stdlib-only — `http.server.ThreadingHTTPServer` with a tiny route table.
Phase 5 ships read endpoints for state / deliberations / plan / events
plus POST /api/step to drive a single invocation. Phase 8 will add
WebSocket pushes; we keep the routing simple enough here that swapping
in a real ASGI server later is a 100-line change, not a 1000-line one.

The server is intentionally single-workspace: started with a
`WorkspacePaths`, it serves only that root. A future "workspace
switcher" would run multiple instances on different ports.
"""

from .http_app import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    QuorumHTTPServer,
    create_server,
    serve_forever,
)

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "QuorumHTTPServer",
    "create_server",
    "serve_forever",
]
