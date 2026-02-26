# Timeout

**A Progressive Web App for University Students**

Timeout is a PWA designed to help university students balance academic deadlines, travel, social life, and personal well-being, all in one place.

---

## Tech Stack

| Layer       | Technology       |
|-------------|------------------|
| Backend     | Python, Django   |
| Frontend    | JavaScript, Bootstrap 5 |
| Database    | SQLite           |
| Deployment  | PythonAnywhere   |

---

## Core Features

### Dashboard & Calendar
- Centralized view of all upcoming deadlines and events
- Timetable import/export functionality
- Visual timeline for assignment tracking

### Notetaking
- Categorized notes system for quick thoughts or long-form study notes
- Organize by subject, priority, or custom tags
- Rich text support for formatted content

### Statistics
- Visual progress tracking for assignments and coursework
- Interactive "to-do" lists with completion metrics
- Motivational insights based on productivity patterns

### Social Hub
- Share study tips and resources with peers
- Follow classmates and build study networks
- Interact via likes, comments, and direct messages

### Customization
- Personalized profile settings
- Accessibility modes for inclusive design
- Theme preferences and notification controls

---

## Installation

### Prerequisites
- Python 3.10+
- pip

### Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/timeout.git
   cd timeout
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

   or

   ```bash
   python3 -m venv venv
   ```


3. **Activate the virtual environment**
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run database migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create a superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

7. **Start the development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**

   Open your browser and navigate to `http://127.0.0.1:8000`

---

## Deployment

This project is configured for deployment on **PythonAnywhere**.

1. Upload your project files to PythonAnywhere
2. Set up a virtual environment and install dependencies
3. Configure the WSGI file to point to `timeout_pwa.wsgi`
4. Set `DEBUG = False` and configure `ALLOWED_HOSTS` in production
5. Run `python manage.py collectstatic` to gather static files

---

## Upcoming Features

- **PWA Service Worker** — Offline support and installable app experience
- **Push Notifications** — Deadline reminders and social activity alerts
- **Enhanced Social Integration** — Group study sessions and shared calendars
- **AI Study Assistant** — Smart suggestions for study schedules
- **Mobile Optimization** — Native-like experience on all devices

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

<p align="center">
  <strong>Timeout</strong> — Balance your university life.
</p>
