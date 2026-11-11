# modules/pdf_export.py placeholder
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton, QFileDialog, QMessageBox
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

class TripSummaryPDF(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Export Trip Summary to PDF")
        self.setGeometry(300, 300, 500, 400)

        layout = QVBoxLayout()

        self.title_label = QLabel("Trip Title:")
        layout.addWidget(self.title_label)
        self.title_input = QLineEdit()
        layout.addWidget(self.title_input)

        self.content_label = QLabel("Trip Summary (notes, plans, itinerary, etc.):")
        layout.addWidget(self.content_label)
        self.content_input = QTextEdit()
        layout.addWidget(self.content_input)

        self.export_button = QPushButton("Export PDF")
        self.export_button.clicked.connect(self.export_pdf)
        layout.addWidget(self.export_button)

        self.setLayout(layout)

    def export_pdf(self):
        title = self.title_input.text()
        content = self.content_input.toPlainText()

        if not title or not content:
            QMessageBox.warning(self, "Incomplete", "Please fill in both title and content.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", f"{title}.pdf", "PDF Files (*.pdf)")
        if file_path:
            try:
                c = canvas.Canvas(file_path, pagesize=A4)
                width, height = A4
                c.setFont("Helvetica-Bold", 16)
                c.drawString(50, height - 50, title)
                c.setFont("Helvetica", 12)

                y = height - 100
                for line in content.split('\n'):
                    if y < 50:
                        c.showPage()
                        c.setFont("Helvetica", 12)
                        y = height - 50
                    c.drawString(50, y, line)
                    y -= 20

                c.save()
                QMessageBox.information(self, "Success", f"PDF saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save PDF:\n{e}")
