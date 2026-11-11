# modules/budget_planner.py placeholder
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

class BudgetPlanner(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Budget Planner – Gojo")
        self.setGeometry(500, 200, 600, 400)
        self.total_cost = 0
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("Trip Budget Planner")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)

        # Inputs
        input_layout = QHBoxLayout()
        self.purpose_input = QLineEdit()
        self.purpose_input.setPlaceholderText("Purpose (e.g., Travel, Hotel)")

        self.cost_input = QLineEdit()
        self.cost_input.setPlaceholderText("Cost (in ₹)")

        add_btn = QPushButton("Add Expense")
        add_btn.clicked.connect(self.add_expense)
        add_btn.setStyleSheet(self.button_style())

        input_layout.addWidget(self.purpose_input)
        input_layout.addWidget(self.cost_input)
        input_layout.addWidget(add_btn)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Purpose", "Cost (₹)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Total
        self.total_label = QLabel("Total: ₹0")
        self.total_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.total_label.setAlignment(Qt.AlignRight)

        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addLayout(input_layout)
        layout.addWidget(self.table)
        layout.addWidget(self.total_label)

        self.setLayout(layout)

    def add_expense(self):
        purpose = self.purpose_input.text().strip()
        cost_text = self.cost_input.text().strip()

        if not purpose or not cost_text:
            QMessageBox.warning(self, "Input Error", "Please fill in both fields.")
            return

        try:
            cost = float(cost_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Cost must be a number.")
            return

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(purpose))
        self.table.setItem(row, 1, QTableWidgetItem(f"{cost:.2f}"))

        self.total_cost += cost
        self.total_label.setText(f"Total: ₹{self.total_cost:.2f}")

        self.purpose_input.clear()
        self.cost_input.clear()

    def button_style(self):
        return """
            QPushButton {
                background-color: #00b894;
                color: white;
                padding: 6px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #019875;
            }
        """
