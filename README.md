# Crosswalk V2

The Python-based control system for managing Crosswalk, an interactive art project that mimics a real push-button-to-cross crosswalk, but that tells you to do much more than walk. It uses ZMQ for communication and runs animations on LED matrix displays.

## Requirements

- Python 3.13 or higher
- pyzmq >= 26.4.0
- pydantic >= 2.0.0

## Installation

### The Normal Way

1. https://docs.astral.sh/uv/getting-started/installation/ (a Python package and project manager):
2. Create and activate a virtual environment:
   ```bash
   uv venv
   source .venv/bin/activate  # On Unix/macOS
   # or
   .venv\Scripts\activate  # On Windows
   ```
3. Install dependencies:
   ```bash
   uv pip install -e .
   ```

### The Nix Way

To get started:

1. Install [Nix](https://nixos.org/download.html) if you haven't already
2. Run the following command in the project directory:
   ```bash
   nix develop
   ```
   This will drop you into a development shell with all dependencies installed.

## Running the Program

After installation, make sure you're in the project root directory and run the controller:

```bash
python xwalk2/controller.py
```

You should see output similar to this:
```
Starting Crosswalk V2 Controller...
Initializing ZMQ sockets...
ZMQ sockets initialized successfully
Listening on ports:
  - 5556: Interactions
  - 5557: Control
  - 5558: Heartbeats

Controller is running. Press Ctrl+C to exit.
Waiting for components to connect...
```

To stop the program, press Ctrl+C.

## Project Structure

- `xwalk2/` - Main package directory
  - `animation.py` - Animation system implementation
  - `button_lights.py` - Button lighting control
  - `button_switch.py` - Button switch handling
  - `controller.py` - Main controller logic
  - `matrix_driver.py` - Matrix display driver
  - `models.py` - Data models
  - `timer.py` - Timing utilities
  - `util.py` - Utility functions

## Development

The project uses modern Python tooling:
- `pyproject.toml` for project configuration and dependencies
- `flake.nix` for Nix development environment
- `uv.lock` for dependency locking