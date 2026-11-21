import ctypes
from threading import Thread as thread


class breakPopup:
    def __init__(self):
        self.shown = False
        self.dialog = None

    def update(self, fatigueScore: float) -> bool:
        if fatigueScore <= 60:
            self.shown = False
            return False

        if self.shown or (self.dialog is not None and self.dialog.is_alive()):
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
        self.shown = True
        return True