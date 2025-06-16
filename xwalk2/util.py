import threading
from pathlib import Path
import time
from datetime import datetime
from typing import Dict, List, Optional

import zmq
from pydantic import BaseModel

from xwalk2.models import Heatbeat, parse_message


class Heartbeat:
    def __init__(self, component: str, host: str, every_s: int = 1):
        self.component = component
        self.host = host
        self.every_s = every_s
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self._started = False

    def _beat(self):
        context = zmq.Context.instance()
        socket = context.socket(zmq.PUB)
        socket.connect("tcp://127.0.0.1:5558")  # TODO: make configurable

        try:
            while not self.stop_event.is_set():
                msg = Heatbeat(
                    host=self.host, component=self.component, sent_at=datetime.now()
                ).model_dump_json()
                socket.send_string(msg)
                time.sleep(self.every_s)
        finally:
            socket.close(0)
            # Do not call context.term() — it's global

    def start(self):
        if self._started:
            print("Trying to start already started heartbeat!")
            return  # prevent starting twice
        self.thread = threading.Thread(target=self._beat)
        self.thread.daemon = False
        self.thread.start()
        self._started = True

    def stop(self):
        if self._started:
            self.stop_event.set()
            if self.thread:
                self.thread.join(0)
            self._started = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class SubscribeComponent:
    def __init__(
        self,
        component_name: str,
        host_name: str,
        subscribe_address="tcp://127.0.0.1:5557",
    ) -> None:
        self.component_name = component_name
        self.host_name = host_name
        self.subscribe_address = subscribe_address

    def process_message(self, message: BaseModel):
        raise NotImplementedError()

    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(self.subscribe_address)
        socket.setsockopt_string(zmq.SUBSCRIBE, "")

        with Heartbeat(self.component_name, self.host_name):
            try:
                while True:
                    msg = socket.recv_string()
                    message = parse_message(msg)
                    self.process_message(message)
            except KeyboardInterrupt:
                print(f"\nShutting down {self.component_name}")
            finally:
                socket.close(0)
                context.term()


class InteractComponent:
    def __init__(
        self,
        component_name: str,
        host_name: str,
        interact_address="tcp://127.0.0.1:5556",
    ) -> None:
        self.component_name = component_name
        self.host_name = host_name
        self.interact_address = interact_address

    def loop(self):
        raise NotImplementedError()

    def send_action(self, action: BaseModel):
        self.socket.send_string(action.model_dump_json())

    def run(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.PUB)
        self.socket.connect(self.interact_address)

        with Heartbeat(self.component_name, self.host_name):
            try:
                self.loop()
            except KeyboardInterrupt:
                print(f"\nShutting down {self.component_name}")
            finally:
                self.socket.close(1)
                context.term()


class SubscribeInteractComponent:
    def __init__(
        self,
        component_name: str,
        host_name: str,
        interact_address="tcp://127.0.0.1:5556",
        subscribe_address="tcp://127.0.0.1:5557",
    ) -> None:
        self.component_name = component_name
        self.host_name = host_name
        self.interact_address = interact_address
        self.subscribe_address = subscribe_address

    def process_message(self, message: BaseModel):
        raise NotImplementedError()

    def run(self):
        context = zmq.Context()

        self.interact_socket = context.socket(zmq.PUB)
        self.interact_socket.connect(self.interact_address)

        subscribe_socket = context.socket(zmq.SUB)
        subscribe_socket.connect(self.subscribe_address)
        subscribe_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        with Heartbeat(self.component_name, self.host_name):
            try:
                while True:
                    msg = subscribe_socket.recv_string()
                    message = parse_message(msg)
                    self.process_message(message)
            except KeyboardInterrupt:
                print(f"\nShutting down {self.component_name}")
            finally:
                subscribe_socket.close(0)
                self.interact_socket.close(0)
                context.term()

class FileLibrary:
    def __init__(self, root_dir: str, extensions: Optional[List[str]] = None):
        """
        :param root_dir: The root directory to walk.
        :param extensions: List of file extensions to include (e.g., ['.txt', '.py']).
                           If None, includes all files.
        """
        self.root_path = Path(root_dir).resolve()
        self.extensions = {ext.lower() for ext in extensions} if extensions else None
        self.file_map = self.build_map()

    def build_map(self) -> Dict[str, Path]:
        """
        Recursively walks the directory and maps filenames (without extension) to absolute paths.

        :return: Dictionary mapping filename (no extension) to absolute Path objects.
        """
        file_map: dict[str, Path] = {}
        for path in self.root_path.rglob('*'):
            if path.is_file():
                if self.extensions and path.suffix.lower() not in self.extensions:
                    continue
                name_without_ext = path.stem
                if name_without_ext in file_map:
                    raise ValueError(f"Entry {name_without_ext} already exists! {path} and {file_map[name_without_ext]}")
                file_map[name_without_ext] = path.resolve()
        return file_map

    def __getitem__(self, key) -> Path:
        return self.file_map[key]

class ImageLibrary(FileLibrary):
    def __init__(self, root_dir: str, extensions: List[str] | None = None):
        if not extensions:
            extensions = [".gif"]
        super().__init__(root_dir, extensions)

class AudioLibrary(FileLibrary):
    def __init__(self, root_dir: str, extensions: List[str] | None = None):
        if not extensions:
            extensions = ['.mp3', '.m4a', '.wav']
        super().__init__(root_dir, extensions)

