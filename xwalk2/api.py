import time
from contextlib import asynccontextmanager
from typing import Dict

import zmq
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from xwalk2.models import APIRequest, APIResponse


class ActionRequest(BaseModel):
    action: str


class SystemStatus(BaseModel):
    playing: bool
    components: Dict[str, float]  # Using float for timestamp
    uptime: float


class APIController:
    def __init__(self):
        self.context = zmq.Context()
        self.api_socket = None  # Single REQ socket for all communication
        self.start_time = time.time()

    def start(self):
        """Initialize ZMQ connection"""
        try:
            # Single REQ socket for all API communication
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
        """Send a request to the controller and return the response"""
        if not self.api_socket:
            raise RuntimeError("API Controller not initialized")

        try:
            # Send request
            self.api_socket.send_string(request.model_dump_json())

            # Wait for response with timeout
            if self.api_socket.poll(timeout=5000):  # 5 second timeout
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
        """Send an action to the controller"""
        request = APIRequest(request_type="action", action=action)

        response = self._send_request(request)
        print(f"Action '{action}' result: {response.message}")
        return response.message or "Action completed"

    def send_reset(self) -> str:
        """Send an action to the controller"""
        request = APIRequest(request_type="reset")

        response = self._send_request(request)
        return response.message or "Action completed"

    def get_status(self) -> SystemStatus:
        """Get current system status from controller"""
        request = APIRequest(request_type="status")

        response = self._send_request(request)

        # Convert datetime objects to timestamps
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
        )


# Global API controller instance
api_controller = APIController()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    api_controller.start()
    yield
    # Shutdown
    api_controller.stop()


app = FastAPI(
    title="Crosswalk V2 API",
    description="API for controlling the Crosswalk V2 system",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Simple web interface for testing"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Crosswalk V2 Control Panel</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            button { padding: 10px 20px; margin: 10px; font-size: 16px; }
            .status { background: #f0f0f0; padding: 20px; margin: 20px 0; }
            .button-group { margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>🚦 Crosswalk V2 Control Panel</h1>
        
        <div class="button-group">
            <h3>Actions</h3>
            <button onclick="triggerAction('A button pressed')">Press Button</button>
            <button onclick="triggerAction('A Timer fired')">Fire Timer</button>
        </div>
        
        <div class="button-group">
            <button onclick="getStatus()">Refresh Status</button>
        </div>

        <div class="button-group">
            <button onclick="reset()">Reset</button>
        </div>
        
        <div class="status" id="status">
            <h3>System Status</h3>
            <p>Click "Refresh Status" to load current status</p>
        </div>
        
        <script>
            async function triggerAction(action) {
                try {
                    const response = await fetch('/trigger', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({action: action})
                    });
                    const result = await response.json();
                    if (response.ok) {
                        alert('Action result: ' + result.message);
                        getStatus(); // Refresh status
                    } else {
                        alert('Error: ' + result.detail);
                    }
                } catch (error) {
                    alert('Network error: ' + error.message);
                }
            }

            async function reset() {
                try {
                    const response = await fetch('/reset', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                    });
                    const result = await response.json();
                    if (response.ok) {
                        alert('Action result: ' + result.message);
                        getStatus(); // Refresh status
                    } else {
                        alert('Error: ' + result.detail);
                    }
                } catch (error) {
                    alert('Network error: ' + error.message);
                }
            }

            async function getStatus() {
                try {
                    const response = await fetch('/status');
                    const status = await response.json();
                    document.getElementById('status').innerHTML = `
                        <h3>System Status</h3>
                        <p><strong>Playing:</strong> ${status.playing ? '🟢 Yes' : '🔴 No'}</p>
                        <p><strong>Uptime:</strong> ${Math.round(status.uptime)} seconds</p>
                        <p><strong>Components:</strong></p>
                        <ul>
                            ${Object.entries(status.components).map(([name, timestamp]) => 
                                `<li>${name}: Last seen ${Math.round(Date.now()/1000 - timestamp)}s ago</li>`
                            ).join('')}
                        </ul>
                    `;
                } catch (error) {
                    document.getElementById('status').innerHTML = 
                        '<p>Error loading status: ' + error.message + '</p>';
                }
            }
            
            // Auto-refresh status every 5 seconds
            setInterval(getStatus, 5000);
            getStatus(); // Initial load
        </script>
    </body>
    </html>
    """


@app.get("/status", response_model=SystemStatus)
async def get_status():
    """Get current system status"""
    return api_controller.get_status()


@app.post("/trigger")
async def trigger_action(request: ActionRequest):
    """Trigger an action in the controller"""
    try:
        message = api_controller.send_action(request.action)
        return {"message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/button")
async def press_button():
    """Trigger a button press"""
    try:
        message = api_controller.send_action("A button pressed")
        return {"message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/timer")
async def fire_timer():
    """Trigger a timer event"""
    try:
        message = api_controller.send_action("A Timer fired")
        return {"message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset")
async def reset_system():
    """Reset the system"""
    try:
        message = api_controller.send_reset()  # Timer fired triggers reset
        return {"message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
