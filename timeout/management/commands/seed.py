"""
Custom management command to seed the database with test data.

Usage:
    python manage.py seed
"""

import os
import random
from datetime import timedelta

from dotenv import load_dotenv


from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone
from faker import Faker

from allauth.socialaccount.models import SocialApp
from timeout.models import Event, Post, Comment, Like, Bookmark, FocusSession, Note, StudyLog, Conversation, Message

User = get_user_model()
fake = Faker()

NUM_USERS = 25
NUM_EVENTS = 15
NUM_POSTS = 40
NUM_NOTES_PER_USER = (5, 50)  # min, max notes per user
HEATMAP_WEEKS = 12
SUPERUSER_USERNAME = 'johndoe'
SUPERUSER_PASSWORD = 'Password123'
SUPERUSER_EMAIL = 'john.doe@email.com'
DEFAULT_PASSWORD = 'Student@123'

UNIVERSITIES = [
    'Kings College London',
    'Imperial College London',
    'University College London',
    'Oxford University',
    'Cambridge University',
    'University of Manchester',
    'University of Edinburgh',
    'University of Warwick',
    'University of Glasgow',
    'London School of Economics',
    'London Business School',
    'University of Bath',
    'Newcastle University',
    'Durham University',
]

INTERESTS = [
    'Computer Science',
    'Mathematics',
    'Physics',
    'Engineering',
    'Literature',
    'Philosophy',
    'Economics',
    'Biology',
    'Chemistry',
    'History',
    'Psychology',
    'Art',
    'Music',
    'Political Science',
    'Data Science',
]

MANAGEMENT_STYLES = ['early_bird', 'night_owl']

NOTE_CATEGORIES = ['lecture', 'todo', 'study_plan', 'personal', 'other']

NOTE_TITLES = {
    'lecture': [
        'Lecture 1 — Introduction to {}',
        '{} — Key Concepts',
        'Week {} Notes: {}',
        '{} Lecture Summary',
        'Guest Lecture: {}',
    ],
    'todo': [
        'Submit {} assignment',
        'Review {} before exam',
        'Email professor about {}',
        'Finish {} lab report',
        'Prepare slides for {}',
        'Buy materials for {}',
    ],
    'study_plan': [
        '{} Exam Prep Plan',
        'Weekly Study Schedule — {}',
        '{} Revision Strategy',
        'Group Study Plan: {}',
        'Final Exam Roadmap — {}',
    ],
    'personal': [
        'Gym routine this week',
        'Meal prep ideas',
        'Books to read this month',
        'Budget tracker — {}',
        'Weekend plans',
        'Self-care reminders',
    ],
    'other': [
        'Meeting notes — {}',
        'Random thoughts on {}',
        'Club event planning',
        'Internship application notes',
        'Career fair prep',
    ],
}

NOTE_CONTENT_SNIPPETS = [
    'Need to focus on the main concepts here. The professor emphasized that this will be on the exam.',
    'Key takeaway: always start with the fundamentals before moving to advanced topics.',
    'Remember to cross-reference with the textbook chapter {}. There are some discrepancies with the slides.',
    'This connects to what we learned last week about {}. Important to see the bigger picture.',
    'TODO: re-watch the recorded lecture and fill in the gaps from my notes.',
    'Great discussion in today\'s seminar. The point about {} really changed my perspective.',
    'Step 1: Outline the problem. Step 2: Break it into subproblems. Step 3: Solve each part.',
    'The formula is straightforward but the edge cases are tricky. Need more practice problems.',
    'Deadline is approaching fast. Prioritize sections A and C, section B can wait.',
    'Group decided to split the work: I\'m handling the implementation, Alex does the report.',
    'Interesting approach using {} — could be useful for the final project too.',
    'Don\'t forget to include citations from the {} paper. The professor is strict about referencing.',
]

SITE_DOMAIN = '127.0.0.1:8000'
SITE_NAME = 'Timeout Local'


class Command(BaseCommand):
    help = 'Seed the database with site config, Google OAuth app, a superuser, and 25 random student users.'

    def handle(self, *args, **options):
        self.stdout.write('=' * 50)
        self.stdout.write('SEEDING DATABASE')
        self.stdout.write('=' * 50)

        self.stdout.write('\n[1/9] Setting up Site...')
        self._setup_site()

        self.stdout.write('\n[2/9] Setting up Google SocialApp...')
        self._setup_google_social_app()

        self.stdout.write('\n[3/9] Creating superuser...')
        self._create_superuser()

        self.stdout.write(f'\n[4/9] Creating {NUM_USERS} users...')
        users = self._create_users(NUM_USERS)

        self.stdout.write(f'\n[5/9] Creating follow relationships...')
        self._create_follow_relationships(users)

        self.stdout.write(f'\n[6/9] Creating {NUM_EVENTS} events...')
        events = self._create_events(users)

        self.stdout.write(f'\n[7/9] Creating {NUM_POSTS} posts...')
        posts = self._create_posts(users, events)

        self.stdout.write('\n[8/9] Creating comments...')
        self._create_comments(users, posts)

        self.stdout.write('\n[9/9] Creating likes and bookmarks...')
        self._create_likes_and_bookmarks(users, posts)

        self.stdout.write('\n[10/9] Creating focus sessions...')
        self._create_focus_sessions(users)

        self.stdout.write('\n[11/9] Creating johndoe schedule...')
        self._create_johndoe_schedule()

        self.stdout.write(f'\n[6b/9] Creating global recurring events...')
        self._create_global_events()

        self.stdout.write('\n[12] Creating notes for all users...')
        self._create_notes(users)

        self.stdout.write('\n[13] Creating study logs (heatmap data)...')
        self._create_study_logs(users)

        self.stdout.write('\n[14] Setting gamification stats...')
        self._set_gamification_stats(users)

        self.stdout.write('\n[15] Creating messages for johndoe...')
        self._create_messages()

        total_users = User.objects.count()
        total_posts = Post.objects.count()
        total_events = Event.objects.count()
        total_notes = Note.objects.count()
        total_logs = StudyLog.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Users: {total_users}, '
            f'Posts: {total_posts}, Events: {total_events}, '
            f'Notes: {total_notes}, StudyLogs: {total_logs}'
        ))

    def _setup_site(self):
        """Ensure Site(id=1) exists with the correct domain."""
        Site.objects.all().delete()
        Site.objects.create(id=1, domain=SITE_DOMAIN, name=SITE_NAME)
        self.stdout.write(self.style.SUCCESS(
            f'  Site(id=1, domain="{SITE_DOMAIN}") ready.'
        ))

    def _setup_google_social_app(self):
        """Create the Google SocialApp from environment variables if missing."""
        load_dotenv()
        client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
        secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')

        if not client_id or not secret:
            self.stdout.write(self.style.WARNING(
                '  GOOGLE_CLIENT_ID and/or GOOGLE_CLIENT_SECRET not set.\n'
                '  Skipping Google SocialApp creation.\n'
                '  Set these env vars and re-run seed to enable Google login.'
            ))
            return

        app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': client_id,
                'secret': secret,
            },
        )

        if not created:
            app.client_id = client_id
            app.secret = secret
            app.save()

        site = Site.objects.get(id=1)
        app.sites.add(site)

        label = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'  {label} Google SocialApp and linked to site.'
        ))

    def _create_superuser(self):
        """Create the @johndoe superuser if they don't already exist."""
        if User.objects.filter(username=SUPERUSER_USERNAME).exists():
            self.stdout.write(self.style.WARNING(
                f'  Superuser @{SUPERUSER_USERNAME} already exists, skipping.'
            ))
            return

        try:
            User.objects.create_superuser(
                username=SUPERUSER_USERNAME,
                email=SUPERUSER_EMAIL,
                password=SUPERUSER_PASSWORD,
                first_name='John',
                last_name='Doe',
                university='Galatasaray University',
                year_of_study=3,
                bio='Admin account for the Timeout platform.',
                academic_interests='Computer Science, Data Science',
                management_style='early_bird',
            )
            self.stdout.write(self.style.SUCCESS(
                f'  Superuser @{SUPERUSER_USERNAME} created.'
            ))
        except IntegrityError as e:
            self.stdout.write(self.style.ERROR(
                f'  Failed to create superuser: {e}'
            ))

    def _create_users(self, count):
        """Create regular user accounts with randomized Faker data."""
        users = []
        existing = set(User.objects.values_list('username', flat=True))

        for i in range(count):
            username = fake.user_name()
            while username in existing:
                username = fake.user_name() + str(random.randint(10, 99))
            existing.add(username)

            try:
                user = User.objects.create_user(
                    username=username,
                    email=fake.unique.email(),
                    password=DEFAULT_PASSWORD,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    middle_name=fake.first_name() if random.random() < 0.3 else '',
                    university=random.choice(UNIVERSITIES),
                    year_of_study=random.randint(1, 5),
                    bio=fake.sentence(nb_words=12),
                    academic_interests=', '.join(
                        random.sample(INTERESTS, k=random.randint(1, 4))
                    ),
                    privacy_private=random.choice([True, False]),
                    management_style=random.choice(MANAGEMENT_STYLES),
                )
                users.append(user)
                self.stdout.write(f'  [{i + 1}/{count}] Created @{username}')
            except IntegrityError as e:
                self.stdout.write(self.style.ERROR(
                    f'  [{i + 1}/{count}] Failed @{username}: {e}'
                ))

        return users

    def _create_follow_relationships(self, users):
        """Establish random follow relationships between all users."""
        all_users = list(User.objects.all())
        follow_count = 0

        for user in all_users:
            others = [u for u in all_users if u != user]
            to_follow = random.sample(
                others, k=min(random.randint(2, 8), len(others))
            )
            user.following.add(*to_follow)
            follow_count += len(to_follow)

        self.stdout.write(self.style.SUCCESS(
            f'  Created {follow_count} follow relationships.'
        ))

    def _create_events(self, users):
        """Create calendar events."""
        events = []
        event_types = ['deadline', 'exam', 'class', 'meeting', 'study_session']

        for i in range(NUM_EVENTS):
            creator = random.choice(users)
            start = timezone.now() + timedelta(
                days=random.randint(-7, 30),
                hours=random.randint(8, 20)
            )
            end = start + timedelta(hours=random.randint(1, 3))

            event = Event.objects.create(
                creator=creator,
                title=fake.sentence(nb_words=4).rstrip('.'),
                description=fake.paragraph(),
                event_type=random.choice(event_types),
                start_datetime=start,
                end_datetime=end,
                location=fake.city() if random.random() < 0.5 else '',
                is_all_day=random.random() < 0.2
            )
            events.append(event)
            self.stdout.write(f'  [{i + 1}/{NUM_EVENTS}] Created event: {event.title}')

        return events

    def _create_posts(self, users, events):
        """Create social posts."""
        posts = []
        post_templates = [
            "Just finished {} - feeling accomplished! 🎉",
            "Anyone else struggling with {}? Need study buddies!",
            "Quick reminder: {} coming up soon!",
            "Amazing lecture on {} today! 🔥",
            "Looking for group members for {} project",
            "Can someone explain {}? I'm totally lost 😅",
            "Procrastination level: {} 😴",
            "Best resources for {}?",
        ]

        for i in range(NUM_POSTS):
            author = random.choice(users)
            has_event = random.random() < 0.3 and events

            if random.random() < 0.7:
                content = random.choice(post_templates).format(
                    fake.sentence(nb_words=3).rstrip('.')
                )
            else:
                content = fake.paragraph(nb_sentences=random.randint(1, 3))

            post = Post.objects.create(
                author=author,
                content=content,
                event=random.choice(events) if has_event else None,
                privacy=random.choice(['public', 'followers_only'])
            )
            posts.append(post)
            self.stdout.write(f'  [{i + 1}/{NUM_POSTS}] Created post by @{author.username}')

        return posts

    def _create_comments(self, users, posts):
        """Create comments on posts."""
        comment_count = 0

        for post in posts:
            num_comments = random.randint(0, 5)
            for _ in range(num_comments):
                author = random.choice(users)
                Comment.objects.create(
                    author=author,
                    post=post,
                    content=fake.sentence(nb_words=random.randint(5, 15))
                )
                comment_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'  Created {comment_count} comments.'
        ))

    def _create_global_events(self):
        """Create traditional recurring global events visible to all users."""
        from datetime import datetime
        from django.utils import timezone

        global_events = [
            {"title": "Christmas Day", "month": 12, "day": 25},
            {"title": "Valentine's Day", "month": 2, "day": 14},
            {"title": "New Year's Day", "month": 1, "day": 1},
            {"title": "Halloween", "month": 10, "day": 31},
            {"title": "New Year's Eve", "month": 12, "day": 31},
            {"title": "Christmas Eve", "month": 12, "day": 24},
        ]

        created = 0
        current_year = timezone.now().year

        for ev in global_events:
            start = timezone.make_aware(datetime(current_year, ev["month"], ev["day"], 0, 0))
            end = timezone.make_aware(datetime(current_year, ev["month"], ev["day"], 23, 59))

            event, created_flag = Event.objects.get_or_create(
                title=ev["title"],
                start_datetime=start,
                end_datetime=end,
                is_global=True,
                recurrence="yearly",
                defaults={
                    "creator": None,  # global events have no creator
                    "description": f"Global event: {ev['title']}",
                    "visibility": Event.Visibility.PUBLIC,
                }
            )
            created += 1
            self.stdout.write(f'  Global event: {event.title} ({start.date()})')

        self.stdout.write(self.style.SUCCESS(f'  Created {created} global recurring events.'))

    def _create_johndoe_schedule(self):
        """Create a realistic student schedule for johndoe."""
        johndoe = User.objects.filter(username=SUPERUSER_USERNAME).first()
        if not johndoe:
            self.stdout.write(self.style.WARNING('  johndoe not found, skipping.'))
            return

        from django.utils.timezone import make_aware
        from datetime import datetime

        def dt(year, month, day, hour, minute=0):
            return make_aware(datetime(year, month, day, hour, minute))

        now = timezone.now()
        y = now.year
        m = now.month

        # Helper: offset days from today
        def days(n, hour=9, minute=0, duration_h=1):
            start = timezone.now().replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=n)
            end = start + timedelta(hours=duration_h)
            return start, end

        events = []

        # ── Weekly classes (recurring feel — 4 weeks around now) ──
        weekly_classes = [
            ('Software Engineering Group Project', 'class', 'Bush House, KCL', 10, 0, 2),
            ('Algorithms & Complexity', 'class', 'Strand Building, KCL', 14, 0, 1),
            ('Database Systems', 'class', 'Waterloo Campus', 9, 0, 1),
            ('Machine Learning', 'class', 'Bush House, KCL', 13, 0, 2),
        ]
        weekday_offsets = {
            'Software Engineering Group Project': 0,   # Monday
            'Algorithms & Complexity': 2,              # Wednesday
            'Database Systems': 1,                     # Tuesday
            'Machine Learning': 3,                     # Thursday
        }

        for title, etype, loc, hour, minute, dur in weekly_classes:
            base_offset = weekday_offsets[title]
            today_weekday = timezone.now().weekday()
            days_to_next = (base_offset - today_weekday) % 7
            for week in range(-3, 5):
                offset = days_to_next + week * 7
                start, end = days(offset, hour, minute, dur)
                events.append(dict(
                    creator=johndoe, title=title, event_type=etype,
                    start_datetime=start, end_datetime=end,
                    location=loc, visibility='private',
                    status='completed' if offset < 0 else 'upcoming',
                ))

        # ── Exams ──
        exams = [
            ('Algorithms & Complexity Exam', days(18, 9, 0, 3), 'Exam Hall A, KCL'),
            ('Database Systems Exam', days(32, 14, 0, 2), 'Great Hall, KCL'),
            ('Machine Learning Final Exam', days(45, 10, 0, 3), 'Exam Hall B, KCL'),
        ]
        for title, (start, end), loc in exams:
            events.append(dict(
                creator=johndoe, title=title, event_type='exam',
                start_datetime=start, end_datetime=end,
                location=loc, visibility='private', status='upcoming',
            ))

        # ── Deadlines ──
        deadlines = [
            ('SEG Coursework Submission', days(7, 23, 59, 0), ''),
            ('ML Assignment 2 Due', days(14, 23, 59, 0), ''),
            ('Database ER Diagram Submission', days(21, 23, 59, 0), ''),
            ('SEG Final Report', days(50, 23, 59, 0), ''),
        ]
        for title, (start, end), loc in deadlines:
            end = start + timedelta(minutes=1)
            events.append(dict(
                creator=johndoe, title=title, event_type='deadline',
                start_datetime=start, end_datetime=end,
                location=loc, visibility='private', status='upcoming',
            ))

        # ── Study sessions ──
        study = [
            ('Algorithms Revision', days(15, 14, 0, 2)),
            ('ML Past Papers', days(40, 10, 0, 3)),
            ('DB Exam Prep', days(28, 16, 0, 2)),
            ('Group Study – SEG', days(5, 15, 0, 2)),
        ]
        for title, (start, end) in study:
            events.append(dict(
                creator=johndoe, title=title, event_type='study_session',
                start_datetime=start, end_datetime=end,
                location='Library, KCL', visibility='private', status='upcoming',
            ))

        # ── Meetings ──
        meetings = [
            ('SEG Team Meeting', days(3, 11, 0, 1)),
            ('Supervisor Check-in', days(10, 14, 0, 1)),
            ('Career Fair Prep', days(6, 13, 0, 1)),
        ]
        for title, (start, end) in meetings:
            events.append(dict(
                creator=johndoe, title=title, event_type='meeting',
                start_datetime=start, end_datetime=end,
                location='Bush House, KCL', visibility='private', status='upcoming',
            ))

        created = 0
        for ev in events:
            # Ensure end > start
            if ev['end_datetime'] <= ev['start_datetime']:
                ev['end_datetime'] = ev['start_datetime'] + timedelta(hours=1)
            Event.objects.create(**ev)
            created += 1

        self.stdout.write(self.style.SUCCESS(f'  Created {created} events for @{SUPERUSER_USERNAME}.'))

    def _create_focus_sessions(self, users):
        """Create focus sessions for johndoe and a few random users for the last 7 days."""
        johndoe = User.objects.filter(username=SUPERUSER_USERNAME).first()
        targets = ([johndoe] if johndoe else []) + random.sample(users, min(5, len(users)))

        count = 0
        now = timezone.now()
        for user in targets:
            for day_offset in range(7):
                if random.random() < 0.7:
                    started_at = now - timedelta(
                        days=day_offset,
                        hours=random.randint(0, 10),
                        minutes=random.randint(0, 59),
                    )
                    duration = random.randint(10 * 60, 120 * 60)
                    ended_at = started_at + timedelta(seconds=duration)
                    FocusSession.objects.create(
                        user=user,
                        started_at=started_at,
                        ended_at=ended_at,
                        duration_seconds=duration,
                    )
                    count += 1

        self.stdout.write(self.style.SUCCESS(f'  Created {count} focus sessions.'))

    def _create_likes_and_bookmarks(self, users, posts):
        """Create likes and bookmarks."""
        like_count = 0
        bookmark_count = 0

        for post in posts:
            # Likes
            num_likes = random.randint(0, min(10, len(users)))
            likers = random.sample(users, num_likes)
            for user in likers:
                Like.objects.get_or_create(user=user, post=post)
                like_count += 1

            # Bookmarks
            if random.random() < 0.3:
                num_bookmarks = random.randint(1, 3)
                bookmarkers = random.sample(users, min(num_bookmarks, len(users)))
                for user in bookmarkers:
                    Bookmark.objects.get_or_create(user=user, post=post)
                    bookmark_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'  Created {like_count} likes and {bookmark_count} bookmarks.'
        ))

    def _create_notes(self, users):
        """Create notes with due dates, categories, and time spent for all users."""
        all_users = list(User.objects.all())
        subjects = ['Algorithms', 'Machine Learning', 'Database Systems',
                     'Software Engineering', 'Networks', 'Maths', 'Statistics',
                     'Operating Systems', 'AI', 'Web Development']
        now = timezone.now()
        note_count = 0

        for user in all_users:
            # Get user's events for linking
            user_events = list(user.created_events.all()[:10])
            num_notes = random.randint(*NUM_NOTES_PER_USER)

            for i in range(num_notes):
                category = random.choice(NOTE_CATEGORIES)
                subject = random.choice(subjects)

                # Pick a title template
                titles = NOTE_TITLES[category]
                title_template = random.choice(titles)
                try:
                    if '{}' in title_template:
                        if 'Week' in title_template:
                            title = title_template.format(random.randint(1, 12), subject)
                        else:
                            title = title_template.format(subject)
                    else:
                        title = title_template
                except (IndexError, KeyError):
                    title = f'{subject} Notes'

                # Build content from snippets
                num_snippets = random.randint(1, 3)
                content_parts = []
                for _ in range(num_snippets):
                    snippet = random.choice(NOTE_CONTENT_SNIPPETS)
                    if '{}' in snippet:
                        snippet = snippet.format(subject)
                    content_parts.append(snippet)
                content = '\n\n'.join(content_parts)

                # Due date: ~40% of todo/study_plan notes have due dates
                due_date = None
                if category in ('todo', 'study_plan') and random.random() < 0.6:
                    days_ahead = random.randint(-3, 14)
                    due_date = now + timedelta(days=days_ahead, hours=random.randint(8, 23))
                elif random.random() < 0.15:
                    due_date = now + timedelta(days=random.randint(1, 30))

                # Time spent: some notes have Pomodoro time logged
                time_spent = 0
                if random.random() < 0.4:
                    time_spent = random.choice([25, 25, 50, 50, 75, 100, 125, 150])

                # Created at: spread notes over last 2 months
                created_offset = timedelta(
                    days=random.randint(0, 60),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                )
                created_at = now - created_offset

                # Pin some notes
                is_pinned = random.random() < 0.15

                # Link to event occasionally
                event = None
                if user_events and random.random() < 0.3:
                    event = random.choice(user_events)

                note = Note(
                    owner=user,
                    title=title[:200],
                    content=content[:5000],
                    category=category,
                    event=event,
                    is_pinned=is_pinned,
                    due_date=due_date,
                    time_spent_minutes=time_spent,
                )
                note.save()
                # Override auto_now_add for created_at
                Note.objects.filter(pk=note.pk).update(created_at=created_at)
                note_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'  Created {note_count} notes across {len(all_users)} users.'
        ))

    def _create_study_logs(self, users):
        """Create study log entries for heatmap data over the past 12 weeks."""
        all_users = list(User.objects.all())
        now = timezone.localtime(timezone.now())
        today = now.date()
        log_count = 0

        for user in all_users:
            # Each user has varying activity levels
            activity_level = random.choice(['low', 'medium', 'high'])
            active_prob = {'low': 0.25, 'medium': 0.5, 'high': 0.75}[activity_level]

            for day_offset in range(HEATMAP_WEEKS * 7):
                date = today - timedelta(days=day_offset)

                # Skip some days based on activity level
                if random.random() > active_prob:
                    continue

                # Weekend = lower activity
                if date.weekday() >= 5 and random.random() < 0.4:
                    continue

                pomodoros = random.choices(
                    [0, 1, 2, 3, 4, 5, 6],
                    weights=[10, 20, 25, 20, 15, 7, 3],
                )[0]
                notes_created = random.choices(
                    [0, 1, 2, 3, 4],
                    weights=[20, 35, 25, 15, 5],
                )[0]
                focus_minutes = pomodoros * random.randint(20, 30) + random.randint(0, 15)

                if pomodoros == 0 and notes_created == 0 and focus_minutes == 0:
                    continue

                StudyLog.objects.get_or_create(
                    user=user,
                    date=date,
                    defaults={
                        'pomodoros': pomodoros,
                        'notes_created': notes_created,
                        'focus_minutes': focus_minutes,
                    },
                )
                log_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'  Created {log_count} study log entries.'
        ))

    def _create_messages(self):
        """Seed conversations and messages between johndoe and random users."""
        johndoe = User.objects.filter(username=SUPERUSER_USERNAME).first()
        if not johndoe:
            self.stdout.write(self.style.WARNING('  johndoe not found, skipping.'))
            return

        other_users = list(User.objects.exclude(username=SUPERUSER_USERNAME))
        targets = random.sample(other_users, min(24, len(other_users)))

        MESSAGE_PAIRS = [
            ("Hey! Are you going to the study session tomorrow?", "Yeah, planning to! What time works for you?"),
            ("Did you get the notes from today's lecture?", "I did, want me to send them over?"),
            ("Struggling with the algorithms assignment, any tips?", "Start with the dynamic programming section, that's the key part."),
            ("Are you joining the group project meeting?", "Yes, see you there at 3!"),
            ("Have you started the ML coursework yet?", "Just started, it's quite involved. You?"),
            ("Library is packed today, found a spot?", "Yeah grab the third floor, it's quieter up there."),
            ("Did the professor extend the deadline?", "Yes, one extra week apparently!"),
            ("Want to grab coffee before the lecture?", "Sounds good, meet at the usual spot?"),
        ]

        conv_count = 0
        msg_count = 0
        now = timezone.now()

        for i, other_user in enumerate(targets):
            conv = Conversation.objects.create()
            conv.participants.add(johndoe, other_user)

            opening, reply = MESSAGE_PAIRS[i % len(MESSAGE_PAIRS)]
            offset_minutes = random.randint(5, 60)

            # Opening message from the other user
            Message.objects.create(
                conversation=conv,
                sender=other_user,
                content=opening,
                is_read=random.choice([True, False]),
            )

            # Optional reply from johndoe
            if random.random() < 0.7:
                Message.objects.create(
                    conversation=conv,
                    sender=johndoe,
                    content=reply,
                    is_read=True,
                )

            # Occasionally add a follow-up from the other user (unread)
            if random.random() < 0.4:
                Message.objects.create(
                    conversation=conv,
                    sender=other_user,
                    content=fake.sentence(nb_words=random.randint(6, 12)),
                    is_read=False,
                )

            conv_count += 1
            msg_count += conv.messages.count()
            self.stdout.write(f'  Conversation with @{other_user.username}')

        self.stdout.write(self.style.SUCCESS(
            f'  Created {conv_count} conversations, {msg_count} messages.'
        ))

    def _set_gamification_stats(self, users):
        """Set XP, streaks, and daily goals for all users."""
        all_users = list(User.objects.all())
        now = timezone.localtime(timezone.now()).date()

        for user in all_users:
            # XP: proportional to their study logs
            log_count = StudyLog.objects.filter(user=user).count()
            note_count = Note.objects.filter(owner=user).count()
            base_xp = log_count * random.randint(15, 35) + note_count * 10
            user.xp = base_xp + random.randint(0, 200)

            # Streak: check consecutive days with study logs
            streak = 0
            check_date = now
            while True:
                if StudyLog.objects.filter(user=user, date=check_date).exists():
                    streak += 1
                    check_date -= timedelta(days=1)
                else:
                    break
            user.note_streak = streak
            user.longest_note_streak = max(streak, random.randint(streak, streak + 10))
            user.last_note_date = now if streak > 0 else (now - timedelta(days=random.randint(2, 10)))

            # Daily goals: randomize per user
            user.daily_pomo_goal = random.choice([2, 3, 4, 5, 6])
            user.daily_notes_goal = random.choice([1, 2, 3, 4])
            user.daily_focus_goal = random.choice([60, 90, 120, 150, 180])

            user.save(update_fields=[
                'xp', 'note_streak', 'longest_note_streak', 'last_note_date',
                'daily_pomo_goal', 'daily_notes_goal', 'daily_focus_goal',
            ])

        self.stdout.write(self.style.SUCCESS(
            f'  Set gamification stats for {len(all_users)} users.'
        ))
