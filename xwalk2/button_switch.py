import sys
import time
from datetime import datetime

import os
import zmq
from gpiozero import LED, Button

from xwalk2.models import ButtonPress
from xwalk2.util import heatbeat


# button_switch can run in console mode or physical mode.
# python xwalk2/button_switch.py -m console
# python xwalk2/button_switch.py -m physical
def main(mode):
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.connect("tcp://127.0.0.1:5556")
    t = heatbeat("button_switch", "crosswalk-a")

    if mode == "console":
        try:
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
                    host="crosswalk-a",
                    component="button_switch",
                    press_duration=press_duration,
                    sent_at=datetime.now(),
                )
                socket.send_string(button_press.model_dump_json())
        except KeyboardInterrupt:
            print("\nShutting down...")
            t.stop() 
            socket.close()
            context.term()
            sys.exit(0)
    else:
        button_pin = int(os.getenv('XWALK_BUTTON_PIN', 25))
        button = Button(button_pin, pull_up=True, bounce_time=0.05)
        try:
            while True:
                button.wait_for_press()
                s = time.time()
                button.wait_for_release()
                d = int(time.time() - s)
                button_press = ButtonPress(host="crosswalk-a", component="button_switch", press_duration=d, sent_at=datetime.now())
                print(button_press)
                socket.send_string(button_press.model_dump_json())
        except KeyboardInterrupt:
            print("\nShutting down...")
            t.stop() 
            socket.close()
            context.term()
            sys.exit(0)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Button switch process")
    parser.add_argument(
        "-m",
        "--mode",
        choices=["console", "physical"],
        required=True,
        help="Mode of operation: console or physical",
    )
    args = parser.parse_args()

    print(f"Starting button switch in {args.mode} mode")
    main(args.mode)
