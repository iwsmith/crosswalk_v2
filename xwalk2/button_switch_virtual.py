import time
from datetime import datetime

from xwalk2.models import ButtonPress
from xwalk2.util import InteractComponent


class VirtualButton(InteractComponent):
    def __init__(
        self,
        component_name: str,
        host_name: str,
        interact_address="tcp://127.0.0.1:5556",
    ) -> None:
        super().__init__(component_name, host_name, interact_address)

    def loop(self):
        while True:
            input("Press enter to simulate button press down")
            print("Button pressed")
            press_start = time.time()

            input("Press enter to simulate button release")
            press_duration = int(
                (time.time() - press_start) * 1000
            )  # Convert to milliseconds
            print(f"Button released (held for {press_duration}ms)")

            button_press = ButtonPress(
                host=self.host_name,
                component=self.component_name,
                press_duration=press_duration,
                sent_at=datetime.now(),
            )
            self.send_action(button_press)


if __name__ == "__main__":
    button = VirtualButton("button_virtual", "crosswalk-a")
    button.run()
