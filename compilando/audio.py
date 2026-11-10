import numpy as np
from PyQt5.QtCore import QIODevice
from .core import RATE

class MixerDevice(QIODevice):
    """Pull-mode PCM source. Editing is paused while playback is active."""
    def __init__(self, project, frame, parent=None):
        super().__init__(parent)
        self.project, self.frame = project, frame

    def isSequential(self):
        return True

    def bytesAvailable(self):
        return max(0, self.project.frames - self.frame) * 4 + super().bytesAvailable()

    def atEnd(self):
        return self.frame >= self.project.frames

    def readData(self, maximum):
        count = min(maximum // 4, self.project.frames - self.frame)
        if count <= 0:
            return bytes()
        block = self.project.render(self.frame, count)
        self.frame += count
        return (np.clip(block, -1, 1) * 32767).astype('<i2').tobytes()

    def writeData(self, data):
        return -1
