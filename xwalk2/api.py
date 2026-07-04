import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import parse_qs

import zmq
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from xwalk2.models import (
    APIQueueClear,
    APIButtonPress,
    APIQueueWalk,
    APIRequests,
    APIResponse,
    APIStatusRequest,
    APITimerExpired,
    SysCommand,
)


CONTROLLER_ADDRESS = "tcp://localhost:5559"

# This box's hostname; used to seed the known-hosts list shown in the UI.
OWN_HOST = os.getenv("XWALK_HOSTNAME", "crosswalk-a")

# Plausible-time guard: reject anything outside ~[2020-01-01, 2100-01-01) so a
# bogus browser value can't set the clock to 1970 or the far future.
_MIN_EPOCH = 1577836800  # 2020-01-01 UTC
_MAX_EPOCH = 4102444800  # 2100-01-01 UTC

# Heartbeat component name -> systemd unit, for the per-component restart button.
COMPONENT_UNITS = {
    "timer": "xwalk_timer",
    "audio-player": "xwalk_audio_player",
    "button_led": "xwalk_button_light",
    "button_physical": "xwalk_button_switch",
    "matrix-viewer": "xwalk_matrix_driver",
    "sys-control": "xwalk_sys_control",
}


def _known_hosts(status) -> list:
    """The set of boxes we know about: ourselves plus any host seen in a
    component heartbeat."""
    hosts = {OWN_HOST}
    for name in status.components:
        parts = name.split("/", 1)
        if len(parts) == 2 and parts[1]:
            hosts.add(parts[1])
    return sorted(hosts)


class APIController:
    def __init__(self):
        self.context = zmq.Context()
        self.api_socket = None  # Single REQ socket for all communication
        self.start_time = time.time()
        # Serialize access: a REQ socket requires strict send/recv alternation,
        # so concurrent FastAPI requests must not share it simultaneously.
        self._lock = threading.Lock()

    def _open_socket(self):
        """(Re)create the REQ socket and connect to the controller."""
        if self.api_socket is not None:
            # Discard a socket that may be in a bad state. LINGER=0 so a pending
            # unsent/unreceived message doesn't block close().
            self.api_socket.close(linger=0)
        self.api_socket = self.context.socket(zmq.REQ)
        self.api_socket.connect(CONTROLLER_ADDRESS)

    def start(self):
        """Initialize ZMQ connection"""
        try:
            self._open_socket()
            print("API Controller initialized successfully")
            print("Connected to controller on port 5559")
        except Exception as e:
            print(f"Failed to initialize API Controller: {e}")
            raise

    def stop(self):
        """Clean up ZMQ connection"""
        if self.api_socket:
            self.api_socket.close(linger=0)
        if self.context:
            self.context.term()

    def _send_request(self, request: APIRequests) -> APIResponse:
        if not self.api_socket:
            raise RuntimeError("API Controller not initialized")
        # A REQ socket is a strict lockstep state machine. If a request times out
        # (we never recv the reply) or errors mid-exchange, the socket is left in
        # an unusable state and every later request would fail. Hold a lock so
        # exchanges don't interleave, and rebuild the socket on any failure.
        with self._lock:
            try:
                self.api_socket.send_string(request.model_dump_json())
                if self.api_socket.poll(timeout=5000):
                    response_data = self.api_socket.recv_string()
                    return APIResponse.model_validate_json(response_data)
                else:
                    self._open_socket()  # reset the wedged REQ socket
                    raise TimeoutError("Controller did not respond within timeout")
            except zmq.ZMQError as e:
                print(f"ZMQ communication error: {e}")
                self._open_socket()  # reset the wedged REQ socket
                raise ConnectionError("Failed to communicate with controller")

    def timer_expired(self) -> APIResponse:
        """Send timer expired event"""
        return self._send_request(APITimerExpired())

    def press_button(self) -> APIResponse:
        return self._send_request(APIButtonPress())

    def queue_walk(self, walk: str) -> APIResponse:
        """Queue a walk animation"""
        request = APIQueueWalk(walk=walk)
        return self._send_request(request)

    def queue_clear(self) -> APIResponse:
        """Queue a walk animation"""
        request = APIQueueClear()
        return self._send_request(request)

    def get_status(self) -> APIResponse:
        request = APIStatusRequest()
        return self._send_request(request)

    def sys_command(self, action, target="all", unit=None, epoch=None) -> APIResponse:
        """Ask the controller to broadcast a system-control command to the
        per-host sys_control agents."""
        return self._send_request(
            SysCommand(action=action, target=target, unit=unit, epoch=epoch)
        )


api_controller = APIController()


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_controller.start()
    yield
    api_controller.stop()


app = FastAPI(
    title="Crosswalk V2 API",
    description="API for controlling the Crosswalk V2 system",
    version="0.2.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
# Available to every template for the per-component restart buttons.
templates.env.globals["component_units"] = COMPONENT_UNITS


def _status_response(request: Request, status, notice: str):
    """Render the status partial with an optional one-off notice."""
    return templates.TemplateResponse(
        "components/status.html",
        {"request": request, "status": status, "now": datetime.now(), "notice": notice},
    )


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    status = api_controller.get_status()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "status": status,
            "now": datetime.now(),
            "hosts": _known_hosts(status),
        },
    )


@app.post("/restart/all", response_class=HTMLResponse)
async def restart_all(request: Request):
    """Restart all xwalk components on every box."""
    resp = api_controller.sys_command("restart_all", target="all")
    return _status_response(request, resp, resp.message)


@app.post("/restart/{host}/{unit}", response_class=HTMLResponse)
async def restart_unit(host: str, unit: str, request: Request):
    """Restart one component (or all, if unit == 'all') on a specific box."""
    if unit == "all":
        resp = api_controller.sys_command("restart_all", target=host)
    else:
        resp = api_controller.sys_command("restart", target=host, unit=unit)
    return _status_response(request, resp, resp.message)


@app.post("/reboot/{host}", response_class=HTMLResponse)
async def reboot(host: str, request: Request):
    """Reboot a box, or all of them when host == 'all'."""
    resp = api_controller.sys_command("reboot", target=host)
    return _status_response(request, resp, resp.message)


@app.get("/status", response_class=HTMLResponse)
async def status_view(request: Request):
    status = api_controller.get_status()
    return templates.TemplateResponse(
        "components/status.html",
        {"request": request, "status": status, "now": datetime.now()},
    )


@app.post("/button", response_class=HTMLResponse)
async def press_button(request: Request):
    """Handle button press action (htmx or API)"""
    status = api_controller.press_button()
    return templates.TemplateResponse(
        "components/status.html",
        {"request": request, "status": status, "now": datetime.now()},
    )


@app.post("/queue/{walk}", response_class=HTMLResponse)
async def queue(walk: str, request: Request):
    """Handle button press action (htmx or API)"""
    status = api_controller.queue_walk(walk)
    return templates.TemplateResponse(
        "components/status.html",
        {"request": request, "status": status, "now": datetime.now()},
    )

@app.delete("/queue/", response_class=HTMLResponse)
async def queue_clear(request: Request):
    """Handle button press action (htmx or API)"""
    status = api_controller.queue_clear()
    return templates.TemplateResponse(
        "components/status.html",
        {"request": request, "status": status, "now": datetime.now()},
    )


@app.post("/timer", response_class=HTMLResponse)
async def fire_timer(request: Request):
    """Handle timer expired action (htmx or API)"""
    status = api_controller.timer_expired()
    return templates.TemplateResponse(
        "components/status.html",
        {"request": request, "status": status, "now": datetime.now()},
    )


@app.post("/clock", response_class=HTMLResponse)
async def set_clock(request: Request):
    """Set the signs' system clocks from the browser's time.

    The browser posts its own `Date.now()` (Unix epoch in milliseconds, UTC) as
    an url-encoded form field. We broadcast it as a `set_clock` command to every
    sign's sys_control agent. Parsing the body by hand avoids a
    `python-multipart` dependency.
    """
    body = (await request.body()).decode("utf-8", "replace")
    raw = parse_qs(body).get("epoch_ms", [None])[0]
    try:
        seconds = float(raw) / 1000.0
    except (TypeError, ValueError):
        seconds = None

    if seconds is None:
        resp = api_controller.get_status()
        notice = "Missing or invalid time value; clock unchanged."
    elif not (_MIN_EPOCH <= seconds < _MAX_EPOCH):
        resp = api_controller.get_status()
        notice = f"Refused implausible time ({seconds:.0f}); clock unchanged."
    else:
        resp = api_controller.sys_command("set_clock", target="all", epoch=seconds)
        notice = "🕐 " + resp.message
    return _status_response(request, resp, notice)


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting Crosswalk V2 API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
