import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict

import zmq
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from xwalk2.models import (
    Animations,
    APIButtonPress,
    APIQueueWalk,
    APIRequests,
    APIResponse,
    APIStatusRequest,
    APITimerExpired,
)


class ActionRequest(BaseModel):
    action: str


class SystemStatus(BaseModel):
    playing: bool
    components: Dict[str, float]  # Using float for timestamp
    uptime: float
    animations: Animations | None = None  # Optional animations data


class APIController:
    def __init__(self):
        self.context = zmq.Context()
        self.api_socket = None  # Single REQ socket for all communication
        self.start_time = time.time()

    def start(self):
        """Initialize ZMQ connection"""
        try:
            self.api_socket = self.context.socket(zmq.REQ)
            self.api_socket.connect("tcp://localhost:5559")
            print("API Controller initialized successfully")
            print("Connected to controller on port 5559")
        except Exception as e:
            print(f"Failed to initialize API Controller: {e}")
            raise

    def stop(self):
        """Clean up ZMQ connection"""
        if self.api_socket:
            self.api_socket.close()
        if self.context:
            self.context.term()

    def _send_request(self, request: APIRequests) -> APIResponse:
        if not self.api_socket:
            raise RuntimeError("API Controller not initialized")
        try:
            self.api_socket.send_string(request.model_dump_json())
            if self.api_socket.poll(timeout=5000):
                response_data = self.api_socket.recv_string()
                return APIResponse.model_validate_json(response_data)
            else:
                raise TimeoutError("Controller did not respond within timeout")
        except zmq.ZMQError as e:
            print(f"ZMQ communication error: {e}")
            raise ConnectionError("Failed to communicate with controller")

    def timer_expired(self) -> APIResponse:
        """Send timer expired event"""
        return self._send_request(APITimerExpired())

    def press_button(self) -> APIResponse:
        return self._send_request(APIButtonPress())

    def queue_walk(self, walk: str) -> APIResponse:
        """Queue a walk animation"""
        request = APIQueueWalk(type="queue_walk", walk=walk)
        return self._send_request(request)

    def get_status(self) -> APIResponse:
        request = APIStatusRequest()
        return self._send_request(request)


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


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    status = api_controller.get_status()
    return templates.TemplateResponse(
        "index.html", {"request": request, "status": status, "now": datetime.now()}
    )


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


@app.post("/timer", response_class=HTMLResponse)
async def fire_timer(request: Request):
    """Handle timer expired action (htmx or API)"""
    status = api_controller.timer_expired()
    return templates.TemplateResponse(
        "components/status.html",
        {"request": request, "status": status, "now": datetime.now()},
    )


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting Crosswalk V2 API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
