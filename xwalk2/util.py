import os
from argparse import ArgumentParser
import threading
from pathlib import Path
import time
from datetime import datetime
from typing import Dict, List, Optional

import zmq
from pydantic import BaseModel

from xwalk2.models import Heatbeat, parse_message


class Heartbeat:
    def __init__(
        self,
        component: str,
        host: str,
        heartbeat_address,
        every_s: int = 1,
    ):
        self.component = component
        self.host = host
        self.every_s = every_s
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self._started = False
        self.heartbeat_address = heartbeat_address

    def _beat(self):
        context = zmq.Context.instance()
        socket = context.socket(zmq.PUB)
        socket.connect(self.heartbeat_address)
        initial = 0

        try:
            while not self.stop_event.is_set():
                msg = Heatbeat(
                    host=self.host, component=self.component, sent_at=datetime.now(), initial=(initial >= 2)
                ).model_dump_json()
                initial += 1
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
        subscribe_address: str,
        heartbeat_address: str,
    ) -> None:
        self.component_name = component_name
        self.host_name = host_name
        self.subscribe_address = subscribe_address
        self.heartbeat_address = heartbeat_address

    def process_message(self, message: BaseModel):
        raise NotImplementedError()

    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(self.subscribe_address)
        socket.setsockopt_string(zmq.SUBSCRIBE, "")

        with Heartbeat(
            self.component_name,
            self.host_name,
            heartbeat_address=self.heartbeat_address,
        ):
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
        interact_address: str,
        heartbeat_address: str,
    ) -> None:
        self.component_name = component_name
        self.host_name = host_name
        self.interact_address = interact_address
        self.heartbeat_address = heartbeat_address

    def loop(self):
        raise NotImplementedError()

    def send_action(self, action: BaseModel):
        self.socket.send_string(action.model_dump_json())

    def run(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.PUB)
        self.socket.connect(self.interact_address)

        with Heartbeat(self.component_name, self.host_name, self.heartbeat_address):
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
        interact_address,
        subscribe_address,
        heartbeat_address,
    ) -> None:
        self.component_name = component_name
        self.host_name = host_name
        self.interact_address = interact_address
        self.subscribe_address = subscribe_address
        self.heartbeat_address = heartbeat_address

    def process_message(self, message: BaseModel):
        raise NotImplementedError()

    def run(self):
        context = zmq.Context()

        self.interact_socket = context.socket(zmq.PUB)
        self.interact_socket.connect(self.interact_address)

        subscribe_socket = context.socket(zmq.SUB)
        subscribe_socket.connect(self.subscribe_address)
        subscribe_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        with Heartbeat(self.component_name, self.host_name, self.heartbeat_address):
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
        for path in self.root_path.rglob("*"):
            if path.is_file():
                if self.extensions and path.suffix.lower() not in self.extensions:
                    continue
                name_without_ext = path.stem
                if name_without_ext in file_map:
                    raise ValueError(
                        f"Entry {name_without_ext} already exists! {path} and {file_map[name_without_ext]}"
                    )
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
            extensions = [".mp3", ".m4a", ".wav"]
        super().__init__(root_dir, extensions)


def add_default_args(parser: ArgumentParser):
    parser.add_argument(
        "--interaction",
        type=str,
        default=os.getenv("XWALK_INTERACTION", "tcp://localhost:5556"),
    )
    parser.add_argument(
        "--controller",
        type=str,
        default=os.getenv("XWALK_CONTROLLER", "tcp://localhost:5557"),
    )
    parser.add_argument(
        "--heartbeat",
        type=str,
        default=os.getenv("XWALK_HEARTBEAT", "tcp://localhost:5558"),
    )
    parser.add_argument(
        "--hostname",
        type=str,
        default=os.getenv("XWALK_HOSTNAME", "crosswalk-unknown"),
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )
