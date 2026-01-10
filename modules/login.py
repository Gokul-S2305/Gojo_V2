from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt5.QtCore import pyqtSignal

class LoginWindow(QWidget):
    login_successful = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.setGeometry(300, 300, 300, 150)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        layout.addWidget(self.username)
        
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password)
        
        btn = QPushButton("Login")
        btn.clicked.connect(self.check_login)
        layout.addWidget(btn)
        
        self.setLayout(layout)

    def check_login(self):
        # fast pass for demo
        if self.username.text() == "admin" and self.password.text() == "admin":
            self.login_successful.emit()
        else:
            QMessageBox.warning(self, "Error", "Invalid credentials (try admin/admin)")
