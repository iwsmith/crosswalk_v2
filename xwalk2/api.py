import time
from contextlib import asynccontextmanager
from typing import Dict

import zmq
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime

from xwalk2.models import APIResponse, APIStatusRequest, APITimerExpired, APIQueueWalk, Animations, APIButtonPress, APIRequests, parse_api


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


def render_status_html(status: APIResponse) -> str:
    components_html = "".join(
        f"<li><strong>{name}</strong>: Last seen { round((datetime.now() - timestamp).total_seconds())}s ago</li>"
        for name, timestamp in status.components.items()
    )

    if status.animations:
        animations_html = ""

        items_html = ""
        for walk in status.animations.intros:
            items_html += f"<li>{walk}</li>\n"
        animations_html += f"<div><strong>Intros</strong><ul>{items_html}</ul></div>"

        items_html = ""
        for walk, info in status.animations.walks.items():
            items_html += (
                f"<li>{walk} - {info.category} "
                f"<button hx-post='/queue/{walk}' "
                f"style='font-size:1em;padding:0 0.5em;height:1.5em;vertical-align:middle;line-height:1.2;' "
                f"hx-target='#status' "
                f"hx-swap='innerHTML' "
                f">"
                f"+</button></li>\n"
            )
        animations_html += f"<div><strong>Walks</strong><ul>{items_html}</ul></div>"

        items_html = ""
        for walk in status.animations.outros:
            items_html += f"<li>{walk}</li>\n"
        animations_html += f"<div><strong>Outros</strong><ul>{items_html}</ul></div>"
    else:
        animations_html = "<em>No animations</em>"

    status_message = status.message or ""

    return f"""
        <h3>System Status</h3>
        {status_message}
        <p><strong>Playing:</strong> {'🟢 Yes' if status.playing else '🔴 No'}</p>
        <p><strong>Controller time:</strong> {status.timestamp.strftime("%d/%m/%Y %H:%M:%S")} (as of last status request) </p>
        <p><strong>Walk queue:</strong> {[w for w in status.walk_queue]} </p>
        <p><strong>Components:</strong></p>
        <ul>
            {components_html}
        </ul>
        <p><strong>Animations:</strong></p>
        {animations_html}
    """


def render_alert_html(message: str, success: bool = True) -> str:
    color = "#d4edda" if success else "#f8d7da"
    border = "#155724" if success else "#721c24"
    return f"""
        <div style="background:{color};border:1px solid {border};padding:10px;margin-bottom:10px;">
            {message}
        </div>
    """


@app.get("/", response_class=HTMLResponse)
async def root():
    status = api_controller.get_status()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Crosswalk V2 Control Panel</title>
        <script src="/static/htmx.min.js"></script>

        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            button {{ padding: 10px 20px; margin: 10px; font-size: 16px; }}
            #status {{ background: #f0f0f0; padding: 20px; margin: 20px 0; }}
            .button-group {{ margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>🚦 Crosswalk V2 Control Panel</h1>
        
        <div id="alert-area"></div>
        
        <div class="button-group">
            <h3>Actions</h3>
            <button 
                hx-post="/button" 
                hx-target="#status" 
                hx-swap="innerHTML"
            >🔘 Press Button</button>
            <button 
                hx-post="/timer" 
                hx-target="#status" 
                hx-swap="innerHTML"
            >⏰ Timer Expired</button>
        </div>
        
        <div class="button-group">
            <button type="button" 
                hx-get="/status" 
                hx-target="#status" 
                hx-swap="innerHTML"
                >📊 Refresh Status</button>
        </div>
        
        <div id="status">
            {render_status_html(status)}
        </div>
        
    </body>
    </html>
    """


@app.get("/status", response_class=HTMLResponse)
async def status():
    """Return status as HTML fragment for htmx"""
    status = api_controller.get_status()
    return render_status_html(status)


@app.post("/button", response_class=HTMLResponse)
async def press_button():
    """Handle button press action (htmx or API)"""
    status = api_controller.press_button()
    return render_status_html(status)

@app.post("/queue/{walk}", response_class=HTMLResponse)
async def queue(walk: str):
    """Handle button press action (htmx or API)"""
    result = api_controller.queue_walk(walk)
    return render_status_html(result)

@app.post("/timer", response_class=HTMLResponse)
async def fire_timer():
    """Handle timer expired action (htmx or API)"""
    result = api_controller.timer_expired()
    return render_status_html(result)



if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Crosswalk V2 API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
