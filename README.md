# Gojo Trip Planner


<br/>
**Live Demo:** [https://gojo-trip-planner.onrender.com](https://gojo-trip-planner.onrender.com)

Gojo Trip Planner is a FastAPI web application for collaborative trip planning, itineraries, bookings, and shared travel memories.

## 🚀 Key Features

### 🌐 Web Application
- **Authentication**: Secure user login and registration with Google OAuth Support.
- **Dashboard**: Overview of upcoming trips, recent activities, and itinerary management.
- **AI trip planning**: Generate destination ideas and day-by-day itinerary drafts with Gemini 2.5 Flash.
- **Interactive maps**: Explore trip destinations and routes with OpenStreetMap data.
- **Gallery**: Upload and download photos and videos to share memories.
- **Real-time Chat**: Coordinate with fellow travelers instantly.
- **PDF Export**: Generate professional trip summaries for offline use.

### 💻 Desktop Prototype
The separate PyQt5 desktop app in `desktop/` is an unfinished demo, independent of the web app. Its login uses hardcoded demo credentials and its email reminder module contains placeholders. Do not use it with real accounts, data, or email credentials; it is not production-ready and its optional dependencies are not included in `requirements.txt`.

## 🛠️ Technology Stack

- **Backend/Web**: FastAPI, Jinja2 Templates
- **Database**: SQLModel (SQLite for local, PostgreSQL for production)
- **Desktop UI**: PyQt5
- **Mapping**: Folium
- **PDF Generation**: ReportLab
- **Real-time**: WebSockets
- **Authentication**: PyJWT, bcrypt, Authlib
- **Deployment**: Render

## ⚙️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Gojo_V2
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt

3. **Configure AI suggestions** (optional): copy `.env.example` to `.env` and set `GEMINI_API_KEY` to a valid Google AI Studio key. AI suggestions are not replaced with sample places when the provider is unavailable; the page will offer a retry instead.
   ```

## 🏃 Usage

### Running the Web Application
Launch the web server using `run.py`:
```bash
python run.py
```
Then open your browser and navigate to `http://127.0.0.1:8000`.

### Running the Desktop Application
The desktop prototype can be launched separately (after installing its required dependencies):
```bash
python desktop/main.py
```

## 📁 Project Structure

- `app/`: FastAPI web application source code (routers, templates, database).
- `desktop/`: Unfinished PyQt5 desktop prototype; not production-ready.
- `run.py`: Entry point for the Web application server.
- `requirements.txt`: Web application dependencies.
- `alembic/`: Database schema migrations.
- `uploads/` / `gallery/`: Storage for uploaded photos.
