from xwalk2.models import PlayScene, EndScene
from transitions import Machine

class Controller:
  states = ['ready','walk']
  def __init__(self):
    self.machine = Machine(model=self, states=Controller.states, initial='ready', ignore_invalid_triggers=True)
    self.machine.add_transition('button_press', source='ready', dest='walk')
    self.machine.add_transition('reset', source='*', dest='ready')

  def on_enter_walk(self, send_fn):
    # We would choose a walk here
    send_fn(PlayScene().model_dump_json())

  def on_enter_reset(self, send_fn):
    send_fn(EndScene().model_dump_json())
