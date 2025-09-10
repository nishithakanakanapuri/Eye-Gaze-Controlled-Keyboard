import sys
import cv2
import time
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QTextEdit, QGridLayout, QHBoxLayout, QVBoxLayout
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtMultimedia import QSound
from gaze_tracking import GazeTracking
from wordfreq import top_n_list
from twilio.rest import Client

class GazeKeyboard(QWidget):
    def __init__(self):
        super().__init__()

        self.gaze = GazeTracking()
        self.webcam = cv2.VideoCapture(0)

        self.predictive_words = ["", "", ""]
        self.keys = [
            [],
            ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
            ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
            ["Z", "X", "C", "V", "B", "N", "M"],
            ["Space", "Backspace", "EMERGENCY"]
        ]

        self.row = 1
        self.col = 0

        self.left_eye_state = {"closed": False, "since": 0}
        self.right_eye_state = {"closed": False, "since": 0}
        self.both_closed_since = 0

        self.WINK_THRESHOLD = 0.01
        self.BLINK_THRESHOLD = 1
        self.MOVE_DELAY = 0.3
        self.last_move_time = 0

        self.sound = QSound("beep.wav")
        self.typed_text = ""

        self.initUI()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(50)

    def initUI(self):
        self.setWindowTitle("Gaze Controlled Keyboard")
        self.setGeometry(100, 100, 1600, 800)
        self.setStyleSheet("background-color: #E6F0FF;")

        main_layout = QHBoxLayout()  # Main horizontal layout

        # Left side: keyboard and text
        left_layout = QVBoxLayout()
        self.grid = QGridLayout()
        self.grid.setSpacing(10)

        self.text_edit = QTextEdit(self)
        self.text_edit.setFont(QFont("Arial", 20))
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet(
            "background-color: white; border-radius: 12px; padding: 10px; font-weight: bold;"
        )
        self.grid.addWidget(self.text_edit, 0, 0, 1, 10)

        self.labels = []

        self.prediction_labels = []
        for i in range(3):
            lbl = QLabel("", self)
            lbl.setFont(QFont("Arial", 18))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background-color: white; border: 2px solid #cccccc; border-radius: 15px;")
            lbl.setFixedSize(120, 70)
            self.grid.addWidget(lbl, 1, i * 3, 1, 3)
            self.prediction_labels.append(lbl)
        self.labels.append(self.prediction_labels)

        for i, row in enumerate(self.keys[1:], start=2):
            label_row = []
            for j in range(10):
                key = row[j] if j < len(row) else ""
                lbl = QLabel(key, self)
                lbl.setFont(QFont("Arial", 18))
                lbl.setAlignment(Qt.AlignCenter)

                if key == "EMERGENCY":
                    lbl.setStyleSheet("background-color: #FF4C4C; border-radius: 20px; color: white; font-weight: bold;")
                elif key == "":
                    lbl.setStyleSheet("background-color: transparent; border: none;")
                else:
                    lbl.setStyleSheet("background-color: white; border: 2px solid #cccccc; border-radius: 15px;")
                lbl.setFixedSize(120, 70)

                self.grid.addWidget(lbl, i, j)
                label_row.append(lbl)
            self.labels.append(label_row)

        self.detect_label = QLabel("Detection: ...", self)
        self.detect_label.setFont(QFont("Arial", 14))
        self.detect_label.setStyleSheet("color: green; font-weight: bold;")
        self.grid.addWidget(self.detect_label, len(self.labels) + 1, 0, 1, 10)

        for i in range(10):
            self.grid.setColumnStretch(i, 1)

        left_layout.addLayout(self.grid)
        main_layout.addLayout(left_layout)

        # Right side: webcam video
        right_layout = QVBoxLayout()
        self.video_label = QLabel(self)
        self.video_label.setFixedSize(400, 300)
        self.video_label.setStyleSheet("border: 2px solid #999; border-radius: 10px;")
        right_layout.addStretch()
        right_layout.addWidget(self.video_label)
        right_layout.addStretch()

        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)

    def update_highlight(self):
        for i, row in enumerate(self.labels):
            for j, lbl in enumerate(row):
                if i == self.row and j == self.col:
                    lbl.setStyleSheet("background-color: #FFEB99; border: 3px solid orange; border-radius: 15px;")
                else:
                    text = lbl.text()
                    if text == "EMERGENCY":
                        lbl.setStyleSheet("background-color: #FF4C4C; border-radius: 20px; color: white; font-weight: bold;")
                    elif i == 0:
                        lbl.setStyleSheet("background-color: white; border: 2px solid #cccccc; border-radius: 15px;")
                    elif text == "":
                        lbl.setStyleSheet("background-color: transparent; border: none;")
                    else:
                        lbl.setStyleSheet("background-color: white; border: 2px solid #cccccc; border-radius: 15px;")

    def update_predictions(self):
        text = self.text_edit.toPlainText().split()
        prefix = text[-1].lower() if text else ""
        predictions = [w for w in top_n_list('en', 50000) if w.startswith(prefix)][:3] if prefix else []
        self.predictive_words[:] = predictions + [""] * (3 - len(predictions))
        for i in range(3):
            self.prediction_labels[i].setText(self.predictive_words[i])

    def send_emergency_sms(self):
        try:
            account_sid = "your_twilio_account_sid_here"
            auth_token = "your_twilio_auth_token_here"
            from_number = "your_twilio_number"
            to_number = "your_reciepient_number"

            client = Client(account_sid, auth_token)
            message = client.messages.create(
                body="🚨 EMERGENCY ALERT: Immediate assistance needed!",
                from_=from_number,
                to=to_number
            )
            print(f"Emergency SMS sent: SID {message.sid}")
        except Exception as e:
            print("Failed to send emergency SMS:", e)

    def update_frame(self):
        ret, frame = self.webcam.read()
        if not ret:
            return

        self.gaze.refresh(frame)
        frame_with_gaze = self.gaze.annotated_frame()
        current_time = time.time()

        rgb_frame = cv2.cvtColor(frame_with_gaze, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        q_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(q_image).scaled(self.video_label.size(), Qt.KeepAspectRatio))

        if self.gaze.eye_left:
            if self.gaze.eye_left.is_closed:
                if not self.left_eye_state["closed"]:
                    self.left_eye_state["since"] = current_time
                self.left_eye_state["closed"] = True
            else:
                self.left_eye_state["closed"] = False

        if self.gaze.eye_right:
            if self.gaze.eye_right.is_closed:
                if not self.right_eye_state["closed"]:
                    self.right_eye_state["since"] = current_time
                self.right_eye_state["closed"] = True
            else:
                self.right_eye_state["closed"] = False

        action = "Looking center"

        if (self.left_eye_state["closed"] and not self.right_eye_state["closed"] and
                current_time - self.left_eye_state["since"] > self.WINK_THRESHOLD):
            action = "Left wink"
            if current_time - self.last_move_time > self.MOVE_DELAY:
                self.row = max(0, self.row - 1)
                self.col = min(self.col, len(self.labels[self.row]) - 1)
                self.last_move_time = current_time

        elif (self.right_eye_state["closed"] and not self.left_eye_state["closed"] and
              current_time - self.right_eye_state["since"] > self.WINK_THRESHOLD):
            action = "Right wink"
            if current_time - self.last_move_time > self.MOVE_DELAY:
                self.row = min(len(self.labels) - 1, self.row + 1)
                self.col = min(self.col, len(self.labels[self.row]) - 1)
                self.last_move_time = current_time

        elif self.left_eye_state["closed"] and self.right_eye_state["closed"]:
            if self.both_closed_since == 0:
                self.both_closed_since = current_time
            elif current_time - self.both_closed_since >= self.BLINK_THRESHOLD:
                action = "Blinking - Typing"
                key = self.labels[self.row][self.col].text()

                if self.row == 0:
                    text = self.text_edit.toPlainText().rstrip()
                    words = text.split()
                    if words:
                        words[-1] = key
                        self.typed_text = " ".join(words) + " "
                    else:
                        self.typed_text = key + " "
                else:
                    if key == "Space":
                        self.typed_text += " "
                    elif key == "Backspace":
                        self.typed_text = self.typed_text[:-1]
                    elif key == "EMERGENCY":
                        self.send_emergency_sms()
                    else:
                        self.typed_text += key

                self.text_edit.setPlainText(self.typed_text)
                self.sound.play()
                self.update_predictions()
                self.both_closed_since = 0
        else:
            self.both_closed_since = 0

        if not self.left_eye_state["closed"] and not self.right_eye_state["closed"]:
            if self.gaze.is_right():
                action = "Looking right"
                if current_time - self.last_move_time > self.MOVE_DELAY:
                    self.col = min(len(self.labels[self.row]) - 1, self.col + 1)
                    self.last_move_time = current_time
            elif self.gaze.is_left():
                action = "Looking left"
                if current_time - self.last_move_time > self.MOVE_DELAY:
                    self.col = max(0, self.col - 1)
                    self.last_move_time = current_time

        self.update_highlight()
        self.detect_label.setText(f"Detection: {action}")

    def closeEvent(self, event):
        self.webcam.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GazeKeyboard()
    ex.show()
    sys.exit(app.exec_())
