import logging
import os
import time
from datetime import datetime
from signal import pause

import lgpio
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
        self._h = lgpio.gpiochip_open(0)  # assumes default chip 0
        self._press_time = None

        # Request falling and rising edge detection (press and release)
        lgpio.gpio_claim_input(self._h, self.button_pin)
        lgpio.gpio_set_debounce_micros(self._h, self.button_pin, 50)
        lgpio.gpio_set_alert_func(self._h, self.button_pin, self._callback)

        logger.info(f"Initialized button on pin {self.button_pin} using lgpio")

    def _callback(self, chip, gpio, level, tick):
        if level == 0:  # pressed
            self._press_time = time.time()
        elif level == 1 and self._press_time is not None:  # released
            d = int((time.time() - self._press_time) * 1000)
            self._press_time = None
            button_press = ButtonPress(
                host=self.host_name,
                component=self.component_name,
                press_duration=d,
                sent_at=datetime.now(),
            )
            self.send_action(button_press)

    def loop(self):
        # Wait forever without using CPU
        while True:
            time.sleep(3600)



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
