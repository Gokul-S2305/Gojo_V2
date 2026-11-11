# main.py placeholder
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QTabWidget
)

from modules.login import LoginWindow
from modules.dashboard import Dashboard
from modules.reminder_email import ReminderEmail as TripReminder
from modules.maps_preview import MapsPreview as GoogleMapsPreview
from modules.budget_planner import BudgetPlanner
from modules.pdf_export import TripSummaryPDF
from modules.photo_gallery import PhotoGallery

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gojo Trip Planner")
        self.setGeometry(100, 100, 1000, 700)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.init_tabs()

    def init_tabs(self):
        # Add all modules to the main tabs
        self.tabs.addTab(Dashboard(), "Dashboard")
        self.tabs.addTab(GoogleMapsPreview(), "Google Maps")
        self.tabs.addTab(BudgetPlanner(), "Budget Planner")
        self.tabs.addTab(TripReminder(), "Reminder Email")
        self.tabs.addTab(TripSummaryPDF(), "Export Trip Summary")
        self.tabs.addTab(PhotoGallery(), "Photo Gallery")

def run_app():
    app = QApplication(sys.argv)
    login = LoginWindow()
    
    def open_main():
        main_win = MainWindow()
        main_win.show()
        login.close()

    login.login_successful.connect(open_main)
    login.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run_app()
