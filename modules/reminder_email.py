# modules/reminder_email.py placeholder
import smtplib
from email.mime.text import MIMEText
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QDateEdit
from PyQt5.QtCore import QDate
from datetime import datetime

class ReminderEmail(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trip Reminder Email")
        self.setGeometry(300, 300, 400, 250)

        layout = QVBoxLayout()

        self.email_label = QLabel("Enter your email:")
        layout.addWidget(self.email_label)

        self.email_input = QLineEdit()
        layout.addWidget(self.email_input)

        self.date_label = QLabel("Select Trip Start Date:")
        layout.addWidget(self.date_label)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        layout.addWidget(self.date_input)

        self.send_button = QPushButton("Send Test Reminder")
        self.send_button.clicked.connect(self.send_email)
        layout.addWidget(self.send_button)

        self.setLayout(layout)

    def send_email(self):
        user_email = self.email_input.text()
        trip_date = self.date_input.date().toPyDate()
        current_date = datetime.now().date()

        if (trip_date - current_date).days != 1:
            QMessageBox.warning(self, "Not Sent", "Trip date is not tomorrow. Test email sent anyway.")

        subject = "Gojo Trip Reminder"
        body = f"Hi there!\n\nJust a reminder that your Gojo trip starts tomorrow on {trip_date}.\n\nSafe travels!\n— Team Gojo"

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = "your_email@gmail.com"       # Replace with your Gmail
        msg["To"] = user_email

        try:
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            server.login("your_email@gmail.com", "your_app_password")  # Use App Password from Gmail
            server.sendmail(msg["From"], [msg["To"]], msg.as_string())
            server.quit()
            QMessageBox.information(self, "Success", "Reminder email sent successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to send email:\n{e}")
