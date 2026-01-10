# Gojo Trip Planner

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)
<br/>
**Live Demo:** [https://gojo-trip-planner.onrender.com](https://gojo-trip-planner.onrender.com)

Gojo Trip Planner is a comprehensive application designed to help you organize and manage your travels effortlessly. It offers two interfaces: a modern **FastAPI-based Web Application** and a feature-rich **PyQt5-based Desktop Application**.

## 🚀 Key Features

### 🌐 Web Application
- **Authentication**: Secure user login and registration.
- **Dashboard**: Overview of upcoming trips and recent activities.
- **Interactive Maps**: Visualize your trip routes and locations (powered by Folium).
- **Photo Gallery**: Upload and manage memories from your trips.
- **Real-time Chat**: Coordinate with fellow travelers instantly.
- **PDF Export**: Generate professional trip summaries for offline use.

### 💻 Desktop Application
- **Personal Dashboard**: Quick access to your travel plans.
- **Maps Preview**: Integrated map view for location scouting.
- **Budget Planner**: track and manage your trip expenses.
- **Email Reminders**: Never miss a deadline with automated trip notifications.
- **Photo Gallery**: Local management of your travel photos.

## 🛠️ Technology Stack

- **Backend/Web**: FastAPI, Jinja2 Templates
- **Database**: SQLModel (SQLite for local, PostgreSQL for production)
- **Desktop UI**: PyQt5
- **Mapping**: Folium
- **PDF Generation**: ReportLab
- **Real-time**: WebSockets
- **Authentication**: Python-JOSE, Passlib (Bcrypt)
- **Deployment**: Render

## ⚙️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd gojo_1
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 🏃 Usage

### Running the Web Application
Launch the web server using `run.py`:
```bash
python run.py
```
Then open your browser and navigate to `http://127.0.0.1:8000`.

### Running the Desktop Application
Launch the PyQt5 GUI using the root `main.py`:
```bash
python main.py
```

## 📁 Project Structure

- `app/`: FastAPI web application source code (routers, templates, database).
- `modules/`: PyQt5 desktop application modules.
- `main.py`: Entry point for the Desktop application.
- `run.py`: Entry point for the Web application server.
- `requirements.txt`: Python dependencies.
- `db/`: Database related files.
- `uploads/` / `gallery/`: Storage for uploaded photos.
