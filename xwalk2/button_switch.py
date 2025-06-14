import os
import sys
import time
from datetime import datetime

import zmq
from gpiozero import Button

from xwalk2.models import ButtonPress
from xwalk2.util import InteractComponent


class PhysicalButton(InteractComponent):
    def __init__(
        self,
        component_name: str,
        host_name: str,
        interact_address="tcp://127.0.0.1:5556",
    ) -> None:
        super().__init__(component_name, host_name, interact_address)
        self.button_pin = int(os.getenv("XWALK_BUTTON_PIN", 25))
        self.button = Button(self.button_pin, pull_up=True, bounce_time=0.05)

    def loop(self):
        while True:
            self.button.wait_for_press()
            s = time.time()
            self.button.wait_for_release()
            d = int(time.time() - s) * 1000 # convert S -> MS
            button_press = ButtonPress(
                host=self.host_name,
                component=self.component_name,
                press_duration=d,
                sent_at=datetime.now(),
            )
            self.send_action(button_press)


if __name__ == "__main__":
    button = PhysicalButton("button_physical", "crosswalk-a")
    button.run()
