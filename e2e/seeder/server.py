"""
HTTP sidecar seeding e2e scenarios into Django's database on request.

Endpoints:
    GET  /health            -> {"status": "ok", "scenarios": [...]}
    POST /scenarios/<name>  -> the scenario's manifest; the body is a JSON
                               object passed to the scenario as params

Errors are JSON objects {"error": "..."}: 400 for an invalid body or
params, 404 for an unknown path or scenario, 405 for a wrong method and 500
for an unexpected failure.

The server is single-threaded, so seeding requests are handled one at a
time and never interleave in the database.

Run inside the Django image: python -m e2e.seeder.server
(port from E2E_SEEDER_PORT, default 8090).
"""

import json
import os
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote, urlsplit

from e2e import scenarios  # noqa: F401  (registers the scenarios)
from e2e.scenarios.registry import (
    get_scenario,
    scenario_names,
    ScenarioParamsError,
    UnknownScenarioError,
)

DEFAULT_PORT = 8090
PORT_ENV_VAR = "E2E_SEEDER_PORT"
# Scenario params are small; anything bigger is a client error.
MAX_BODY_BYTES = 1024 * 1024
SCENARIO_PATH = re.compile(r"/scenarios/([^/]+)")
LOG_PREFIX = "[e2e-seeder]"


def _log(message):
    """
    Write a log line to stderr.

            Parameters:
                    message (str): Text to log
    """
    print(f"{LOG_PREFIX} {message}", file=sys.stderr, flush=True)


def _error(status, message):
    """
    Return an error response.

            Parameters:
                    status (int): HTTP status
                    message (str): Error description

            Returns:
                    response (tuple): (status, {"error": message})
    """
    return status, {"error": message}


def _parse_params(body):
    """
    Parse a request body into scenario params.

            Parameters:
                    body (bytes): Raw request body

            Returns:
                    params (dict | None): The parsed JSON object, or None if the
                    body is not a UTF-8 encoded JSON object
    """
    try:
        params = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return params if isinstance(params, dict) else None


def _run_scenario(name, body):
    """
    Run a registered scenario with params parsed from the body.

            Parameters:
                    name (str): Scenario name
                    body (bytes): Raw request body

            Returns:
                    response (tuple): (status, body dict)
    """
    try:
        func = get_scenario(name)
    except UnknownScenarioError:
        return _error(404, f"unknown scenario {name!r}")
    params = _parse_params(body)
    if params is None:
        return _error(400, "request body must be a JSON object")
    try:
        return 200, func(params)
    except ScenarioParamsError as error:
        return _error(400, str(error))
    except Exception as error:  # noqa: B902  (reported to the caller as 500)
        _log(f"scenario {name!r} failed:\n{traceback.format_exc()}")
        return _error(500, f"scenario {name!r} failed: {type(error).__name__}: {error}")


def dispatch(method, path, body):
    """
    Route a request to its handler.

            Parameters:
                    method (str): HTTP method
                    path (str): Request path, optionally with a query string
                    body (bytes): Raw request body

            Returns:
                    response (tuple): (status, JSON-serializable body dict)
    """
    route = urlsplit(path).path
    if route == "/health":
        if method != "GET":
            return _error(405, f"method {method} not allowed on {route}")
        return 200, {"status": "ok", "scenarios": scenario_names()}
    match = SCENARIO_PATH.fullmatch(route)
    if not match:
        return _error(404, f"no such path {route}")
    if method != "POST":
        return _error(405, f"method {method} not allowed on {route}")
    return _run_scenario(unquote(match.group(1)), body)


class SeederRequestHandler(BaseHTTPRequestHandler):
    """
    Serve dispatch() over HTTP with JSON responses.
    """

    server_version = "E2ESeeder/1.0"

    def _handle(self):
        """
        Read the request body, dispatch it and write the JSON response.
        """
        from django.db import close_old_connections

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            status, payload = _error(400, "invalid Content-Length")
        else:
            body = self.rfile.read(length)
            # The process outlives many requests, so stale or broken database
            # connections are dropped as Django does around each request.
            close_old_connections()
            try:
                status, payload = dispatch(self.command, self.path, body)
            finally:
                close_old_connections()
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _handle

    def log_message(self, format, *args):
        """
        Log a request line to stderr.

                Parameters:
                        format (str): printf-style format from the base class
                        *args: Format arguments
        """
        _log(format % args)


class SeederHTTPServer(HTTPServer):
    """
    Single-threaded HTTP server with a listen backlog for parallel workers.
    """

    # Parallel Playwright workers may connect at once; queue them instead of
    # refusing connections while one scenario is being seeded.
    request_queue_size = 64


def _port():
    """
    Return the port to listen on.

            Returns:
                    port (int): E2E_SEEDER_PORT, or DEFAULT_PORT when unset

            Raises:
                    ValueError: If E2E_SEEDER_PORT is not a valid port number
    """
    raw = os.environ.get(PORT_ENV_VAR) or str(DEFAULT_PORT)
    port = int(raw)
    if not 0 < port < 65536:
        raise ValueError(f"{PORT_ENV_VAR} must be a port number, got {raw!r}")
    return port


def main():
    """
    Set up Django and serve seeding requests until interrupted.
    """
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "apartment_application_service.settings"
    )
    import django

    django.setup()
    port = _port()
    server = SeederHTTPServer(("0.0.0.0", port), SeederRequestHandler)
    _log(f"listening on port {port}; scenarios: {', '.join(scenario_names())}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
