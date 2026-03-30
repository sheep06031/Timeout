# Timeout

**A Study Productivity Hub for University Students**

Timeout is a web app designed to help university students stay organised, focused, and connected. It combines a Pomodoro focus timer, smart note-taking, calendar and deadline management, a social community, gamification, and productivity analytics into one platform.

**Deployed at:** https://kcltimeout.com

---

## Authors

- Bader Al Homood
- Elif Haciyanli
- Yagmur Erin Ozdemir
- Hikmet Ozan Kaya
- Juyeop Lee
- Som Ajmera
- Duru Atay

---

## Access Credentials

The following credentials are created automatically when running `nix run .#init`.

### Admin / Superuser
| Field    | Value                  |
|----------|------------------------|
| URL      | `/admin/`              |
| Username | `johndoe`              |
| Email    | `john.doe@email.com`   |

The admin account has full access to the Django admin panel and all moderation features within the application. We don't want to disclose admin password here, you can run "nix run .#init" to see the admin credentials.

### Regular Demo Users
80 additional student accounts are seeded with randomised data. All seeded users share the password below. Their usernames can be found via the admin panel or the user search on the social page.

| Field    | Value         |
|----------|---------------|
| Password | `Student@123` |

---

## Setup (Nix)

### Prerequisites
- [Nix package manager](https://nixos.org/download/) with flakes enabled

Add the following to `~/.config/nix/nix.conf` to enable flakes:
```
experimental-features = nix-command flakes
```

### Installation & Running

```bash
git clone https://github.com/ozankaya4/Timeout.git
cd Timeout
cp .env.example .env   # add API keys if needed (see below)
nix run .#init         # migrate, seed database, create demo user
nix run .#run          # start server at http://127.0.0.1:8000
```

### All Nix Commands

| Command          | Description |
|------------------|-------------|
| `nix run .#init` | Run migrations, seed database, create demo superuser |
| `nix run .#run`  | Start development server at http://127.0.0.1:8000 |
| `nix run .#tests`| Run all tests and generate HTML coverage report in `./coverage/` |
| `nix run .#seed` | Re-seed database without re-running migrations |
| `nix run .#unseed` | Remove all seeded data |

### Environment Variables

Copy `.env.example` to `.env`. All keys are optional, the app runs fully without them.

| Variable               | Required | Purpose |
|------------------------|----------|---------|
| `OPENAI_API_KEY`       | No       | AI calendar event creation and dashboard briefing |
| `SENDGRID_API_KEY`     | No       | Transactional email (password reset) |
| `SENDGRID_FROM_EMAIL`  | No       | Sender address for outbound emails |
| `GOOGLE_CLIENT_ID`     | No       | Google OAuth social login |
| `GOOGLE_CLIENT_SECRET` | No       | Google OAuth social login |

---

## AI Disclosure

AI assistance (GitHub Copilot / Claude Code) was used during the development of this project in the following areas:

- **Frontend design and implementation** — This was the area where AI assistance was used the most. AI helped with structuring UI components, writing and debugging HTML/CSS layouts, and implementing responsive design patterns.
- **CSS implementation** — AI was used to implement and refine styling, including dark mode overrides, colorblind accessibility modes, and component-level CSS.
- **Test case discovery** — AI helped identify edge cases and suggest test scenarios to improve coverage across views, services, and models.
- **Backend bug finding** — AI assisted in identifying and diagnosing backend bugs, particularly in view logic, model behaviour, and API response handling.

All AI-generated code was reviewed, understood, and integrated by team members. No AI output was used blindly or without verification.

---

## Third-Party Code & Libraries

The following third-party software was used directly or relied upon heavily in building this project.

### Python / Backend

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| Django | 5.x | Web framework (MVT architecture, ORM, auth) | https://www.djangoproject.com |
| django-allauth | latest | Social authentication (Google, GitHub, Discord) | https://allauth.org |
| Pillow | latest | Profile picture image processing | https://python-pillow.org |
| openai | latest | AI calendar event creation and study briefing | https://github.com/openai/openai-python |
| SendGrid | 6.11.0 | Transactional email delivery | https://github.com/sendgrid/sendgrid-python |
| python-dotenv | latest | `.env` file loading | https://github.com/theskumar/python-dotenv |
| Faker | latest | Seed data generation | https://faker.readthedocs.io |
| coverage.py | latest | Test coverage reporting | https://coverage.readthedocs.io |
| argon2-cffi | latest | Password hashing | https://github.com/hynek/argon2-cffi |

### JavaScript / Frontend

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| Bootstrap | 5.3.2 | UI component framework and grid layout | https://getbootstrap.com |
| Bootstrap Icons | 1.11.0 | Icon set | https://icons.getbootstrap.com |
| Chart.js | 4.4.0 | Statistics charts and heatmap visualisation | https://www.chartjs.org |
| Quill | 2.0.3 | Rich text editor for notes | https://quilljs.com |

All JavaScript libraries are loaded via CDN (jsDelivr). No npm build step is required.

---

## Features

### Dashboard
- Centralised view of upcoming events, deadlines, recent notes, social feed, and messages
- Time-aware greeting and quick action buttons
- Weekly focus statistics bar

### Pomodoro Focus Timer
- Customisable work, short break, and long break durations
- Focus mode integrated into the notes page
- Session history tracking with daily pomodoro counts
- Earns 25 XP per completed session

### Smart Notes
- Create, edit, delete, and pin notes
- Categories: Lecture, To-Do, Study Plan, Personal, Other
- Search and filter by category
- Link notes to calendar events
- Rich text support via Quill editor

### Calendar & Deadlines
- Month-view calendar with colour-coded event chips
- Event types: Deadline, Exam, Class, Meeting, Study Session, Other
- Priority levels and recurrence (Daily, Weekly, Monthly)
- AI-powered event creation via OpenAI
- Dedicated deadlines view with urgency indicators (Overdue, Urgent, On Track)

### Gamification
- **XP System**: Earn XP for creating notes (10 XP), editing notes (5 XP), completing focus sessions (25 XP), and maintaining streaks (5 XP/day bonus)
- **Levels**: Calculated from total XP
- **Streaks**: Track consecutive days of note-taking with longest streak records

### Social Community
- Post updates with public or followers-only visibility
- Like, comment (with threaded replies), and bookmark posts
- Follow/unfollow users and discover classmates via search
- User profiles with stats and post history
- Privacy settings and block/report functionality
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
- Customisable Pomodoro durations
- Daily study reminder time
- Default note category

### Authentication
- Email-based signup and login
- Social login via Google, GitHub, and Discord
- Profile completion flow on first login
