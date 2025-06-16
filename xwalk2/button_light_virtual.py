from pydantic import BaseModel

from xwalk2.models import CurrentState, EndScene, PlayScene
from xwalk2.util import SubscribeComponent


class VirtualLED:
    def __init__(self) -> None:
        self.light = "off"

    def on(self):
        self.light = "on"
        print(f"{self.light=}")

    def off(self):
        self.light = "off"
        print(f"{self.light=}")


class ButtonLight(SubscribeComponent):
    def __init__(
        self,
        component_name: str,
        host_name: str,
        subscribe_address="tcp://127.0.0.1:5557",
    ) -> None:
        super().__init__(component_name, host_name, subscribe_address)
        self.led = VirtualLED()

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
                print(f"Unknown state {message=}")


if __name__ == "__main__":
    component = ButtonLight("button_led_virtual", "crosswalk-a")
    component.run()
