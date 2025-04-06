from microapi.event import Event


class CronEvent(Event):
    def __init__(self):
        super().__init__()
        self.actions = []
