import logging
import subprocess

from pydantic import BaseModel

from xwalk2.models import SysCommand
from xwalk2.util import SubscribeComponent, add_default_args

logger = logging.getLogger(__name__)

# Root-owned helper (installed via ansible) with a narrow NOPASSWD sudoers rule.
CTL_CMD = "/usr/local/bin/crosswalk-ctl"


class SysControl(SubscribeComponent):
    """Executes system-control commands (restart services, reboot, set clock)
    for its own host.

    Commands arrive on the control channel as SysCommands; each agent acts only
    on those targeting "all" or its own hostname. Privileged actions run through
    the root-owned crosswalk-ctl helper, so no SSH between boxes is required.
    """

    def _run(self, *args: str) -> None:
        cmd = ["sudo", "-n", CTL_CMD, *args]
        logger.info("Running %s", cmd)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=25)
        except subprocess.CalledProcessError as e:
            logger.error("crosswalk-ctl failed: %s", (e.stderr or "").strip() or e)
        except Exception:
            logger.exception("Failed to run crosswalk-ctl %s", args)

    def process_message(self, message: BaseModel):
        if not isinstance(message, SysCommand):
            return
        if message.target not in ("all", self.host_name):
            return

        logger.info("Handling %s (target=%s)", message.action, message.target)
        if message.action == "restart" and message.unit:
            self._run("restart", message.unit)
        elif message.action == "restart_all":
            self._run("restart-all")
        elif message.action == "reboot":
            self._run("reboot")
        elif message.action == "set_clock" and message.epoch is not None:
            self._run("set-clock", f"{message.epoch:.3f}")
        else:
            logger.warning("Ignoring malformed SysCommand: %s", message)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    add_default_args(parser)
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    component = SysControl(
        "sys-control", args.hostname, args.controller, args.heartbeat
    )
    component.run()
