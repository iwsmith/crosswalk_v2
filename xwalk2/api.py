import time
from contextlib import asynccontextmanager
from typing import Dict

import zmq
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from xwalk2.models import APIRequest, APIResponse, Animations


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

    def _send_request(self, request: APIRequest) -> APIResponse:
        if not self.api_socket:
            raise RuntimeError("API Controller not initialized")
        try:
            self.api_socket.send_string(request.model_dump_json())
            if self.api_socket.poll(timeout=5000):
                response_data = self.api_socket.recv_string()
                response = APIResponse.model_validate_json(response_data)
                if not response.success:
                    raise RuntimeError(response.message or "Request failed")
                return response
            else:
                raise TimeoutError("Controller did not respond within timeout")
        except zmq.ZMQError as e:
            print(f"ZMQ communication error: {e}")
            raise ConnectionError("Failed to communicate with controller")

    def send_action(self, action: str) -> str:
        request = APIRequest(request_type="action", action=action)
        response = self._send_request(request)
        print(f"Action '{action}' result: {response.message}")
        return response.message or "Action completed"

    def send_reset(self) -> str:
        request = APIRequest(request_type="reset")
        response = self._send_request(request)
        return response.message or "Reset completed"

    def get_status(self) -> SystemStatus:
        request = APIRequest(request_type="status")
        response = self._send_request(request)
        components_timestamps = {}
        if response.components:
            for component, dt in response.components.items():
                if hasattr(dt, "timestamp"):
                    components_timestamps[component] = dt.timestamp()
                else:
                    components_timestamps[component] = time.time()
        return SystemStatus(
            playing=response.playing or False,
            components=components_timestamps,
            uptime=time.time() - self.start_time,
            animations=response.animations
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


def render_status_html(status: SystemStatus) -> str:
    components_html = "".join(
        f"<li><strong>{name}</strong>: Last seen {int(time.time() - timestamp)}s ago</li>"
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
            items_html += f"<li>{walk} - {info.category}</li>\n"
        animations_html += f"<div><strong>Walks</strong><ul>{items_html}</ul></div>"

        items_html = ""
        for walk in status.animations.outros:
            items_html += f"<li>{walk}</li>\n"
        animations_html += f"<div><strong>Outros</strong><ul>{items_html}</ul></div>"
    else:
        animations_html = "<em>No animations</em>"

    return f"""
        <h3>System Status</h3>
        <p><strong>Playing:</strong> {'🟢 Yes' if status.playing else '🔴 No'}</p>
        <p><strong>Uptime:</strong> {int(status.uptime)} seconds</p>
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
            .status {{ background: #f0f0f0; padding: 20px; margin: 20px 0; }}
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
                hx-target="#alert-area"
                hx-swap="beforeend"
                hx-on="htmx:afterRequest: document.getElementById('status').dispatchEvent(new Event('refresh'))"
            >🔘 Press Button</button>
            <button 
                hx-post="/timer" 
                hx-target="#alert-area"
                hx-swap="beforeend"
                hx-on="htmx:afterRequest: document.getElementById('status').dispatchEvent(new Event('refresh'))"
            >⏰ Timer Expired</button>
            <button 
                hx-post="/reset" 
                hx-target="#alert-area"
                hx-swap="beforeend"
                hx-on="htmx:afterRequest: document.getElementById('status').dispatchEvent(new Event('refresh'))"
            >🔄 Reset</button>
        </div>
        
        <div class="button-group">
            <button 
                hx-get="/status_html" 
                hx-target="#status"
                hx-swap="outerHTML"
            >📊 Refresh Status</button>
            <button 
                hx-post="/reset"
                hx-target="#alert-area"
                hx-swap="beforeend"
                hx-on="htmx:afterRequest: document.getElementById('status').dispatchEvent(new Event('refresh'))"
            >🔄 Reset System</button>
        </div>
        
        <div class="status" id="status">
            {render_status_html(status)}
        </div>
        
        <script>
            document.getElementById('status').addEventListener('refresh', function() {{
                htmx.ajax('GET', '/status_html', '#status');
            }});
        </script>
    </body>
    </html>
    """


@app.get("/status_html", response_class=HTMLResponse)
async def status_html():
    """Return status as HTML fragment for htmx"""
    try:
        status = api_controller.get_status()
        return f'<div class="status" id="status">{render_status_html(status)}</div>'
    except Exception as e:
        return f'<div class="status" id="status"><span style="color:red;">Failed to get status: {e}</span></div>'


@app.get("/status", response_model=SystemStatus)
async def get_status():
    """Get system status from controller (JSON, for API use)"""
    try:
        return api_controller.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")


@app.post("/button", response_class=HTMLResponse)
async def press_button():
    """Handle button press action (htmx or API)"""
    try:
        result = api_controller.send_action("button_pressed")
        return render_alert_html(f"Button pressed: {result}", success=True)
    except Exception as e:
        return render_alert_html(f"Button press failed: {e}", success=False)


@app.post("/timer", response_class=HTMLResponse)
async def fire_timer():
    """Handle timer expired action (htmx or API)"""
    try:
        result = api_controller.send_action("timer_expired")
        return render_alert_html(f"Timer expired: {result}", success=True)
    except Exception as e:
        return render_alert_html(f"Timer action failed: {e}", success=False)


@app.post("/reset", response_class=HTMLResponse)
async def reset_system():
    """System reset action (htmx or API)"""
    try:
        result = api_controller.send_reset()
        return render_alert_html(f"Reset result: {result}", success=True)
    except Exception as e:
        return render_alert_html(f"Reset failed: {e}", success=False)


@app.post("/trigger", response_class=HTMLResponse)
async def trigger_action(request: Request):
    """Trigger an action through the controller (API use only)"""
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
        action = data.get("action")
    else:
        form = await request.form()
        action = form.get("action")
    try:
        result = api_controller.send_action(action)
        return render_alert_html(f"Action result: {result}", success=True)
    except Exception as e:
        return render_alert_html(f"Action failed: {e}", success=False)


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Crosswalk V2 API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
