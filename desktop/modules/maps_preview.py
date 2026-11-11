
import sys
import webbrowser
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from geopy.geocoders import Nominatim
import folium

class MapsPreview(QWidget):
    def __init__(self, destination="New York"):
        super().__init__()
        self.setWindowTitle("Destination Map Preview")
        self.setGeometry(200, 200, 400, 200)

        self.destination = destination
        layout = QVBoxLayout()

        self.label = QLabel(f"Destination: {self.destination}")
        layout.addWidget(self.label)

        self.map_button = QPushButton("Show Map")
        self.map_button.clicked.connect(self.generate_map)
        layout.addWidget(self.map_button)

        self.setLayout(layout)

    def generate_map(self):
        geolocator = Nominatim(user_agent="gojo_trip_planner")
        location = geolocator.geocode(self.destination)
        if location:
            map_obj = folium.Map(location=[location.latitude, location.longitude], zoom_start=12)
            folium.Marker([location.latitude, location.longitude], popup=self.destination).add_to(map_obj)
            map_obj.save("map.html")
            webbrowser.open("map.html")
        else:
            self.label.setText("Location not found")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MapsPreview("Chennai")
    window.show()
    sys.exit(app.exec_())
