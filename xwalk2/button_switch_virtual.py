import argparse
import logging
import time
from datetime import datetime

from xwalk2.models import ButtonPress
from xwalk2.util import InteractComponent, add_default_args

logger = logging.getLogger(__name__)


class VirtualButton(InteractComponent):
    def __init__(
        self,
        component_name: str,
        host_name: str,
        interact_address: str,
        heartbeat_address: str,
    ) -> None:
        super().__init__(component_name, host_name, interact_address, heartbeat_address)
        logger.info("Initialized virtual button")

    def loop(self):
        while True:
            input("Press enter to simulate button press down")
            logging.info("Button pressed")
            press_start = time.time()

            input("Press enter to simulate button release")
            press_duration = int(
                (time.time() - press_start) * 1000
            )  # Convert to milliseconds

            button_press = ButtonPress(
                host=self.host_name,
                component=self.component_name,
                press_duration=press_duration,
                sent_at=datetime.now(),
            )
            logging.info(f"button press duration={press_duration}ms")
            self.send_action(button_press)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_default_args(parser)
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    button = VirtualButton(
        "button_virtual", args.hostname, args.interaction, args.heartbeat
    )
    button.run()
