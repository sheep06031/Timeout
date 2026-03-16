# Timeout

**A Study Productivity Hub for University Students**

Timeout is a web app designed to help university students stay organized, focused, and connected. It combines a Pomodoro focus timer, smart note-taking, calendar and deadline management, a social community, gamification, and productivity analytics into one platform.

---

## Features

### Dashboard
- Centralized view of upcoming events, deadlines, recent notes, social feed, and messages
- Time-aware greeting and quick action buttons
- Weekly focus statistics bar

### Pomodoro Focus Timer
- Customizable work, short break, and long break durations
- Focus mode integrated into the notes page
- Session history tracking with daily pomodoro counts
- Earns 25 XP per completed session

### Smart Notes
- Create, edit, delete, and pin notes
- Categories: Lecture, To-Do, Study Plan, Personal, Other
- Search and filter by category
- Link notes to calendar events
- Rich text support (up to 5000 characters)

### Calendar & Deadlines
- Month-view calendar with color-coded event chips
- Event types: Deadline, Exam, Class, Meeting, Study Session, Other
- Priority levels (Low, Medium, High) and recurrence (Daily, Weekly, Monthly)
- Schedule conflict detection
- AI-powered event creation via OpenAI
- Dedicated deadlines view with urgency indicators (Overdue, Urgent, On Track)

### Gamification
- **XP System**: Earn XP for creating notes (10 XP), editing notes (5 XP), completing focus sessions (25 XP), and maintaining streaks (5 XP/day bonus)
- **Levels**: Calculated from total XP, level up as you study more
- **Streaks**: Track consecutive days of note-taking with longest streak records

### Social Community
- Post updates with public or followers-only visibility
- Like, comment (with threaded replies), and bookmark posts
- Follow/unfollow users and discover classmates via search
- User profiles with stats and post history
- Status updates: Focus Mode, Social, Inactive

### Direct Messaging
- Conversations with other users
- Read status tracking
- Real-time message polling

### Statistics & Analytics
- Focus time charts with daily breakdown (last 7 days)
- Event type distribution
- Urgent events tracker and total event counts

### Settings & Accessibility
- Themes: Light, Dark, System Default
- Colorblind modes: Protanopia, Deuteranopia, Tritanopia
- Adjustable font size (80%–150%)
- Notification sounds toggle
- Customizable Pomodoro durations
- Daily study reminder time
- Default note category

### Authentication
- Email-based signup and login
- Social login via Google, GitHub, and Discord
- Profile completion flow on first login

---

## Deployment

The deployed version of this app can be accessed through https://kcltimeout.com

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

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   ```
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   Copy `.env.example` to `.env` and fill in your keys:
   ```
   GOOGLE_CLIENT_ID=your-client-id
   GOOGLE_CLIENT_SECRET=your-client-secret
   OPENAI_API_KEY=your-openai-api-key
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
