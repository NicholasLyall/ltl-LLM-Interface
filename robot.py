"""
SimBridge — manages the sim_worker subprocess.
  stdout → binary frames (read by _FrameThread)
  stderr → text messages (read by _MsgThread)
  stdin  → commands
"""

import os
import sys
import struct
import subprocess
import numpy as np

from PyQt5.QtCore import QObject, QThread, pyqtSignal

CAM_W, CAM_H = 640, 480
MAGIC = b'FRAM'


class _FrameThread(QThread):
    frame_ready = pyqtSignal(object)

    def __init__(self, stdout, parent=None):
        super().__init__(parent)
        self._stdout = stdout

    def run(self):
        buf = b""
        while True:
            chunk = self._stdout.read(65536)
            if not chunk:
                break
            buf += chunk
            while len(buf) >= 8 and buf[:4] == MAGIC:
                length = struct.unpack('<I', buf[4:8])[0]
                if len(buf) < 8 + length:
                    break
                raw   = buf[8: 8 + length]
                buf   = buf[8 + length:]
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(CAM_H, CAM_W, 3)
                self.frame_ready.emit(frame.copy())


class _MsgThread(QThread):
    msg_received = pyqtSignal(str)

    def __init__(self, stderr, parent=None):
        super().__init__(parent)
        self._stderr = stderr

    def run(self):
        for line in self._stderr:
            line = line.decode(errors="ignore").strip()
            if line:
                print(f"[worker] {line}", flush=True)
                self.msg_received.emit(line)


class SimBridge(QObject):
    frame_ready   = pyqtSignal(object)
    exec_progress = pyqtSignal(int, str)
    exec_done     = pyqtSignal()
    exec_error    = pyqtSignal(str)
    ready         = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc        = None
        self._frame_thread = None
        self._msg_thread   = None

    def start_sim(self):
        python = sys.executable
        script = os.path.join(os.path.dirname(__file__), "sim_worker.py")
        self._proc = subprocess.Popen(
            [python, "-u", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(__file__),
        )
        self._frame_thread = _FrameThread(self._proc.stdout)
        self._frame_thread.frame_ready.connect(self.frame_ready)
        self._frame_thread.start()

        self._msg_thread = _MsgThread(self._proc.stderr)
        self._msg_thread.msg_received.connect(self._on_msg)
        self._msg_thread.start()

    def request_execute(self, plan: list):
        if self._proc and self._proc.poll() is None:
            cmd = "EXEC " + " ".join(plan) + "\n"
            self._proc.stdin.write(cmd.encode())
            self._proc.stdin.flush()

    def stop(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.write(b"QUIT\n")
                self._proc.stdin.flush()
            except Exception:
                pass
            self._proc.terminate()
        for t in (self._frame_thread, self._msg_thread):
            if t:
                t.wait(2000)

    def _on_msg(self, line: str):
        if line == "READY":
            self.ready.emit()
        elif line in ("SIMULATING", "PLAYING"):
            pass  # informational only
        elif line.startswith("PROGRESS "):
            parts = line.split()
            if len(parts) == 3:
                self.exec_progress.emit(int(parts[1]), parts[2])
        elif line == "DONE":
            self.exec_done.emit()
        elif line.startswith("ERROR "):
            self.exec_error.emit(line[6:])
