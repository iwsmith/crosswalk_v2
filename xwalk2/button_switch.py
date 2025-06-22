import logging
import os
import time
from datetime import datetime
from signal import pause

from gpiozero import Button

from xwalk2.models import ButtonPress
from xwalk2.util import InteractComponent, add_default_args

logger = logging.getLogger(__name__)



class PhysicalButton(InteractComponent):
    def __init__(
        self,
        component_name: str,
        host_name: str,
        interact_address: str,
        heartbeat_address: str,
    ) -> None:
        super().__init__(component_name, host_name, interact_address, heartbeat_address)
        self.button_pin = int(os.getenv("XWALK_BUTTON_PIN", 25))
        self.button = Button(self.button_pin, pull_up=True, bounce_time=0.05)
        self._press_time = None

        self.button.when_pressed = self._handle_press
        self.button.when_released = self._handle_release

        logger.info(f"Initialized button with pin {self.button_pin}")

    def _handle_press(self):
        self._press_time = time.time()

    def _handle_release(self):
        if self._press_time is None:
            return
        d = int((time.time() - self._press_time) * 1000)  # duration in ms
        self._press_time = None

        button_press = ButtonPress(
            host=self.host_name,
            component=self.component_name,
            press_duration=d,
            sent_at=datetime.now(),
        )
        self.send_action(button_press)

    def loop(self):
        # Block main thread to keep callbacks active
        pause()


# class PhysicalButton(InteractComponent):
#     def __init__(
#         self,
#         component_name: str,
#         host_name: str,
#         interact_address: str,
#         heartbeat_address: str,
#     ) -> None:
#         super().__init__(component_name, host_name, interact_address, heartbeat_address)
#         self.button_pin = int(os.getenv("XWALK_BUTTON_PIN", 25))
#         self.button = Button(self.button_pin, pull_up=True, bounce_time=0.05)
#         logger.info(f"Initialized button with pin {self.button_pin}")

#     def loop(self):
#         while True:
#             self.button.wait_for_press()
#             s = time.time()
#             self.button.wait_for_release()
#             d = int(time.time() - s) * 1000  # convert S -> MS
#             button_press = ButtonPress(
#                 host=self.host_name,
#                 component=self.component_name,
#                 press_duration=d,
#                 sent_at=datetime.now(),
#             )
#             self.send_action(button_press)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    add_default_args(parser)
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    button = PhysicalButton(
        "button_physical", args.hostname, args.interaction, args.heartbeat
    )
    button.run()
