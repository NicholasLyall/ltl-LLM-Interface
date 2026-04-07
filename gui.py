"""
Main GUI — PyQt5
Layout matches the reference image:
  Left  : chat panel (bubbles + input)
  Right : embedded sim view (top) + plan boxes + LTL formula (bottom)
"""

import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QScrollArea, QLineEdit, QPushButton, QSizePolicy, QFrame,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QImage

# ── Colour palette ───────────────────────────────────────────────────────────
BG       = "#C2D9E8"
BUBBLE_BG= "#FFFFFF"
PLAN_BOX = "#7B9EBA"
LTL_BOX  = "#7B9EBA"
TEAL     = "#4A9DC0"
SIM_BG   = "#1C2333"

FONT     = "Segoe UI"


# ── LLM worker ───────────────────────────────────────────────────────────────

class LLMWorker(QThread):
    finished = pyqtSignal(str, list, str)   # display, plan, ltl
    error    = pyqtSignal(str)

    def __init__(self, message):
        super().__init__()
        self.message = message

    def run(self):
        try:
            from planner import send_message
            text, plan, ltl = send_message(self.message)
            self.finished.emit(text, plan, ltl)
        except Exception as e:
            self.error.emit(str(e))


# ── Chat bubble ──────────────────────────────────────────────────────────────

class ChatBubble(QWidget):
    def __init__(self, text, is_user, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 8, 3)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setMaximumWidth(340)
        label.setFont(QFont(FONT, 13))
        label.setStyleSheet("""
            QLabel {
                background-color: white;
                border-radius: 14px;
                padding: 10px 14px;
                color: #222;
            }
        """)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        avatar = QLabel("👤" if is_user else "🤖")
        avatar.setFont(QFont(FONT, 18))
        avatar.setFixedWidth(32)

        if is_user:
            row.addStretch()
            row.addWidget(label)
            row.addWidget(avatar)
        else:
            row.addWidget(avatar)
            row.addWidget(label)
            row.addStretch()


# ── Chat panel ───────────────────────────────────────────────────────────────

class ChatPanel(QWidget):
    plan_updated = pyqtSignal(list, str)   # plan, ltl

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setAlignment(Qt.AlignTop)
        self._msg_layout.setSpacing(6)
        self._msg_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(self._msg_container)
        root.addWidget(self._scroll)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type instruction or correction…")
        self._input.setFont(QFont(FONT, 13))
        self._input.setStyleSheet("""
            QLineEdit {
                border-radius: 18px;
                padding: 8px 16px;
                background: white;
                border: none;
                color: #222;
            }
        """)
        self._input.returnPressed.connect(self._send)

        self._btn = QPushButton("Send")
        self._btn.setFont(QFont(FONT, 13, QFont.Bold))
        self._btn.setFixedHeight(38)
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TEAL};
                color: white;
                border-radius: 16px;
                padding: 0 18px;
                border: none;
            }}
            QPushButton:hover    {{ background-color: #3A8CB0; }}
            QPushButton:disabled {{ background-color: #9BB8C8; }}
        """)
        self._btn.clicked.connect(self._send)

        input_row.addWidget(self._input)
        input_row.addWidget(self._btn)
        root.addLayout(input_row)

        self._worker = None

    def add_bubble(self, text, is_user):
        self._msg_layout.addWidget(ChatBubble(text, is_user))
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._set_enabled(False)
        self.add_bubble(text, is_user=True)

        self._worker = LLMWorker(text)
        self._worker.finished.connect(self._on_response)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_response(self, display, plan, ltl):
        self.add_bubble(display, is_user=False)
        self._set_enabled(True)
        if plan:
            self.plan_updated.emit(plan, ltl)

    def _on_error(self, err):
        self.add_bubble(f"Error: {err}", is_user=False)
        self._set_enabled(True)

    def _set_enabled(self, enabled):
        self._input.setEnabled(enabled)
        self._btn.setEnabled(enabled)


# ── Right panel ──────────────────────────────────────────────────────────────

class RightPanel(QWidget):
    def __init__(self, sim, parent=None):
        super().__init__(parent)
        self._sim = sim
        self.setStyleSheet(f"background-color: {BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ── Simulation view ──────────────────────────────────────────────────
        self._sim_view = QLabel("Starting simulation…")
        self._sim_view.setAlignment(Qt.AlignCenter)
        self._sim_view.setFont(QFont(FONT, 13))
        self._sim_view.setStyleSheet(f"""
            QLabel {{
                background-color: {SIM_BG};
                color: #88AACC;
                border-radius: 10px;
            }}
        """)
        self._sim_view.setMinimumHeight(300)
        self._sim_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self._sim_view)

        # Hook up sim frames
        self._sim.frame_ready.connect(self._on_frame)
        self._sim.exec_progress.connect(self._on_progress)
        self._sim.exec_done.connect(self._on_exec_done)
        self._sim.exec_error.connect(self._on_exec_error)
        self._sim.ready.connect(lambda: self._sim_view.setText(""))

        # ── Plan boxes ───────────────────────────────────────────────────────
        plan_label = QLabel("Current task plan sequences")
        plan_label.setFont(QFont(FONT, 13, QFont.Bold))
        plan_label.setStyleSheet(f"color: {TEAL}; background: transparent;")
        root.addWidget(plan_label)

        self._boxes_row = QHBoxLayout()
        self._boxes_row.setAlignment(Qt.AlignLeft)
        self._boxes_row.setSpacing(8)
        boxes_container = QWidget()
        boxes_container.setStyleSheet("background: transparent;")
        boxes_container.setLayout(self._boxes_row)
        root.addWidget(boxes_container)

        # ── LTL ─────────────────────────────────────────────────────────────
        ltl_label = QLabel("LTL Formulations")
        ltl_label.setFont(QFont(FONT, 13, QFont.Bold))
        ltl_label.setStyleSheet(f"color: {TEAL}; background: transparent;")
        root.addWidget(ltl_label)

        self._ltl = QLabel("")
        self._ltl.setWordWrap(True)
        self._ltl.setFont(QFont(FONT, 12))
        self._ltl.setStyleSheet(f"""
            QLabel {{
                background-color: {LTL_BOX};
                color: white;
                border-radius: 8px;
                padding: 12px 14px;
            }}
        """)
        self._ltl.setMinimumHeight(56)
        root.addWidget(self._ltl)

        # ── Execute button ───────────────────────────────────────────────────
        self._exec_btn = QPushButton("Execute Plan")
        self._exec_btn.setEnabled(False)
        self._exec_btn.setFont(QFont(FONT, 13, QFont.Bold))
        self._exec_btn.setFixedHeight(42)
        self._exec_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TEAL};
                color: white;
                border-radius: 10px;
                border: none;
            }}
            QPushButton:hover    {{ background-color: #3A8CB0; }}
            QPushButton:disabled {{ background-color: #9BB8C8; color: #ddd; }}
        """)
        self._exec_btn.clicked.connect(self._execute)
        root.addWidget(self._exec_btn)

        self._plan  = []
        self._boxes = []   # keep refs to box labels for highlighting

    # ── slots ────────────────────────────────────────────────────────────────

    def _on_frame(self, frame):
        """Convert numpy frame → QPixmap and display."""
        frame = np.ascontiguousarray(frame[::-1])
        h, w, ch = frame.shape
        img = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self._sim_view.width(),
            self._sim_view.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._sim_view.setPixmap(pix)

    def update_plan(self, plan, ltl=""):
        self._plan = plan

        while self._boxes_row.count():
            item = self._boxes_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._boxes = []
        for color in plan:
            box = QLabel(f"pick_place {color} cube")
            box.setFont(QFont(FONT, 12))
            box.setStyleSheet(f"""
                QLabel {{
                    background-color: {PLAN_BOX};
                    color: white;
                    border-radius: 8px;
                    padding: 8px 14px;
                }}
            """)
            self._boxes_row.addWidget(box)
            self._boxes.append(box)

        self._ltl.setText(ltl)
        self._exec_btn.setEnabled(True)

    def _execute(self):
        if not self._plan:
            return
        self._exec_btn.setEnabled(False)
        self._exec_btn.setText("Executing…")
        self._sim.request_execute(self._plan)

    def _highlight_box(self, active_idx):
        for idx, box in enumerate(self._boxes):
            if idx == active_idx:
                box.setStyleSheet("""
                    QLabel {
                        background-color: #3AAA5C;
                        color: white;
                        border-radius: 8px;
                        padding: 8px 14px;
                    }
                """)
            else:
                box.setStyleSheet(f"""
                    QLabel {{
                        background-color: {PLAN_BOX};
                        color: white;
                        border-radius: 8px;
                        padding: 8px 14px;
                    }}
                """)

    def _on_progress(self, i, color):
        if color != "done":
            self._exec_btn.setText(f"Placing {color}… ({i+1}/{len(self._plan)})")
            self._highlight_box(i)

    def _on_exec_done(self):
        self._highlight_box(-1)   # reset all to default
        self._exec_btn.setText("Execute Plan")
        self._exec_btn.setEnabled(True)

    def _on_exec_error(self, err):
        self._exec_btn.setText("Error — see console")
        self._exec_btn.setEnabled(True)
        print(f"[robot error] {err}")


# ── Main window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, sim):
        super().__init__()
        self.setWindowTitle("Collaborative Task Planner")
        self.setMinimumSize(1100, 700)
        self.resize(1500, 900)
        self.setStyleSheet(f"background-color: {BG};")
        self._sim = sim

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(20, 10, 20, 10)
        root.setSpacing(10)

        title = QLabel("Collaborative Task Planner")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont(FONT, 20, QFont.Bold))
        title.setStyleSheet(f"color: {TEAL}; background: transparent;")
        root.addWidget(title)

        split = QHBoxLayout()
        split.setSpacing(12)

        self._chat  = ChatPanel()
        self._chat.setFixedWidth(460)
        self._right = RightPanel(sim)

        self._chat.plan_updated.connect(lambda plan, ltl: self._right.update_plan(plan, ltl))

        split.addWidget(self._chat)
        split.addWidget(self._right)
        root.addLayout(split)

    def closeEvent(self, event):
        self._sim.stop()
        event.accept()

