import os

def load_trip_details():
    """Reads trip details from trip_details.txt and returns a dictionary."""
    trip_file = "trip_details.txt"
    if not os.path.exists(trip_file):
        return {}

    details = {}
    with open(trip_file, "r") as f:
        for line in f:
            if ":" in line:
                key, value = line.strip().split(":", 1)
                details[key.strip()] = value.strip()
    return details
