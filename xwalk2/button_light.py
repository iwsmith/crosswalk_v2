import logging

from gpiozero import LED
from pydantic import BaseModel

from xwalk2.models import CurrentState, EndScene, PlayScene
from xwalk2.util import SubscribeComponent, add_default_args

logger = logging.getLogger(__name__)


class ButtonLight(SubscribeComponent):
    def __init__(
        self,
        component_name: str,
        host_name: str,
        subscribe_address,
        heartbeat_address,
    ) -> None:
        super().__init__(
            component_name, host_name, subscribe_address, heartbeat_address
        )
        self.led = LED(24)

        self.led.off()

    def process_message(self, message: BaseModel):
        if isinstance(message, PlayScene):
            self.led.off()
        elif isinstance(message, EndScene):
            self.led.on()
        elif isinstance(message, CurrentState):
            if message.state == "walk":
                self.led.off()
            elif message.state == "ready":
                self.led.on()
            else:
                print(f"Unknown State {message=}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    add_default_args(parser)
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    component = ButtonLight(
        "button_led", args.hostname, args.controller, args.heartbeat
    )
    component.run()
