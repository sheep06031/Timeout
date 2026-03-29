# Timeout — Developer's Manual

**Project:** Timeout – A Study Productivity Hub for University Students
**Deployed at:** https://kcltimeout.com
**Repository:** https://github.com/ozankaya4/Timeout

---

## 1. Prerequisites

- [Nix package manager](https://nixos.org/download/) with **flakes enabled**

To enable flakes, add the following to `~/.config/nix/nix.conf` (or `/etc/nix/nix.conf`):

```
experimental-features = nix-command flakes
```

No other dependencies need to be installed manually. Nix manages the entire Python environment.

---

## 2. Setup & Installation

Clone the repository and enter the project root:

```bash
git clone https://github.com/ozankaya4/Timeout.git
cd Timeout
```

Run the initialisation command. This performs migrations, configures the site, and seeds the database with demo data:

```bash
nix run .#init
```

This command:
1. Runs all Django database migrations
2. Runs `init_site` to configure the Django sites framework
3. Seeds the database with 25 demo users, realistic calendar events, notes, social posts, and focus sessions
4. Creates the demo superuser account (see §4)

---

## 3. Running the Application

Start the development server:

```bash
nix run .#run
```

The application will be available at **http://127.0.0.1:8000**

---

## 4. Access Credentials

### Demo Superuser (admin access)
| Field    | Value            |
|----------|------------------|
| Username | `johndoe`        |
| Password | `Password123`    |
| Email    | `john.doe@email.com` |

This account has full staff/superuser privileges and a pre-populated schedule, notes, and social activity.

### Django Admin Panel
Available at **http://127.0.0.1:8000/admin/** — log in with the superuser credentials above.

### Regular Demo Users
25 additional student accounts are seeded with randomised data. Their usernames and passwords can be found by logging into the admin panel and browsing the Users list. All seeded regular users have the password `Password123`.

---

## 5. Running Tests & Coverage

```bash
nix run .#tests
```

This command:
1. Runs the full test suite (1,184 tests) with verbosity
2. Generates an HTML coverage report in `./coverage/`
3. Prints a summary coverage report to the terminal

To view the detailed HTML report, open `./coverage/index.html` in a browser.

---

## 6. Database Seeding & Unseeding

Re-seed the database (without re-running migrations):

```bash
nix run .#seed
```

Remove all seeded data (returns the database to a clean post-migration state):

```bash
nix run .#unseed
```

---

## 7. Environment Variables

The application uses a `.env` file in the project root. Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable               | Required | Purpose |
|------------------------|----------|---------|
| `SECRET_KEY`           | Yes      | Django secret key |
| `OPENAI_API_KEY`       | No       | AI calendar event creation and dashboard briefing. Features degrade gracefully if absent — AI buttons return a friendly error. |
| `SENDGRID_API_KEY`     | No       | Transactional email (password reset codes). Email features are disabled if absent. |
| `SENDGRID_FROM_EMAIL`  | No       | Sender address for outbound emails |
| `GOOGLE_CLIENT_ID`     | No       | Google OAuth social login |
| `GOOGLE_CLIENT_SECRET` | No       | Google OAuth social login |

> **Note for markers:** The application runs fully without any optional keys. Social login and AI features simply become unavailable. All core functionality (notes, calendar, social feed, pomodoro, messaging, deadlines, statistics) works without any API keys.

---

## 8. Application Structure

| URL prefix      | Feature area |
|-----------------|--------------|
| `/`             | Landing page, dashboard, profile, statistics |
| `/calendar/`    | Calendar, event management, AI event creation |
| `/notes/`       | Notes, pomodoro timer, heatmap, daily goals |
| `/social/`      | Feed, user profiles, follow/block, messaging |
| `/deadlines/`   | Deadline tracker with urgency indicators |
| `/study-planner/` | AI-powered study session scheduler |
| `/notifications/` | Notification centre |
| `/settings/`    | Theme, accessibility, pomodoro, reminders |
| `/auth/`        | Login, signup, password reset, social login |
| `/admin/`       | Django admin panel (staff only) |

### Key source directories

| Path | Contents |
|------|----------|
| `timeout/models/` | Domain models: User, Event, Note, Post, Comment, Message, etc. |
| `timeout/views/` | HTTP handlers, split by feature domain |
| `timeout/services/` | Business logic layer (EventService, NoteService, FeedService, etc.) |
| `timeout/templates/` | Django HTML templates |
| `timeout/urls/` | URL configuration, one file per feature domain |
| `static/js/` | Frontend JavaScript (Fetch API, no framework) |
| `timeout/tests/` | Full test suite, mirroring the views/services/models structure |

---

## 9. Troubleshooting

**Migrations fail on `nix run .#init`**
Delete `db.sqlite3` and re-run `nix run .#init`. This resets the database entirely.

**`Site matching query does not exist` error**
Run `nix run .#init` rather than `nix run .#run` directly on a fresh database. The `init_site` step is required once before the server starts.

**Social login (Google) does not work locally**
OAuth redirect URIs must be registered with the provider for the specific domain. Social login is fully functional on the deployed site (https://kcltimeout.com). For local testing, use username/password login with the credentials in §4.

**AI features return an error message**
The `OPENAI_API_KEY` is not set in `.env`. All other features continue to work normally.

**Static files not loading**
Run `python manage.py collectstatic` inside the Nix dev shell:

```bash
nix develop
python manage.py collectstatic
```

**Port 8000 already in use**
Kill the existing process or use a different port:

```bash
nix develop
python manage.py runserver 127.0.0.1:8080
```
