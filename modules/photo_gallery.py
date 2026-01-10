# modules/photo_gallery.py placeholder
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog,
    QScrollArea, QHBoxLayout, QGridLayout, QMessageBox
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

class PhotoGallery(QWidget):
    def __init__(self, gallery_dir="gallery"):
        super().__init__()
        self.setWindowTitle("Trip Photo Gallery")
        self.setGeometry(300, 300, 800, 600)
        self.gallery_dir = gallery_dir

        if not os.path.exists(self.gallery_dir):
            os.makedirs(self.gallery_dir)

        layout = QVBoxLayout()

        upload_button = QPushButton("Upload Photos")
        upload_button.clicked.connect(self.upload_photos)
        layout.addWidget(upload_button)

        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.scroll_layout = QGridLayout()
        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_widget)

        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

        self.load_gallery()

    def upload_photos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Photos", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if files:
            for file in files:
                file_name = os.path.basename(file)
                target_path = os.path.join(self.gallery_dir, file_name)
                if not os.path.exists(target_path):
                    with open(file, 'rb') as f_in, open(target_path, 'wb') as f_out:
                        f_out.write(f_in.read())
            QMessageBox.information(self, "Success", "Photos uploaded!")
            self.load_gallery()

    def load_gallery(self):
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        photos = [f for f in os.listdir(self.gallery_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]

        row = 0
        col = 0
        for idx, photo in enumerate(photos):
            pixmap = QPixmap(os.path.join(self.gallery_dir, photo))
            pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            label = QLabel()
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(label, row, col)

            col += 1
            if col >= 4:
                col = 0
                row += 1
