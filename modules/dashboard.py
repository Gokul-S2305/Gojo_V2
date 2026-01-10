# dashboard.py placeholder
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QDateEdit, QPushButton, QMessageBox
)
from PyQt5.QtCore import QDate

class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trip Dashboard")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.trip_name_input = QLineEdit()
        self.trip_name_input.setPlaceholderText("Enter Trip Name")
        layout.addWidget(QLabel("Trip Name:"))
        layout.addWidget(self.trip_name_input)

        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("Enter Destination City")
        layout.addWidget(QLabel("Destination:"))
        layout.addWidget(self.destination_input)

        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        layout.addWidget(QLabel("Start Date:"))
        layout.addWidget(self.start_date)

        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        layout.addWidget(QLabel("End Date:"))
        layout.addWidget(self.end_date)

        self.save_button = QPushButton("Save Trip Details")
        self.save_button.clicked.connect(self.save_trip)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    def save_trip(self):
        name = self.trip_name_input.text()
        destination = self.destination_input.text()
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")

        if not name or not destination:
            QMessageBox.warning(self, "Missing Info", "Please fill in all fields.")
            return

        with open("trip_details.txt", "w") as f:
            f.write(f"Trip Name: {name}\n")
            f.write(f"Destination: {destination}\n")
            f.write(f"Start Date: {start}\n")
            f.write(f"End Date: {end}\n")

        QMessageBox.information(self, "Saved", "Trip details saved successfully!")
