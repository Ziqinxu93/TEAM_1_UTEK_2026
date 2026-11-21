import ctypes
from threading import Thread as thread
from time import monotonic as clock


class breakPopup:
    def __init__(self):
        self.lastShown = None
        self.dialog = None

    def update(self, fatigueScore: float, resting: bool = False) -> bool:
        if resting:
            self.lastShown = None
            return False

        now = clock()
        if self.lastShown is None:
            if fatigueScore <= 60:
                return False
        elif now - self.lastShown < 600:
            return False

        if self.dialog is not None and self.dialog.is_alive():
            self.lastShown = now
            return False

        self.dialog = thread(
            target=ctypes.windll.user32.MessageBoxW,
            args=(
                None,
                "You might be tired, what about take a sip",
                0x00040040,
            ),
            daemon=True,
        )
        self.dialog.start()
        self.lastShown = now
        return True
