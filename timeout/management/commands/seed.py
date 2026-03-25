"""
Custom management command to seed the database with test data.

Usage:
    python manage.py seed
"""

import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv


from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone
from django.utils.timezone import make_aware
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

NOTE_SUBJECTS = [
    'Algorithms', 'Machine Learning', 'Database Systems',
    'Software Engineering', 'Networks', 'Maths', 'Statistics',
    'Operating Systems', 'AI', 'Web Development',
]

SITE_DOMAIN = '127.0.0.1:8000'
SITE_NAME = 'Timeout Local'

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

POST_TEMPLATES = [
    "Just finished {} - feeling accomplished! 🎉",
    "Anyone else struggling with {}? Need study buddies!",
    "Quick reminder: {} coming up soon!",
    "Amazing lecture on {} today! 🔥",
    "Looking for group members for {} project",
    "Can someone explain {}? I'm totally lost 😅",
    "Procrastination level: {} 😴",
    "Best resources for {}?",
]


def _days_offset(n, hour=9, minute=0, duration_h=1):
    """Return (start, end) datetimes offset by n days from now."""
    start = timezone.now().replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=n)
    return start, start + timedelta(hours=duration_h)


class Command(BaseCommand):
    help = 'Seed the database with site config, Google OAuth app, a superuser, and 25 random student users.'

    def handle(self, *args, **options):
        self.stdout.write('=' * 50 + '\nSEEDING DATABASE\n' + '=' * 50)
        self._setup_site()
        self._setup_google_social_app()
        self._create_superuser()
        users = self._create_users(NUM_USERS)
        self._create_follow_relationships(users)
        events = self._create_events(users)
        posts = self._create_posts(users, events)
        self._create_comments(users, posts)
        self._create_likes_and_bookmarks(users, posts)
        self._create_focus_sessions(users)
        self._create_johndoe_schedule()
        self._create_global_events()
        self._create_notes(users)
        self._create_study_logs(users)
        self._set_gamification_stats(users)
        self._create_messages()
        self._print_summary()

    def _print_summary(self):
        """Print final counts of seeded data."""
        counts = {
            'Users': User.objects.count(),
            'Posts': Post.objects.count(),
            'Events': Event.objects.count(),
            'Notes': Note.objects.count(),
            'StudyLogs': StudyLog.objects.count(),
        }
        summary = ', '.join(f'{k}: {v}' for k, v in counts.items())
        self.stdout.write(self.style.SUCCESS(f'\nDone! {summary}'))

    def _setup_site(self):
        """Ensure Site(id=1) exists with the correct domain."""
        self.stdout.write('\n[1] Setting up Site...')
        Site.objects.all().delete()
        Site.objects.create(id=1, domain=SITE_DOMAIN, name=SITE_NAME)
        self.stdout.write(self.style.SUCCESS(f'  Site(id=1, domain="{SITE_DOMAIN}") ready.'))

    def _setup_google_social_app(self):
        """Create the Google SocialApp from environment variables."""
        self.stdout.write('\n[2] Setting up Google SocialApp...')
        load_dotenv()
        client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
        secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')

        if not client_id or not secret:
            self.stdout.write(self.style.WARNING(
                '  GOOGLE_CLIENT_ID and/or GOOGLE_CLIENT_SECRET not set.\n'
                '  Skipping Google SocialApp creation.'
            ))
            return

        # get_or_create to avoid duplicate SocialApp records on repeated seeding
        app, created = SocialApp.objects.get_or_create( 
            provider='google',
            defaults={'name': 'Google', 'client_id': client_id, 'secret': secret},
        )
        if not created:
            app.client_id, app.secret = client_id, secret
            app.save()

        app.sites.add(Site.objects.get(id=1))
        label = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'  {label} Google SocialApp and linked to site.'))

    def _create_superuser(self):
        """Create the @johndoe superuser if absent."""
        self.stdout.write('\n[3] Creating superuser...')
        if User.objects.filter(username=SUPERUSER_USERNAME).exists():
            self.stdout.write(self.style.WARNING(f'  @{SUPERUSER_USERNAME} already exists, skipping.'))
            return
        try:
            User.objects.create_superuser(
                username=SUPERUSER_USERNAME, email=SUPERUSER_EMAIL,
                password=SUPERUSER_PASSWORD, first_name='John', last_name='Doe',
                university='Galatasaray University', year_of_study=3,
                bio='Admin account for the Timeout platform.',
                academic_interests='Computer Science, Data Science',
                management_style='early_bird',
            )
            self.stdout.write(self.style.SUCCESS(f'  Superuser @{SUPERUSER_USERNAME} created.'))
        except IntegrityError as e:
            self.stdout.write(self.style.ERROR(f'  Failed to create superuser: {e}'))

    def _create_users(self, count):
        """Create regular user accounts with Faker data."""
        self.stdout.write(f'\n[4] Creating {count} users...')
        users, existing = [], set(User.objects.values_list('username', flat=True))
        for i in range(count):
            username = self._unique_username(existing)
            user = self._create_single_user(username, i, count)
            if user:
                users.append(user)
        return users

    def _unique_username(self, existing):
        """Generate a username not already in use."""
        username = fake.user_name()
        while username in existing:
            username = fake.user_name() + str(random.randint(10, 99))
        existing.add(username)
        return username

    def _create_single_user(self, username, index, total):
        """Create one user with randomized profile data."""
        try:
            user = User.objects.create_user(
                username=username, email=fake.unique.email(),
                password=DEFAULT_PASSWORD,
                first_name=fake.first_name(), last_name=fake.last_name(),
                middle_name=fake.first_name() if random.random() < 0.3 else '',
                university=random.choice(UNIVERSITIES),
                year_of_study=random.randint(1, 5),
                bio=fake.sentence(nb_words=12),
                academic_interests=', '.join(random.sample(INTERESTS, k=random.randint(1, 4))),
                privacy_private=random.choice([True, False]),
                management_style=random.choice(MANAGEMENT_STYLES),
            )
            self.stdout.write(f'  [{index + 1}/{total}] Created @{username}')
            return user
        except IntegrityError as e:
            self.stdout.write(self.style.ERROR(f'  [{index + 1}/{total}] Failed @{username}: {e}'))
            return None

    def _create_follow_relationships(self, users):
        """Establish random follow relationships between all users."""
        self.stdout.write('\n[5] Creating follow relationships...')
        all_users = list(User.objects.all())
        follow_count = 0
        for user in all_users:
            others = [u for u in all_users if u != user]
            to_follow = random.sample(others, k=min(random.randint(2, 8), len(others)))
            user.following.add(*to_follow)
            follow_count += len(to_follow)
        self.stdout.write(self.style.SUCCESS(f'  Created {follow_count} follow relationships.'))

    def _create_events(self, users):
        """Create calendar events."""
        self.stdout.write(f'\n[6] Creating {NUM_EVENTS} events...')
        events, event_types = [], ['deadline', 'exam', 'class', 'meeting', 'study_session']
        for i in range(NUM_EVENTS):
            creator = random.choice(users)
            start = timezone.now() + timedelta(days=random.randint(-7, 30), hours=random.randint(8, 20))
            event = Event.objects.create(
                creator=creator, title=fake.sentence(nb_words=4).rstrip('.'),
                description=fake.paragraph(), event_type=random.choice(event_types),
                start_datetime=start, end_datetime=start + timedelta(hours=random.randint(1, 3)),
                location=fake.city() if random.random() < 0.5 else '',
                is_all_day=random.random() < 0.2,
            )
            events.append(event)
            self.stdout.write(f'  [{i + 1}/{NUM_EVENTS}] Created event: {event.title}')
        return events

    def _create_posts(self, users, events):
        """Create social posts."""
        self.stdout.write(f'\n[7] Creating {NUM_POSTS} posts...')
        posts = []
        for i in range(NUM_POSTS):
            author = random.choice(users)
            content = self._random_post_content()
            post = Post.objects.create(
                author=author, content=content,
                event=random.choice(events) if (random.random() < 0.3 and events) else None,
                privacy=random.choice(['public', 'followers_only']),
            )
            posts.append(post)
            self.stdout.write(f'  [{i + 1}/{NUM_POSTS}] Created post by @{author.username}')
        return posts

    def _random_post_content(self):
        """Generate random post content from templates or faker."""
        if random.random() < 0.7:
            return random.choice(POST_TEMPLATES).format(fake.sentence(nb_words=3).rstrip('.'))
        return fake.paragraph(nb_sentences=random.randint(1, 3))

    def _create_comments(self, users, posts):
        """Create comments on posts."""
        self.stdout.write('\n[8] Creating comments...')
        count = 0
        for post in posts:
            for _ in range(random.randint(0, 5)):
                Comment.objects.create(
                    author=random.choice(users), post=post,
                    content=fake.sentence(nb_words=random.randint(5, 15)),
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f'  Created {count} comments.'))

    def _create_likes_and_bookmarks(self, users, posts):
        """Create likes and bookmarks."""
        self.stdout.write('\n[9] Creating likes and bookmarks...')
        like_count, bookmark_count = 0, 0
        for post in posts:
            likers = random.sample(users, random.randint(0, min(10, len(users))))
            for user in likers:
                Like.objects.get_or_create(user=user, post=post)
                like_count += 1
            if random.random() < 0.3:
                bookmarkers = random.sample(users, min(random.randint(1, 3), len(users)))
                for user in bookmarkers:
                    Bookmark.objects.get_or_create(user=user, post=post)
                    bookmark_count += 1
        self.stdout.write(self.style.SUCCESS(f'  Created {like_count} likes and {bookmark_count} bookmarks.'))

    def _create_focus_sessions(self, users):
        """Create focus sessions for johndoe and random users."""
        self.stdout.write('\n[10] Creating focus sessions...')
        johndoe = User.objects.filter(username=SUPERUSER_USERNAME).first()
        targets = ([johndoe] if johndoe else []) + random.sample(users, min(5, len(users)))
        count, now = 0, timezone.now()
        for user in targets:
            for day_offset in range(7):
                if random.random() < 0.7:
                    count += self._create_single_focus_session(user, now, day_offset)
        self.stdout.write(self.style.SUCCESS(f'  Created {count} focus sessions.'))

    def _create_single_focus_session(self, user, now, day_offset):
        """Create one random focus session and return 1."""
        started_at = now - timedelta(
            days=day_offset, hours=random.randint(0, 10), minutes=random.randint(0, 59),
        )
        duration = random.randint(10 * 60, 120 * 60)
        FocusSession.objects.create(
            user=user, started_at=started_at,
            ended_at=started_at + timedelta(seconds=duration),
            duration_seconds=duration,
        )
        return 1

    def _create_johndoe_schedule(self):
        """Create a realistic student schedule for johndoe."""
        self.stdout.write('\n[11] Creating johndoe schedule...')
        johndoe = User.objects.filter(username=SUPERUSER_USERNAME).first()
        if not johndoe:
            self.stdout.write(self.style.WARNING('  johndoe not found, skipping.'))
            return

        events = []
        events.extend(self._johndoe_weekly_classes(johndoe))
        events.extend(self._johndoe_exams(johndoe))
        events.extend(self._johndoe_deadlines(johndoe))
        events.extend(self._johndoe_study_meetings(johndoe))

        created = 0
        for ev in events:
            if ev['end_datetime'] <= ev['start_datetime']:
                ev['end_datetime'] = ev['start_datetime'] + timedelta(hours=1)
            Event.objects.create(**ev)
            created += 1
        self.stdout.write(self.style.SUCCESS(f'  Created {created} events for @{SUPERUSER_USERNAME}.'))

    def _johndoe_weekly_classes(self, johndoe):
        """Generate 8 weeks of recurring class events."""
        classes = [
            ('Software Engineering Group Project', 0, 'Bush House, KCL', 10, 0, 2),
            ('Database Systems', 1, 'Waterloo Campus', 9, 0, 1),
            ('Algorithms & Complexity', 2, 'Strand Building, KCL', 14, 0, 1),
            ('Machine Learning', 3, 'Bush House, KCL', 13, 0, 2),
        ]
        events, today_wd = [], timezone.now().weekday()
        for title, weekday, loc, hour, minute, dur in classes:
            days_to_next = (weekday - today_wd) % 7
            for week in range(-3, 5):
                offset = days_to_next + week * 7
                start, end = _days_offset(offset, hour, minute, dur)
                events.append(dict(
                    creator=johndoe, title=title, event_type='class',
                    start_datetime=start, end_datetime=end,
                    location=loc, visibility='private',
                    status='completed' if offset < 0 else 'upcoming',
                ))
        return events

    def _johndoe_exams(self, johndoe):
        """Generate exam events for johndoe."""
        exams = [
            ('Algorithms & Complexity Exam', 18, 9, 3, 'Exam Hall A, KCL'),
            ('Database Systems Exam', 32, 14, 2, 'Great Hall, KCL'),
            ('Machine Learning Final Exam', 45, 10, 3, 'Exam Hall B, KCL'),
        ]
        events = []
        for title, day, hour, dur, loc in exams:
            start, end = _days_offset(day, hour, 0, dur)
            events.append(dict(
                creator=johndoe, title=title, event_type='exam',
                start_datetime=start, end_datetime=end,
                location=loc, visibility='private', status='upcoming',
            ))
        return events

    def _johndoe_deadlines(self, johndoe):
        """Generate deadline events for johndoe."""
        deadlines = [
            ('SEG Coursework Submission', 7),
            ('ML Assignment 2 Due', 14),
            ('Database ER Diagram Submission', 21),
            ('SEG Final Report', 50),
        ]
        events = []
        for title, day in deadlines:
            start, _ = _days_offset(day, 23, 59, 0)
            events.append(dict(
                creator=johndoe, title=title, event_type='deadline',
                start_datetime=start, end_datetime=start + timedelta(minutes=1),
                location='', visibility='private', status='upcoming',
            ))
        return events

    def _johndoe_study_meetings(self, johndoe):
        """Generate study sessions and meetings for johndoe."""
        items = [
            ('Algorithms Revision', 'study_session', 'Library, KCL', 15, 14, 2),
            ('ML Past Papers', 'study_session', 'Library, KCL', 40, 10, 3),
            ('DB Exam Prep', 'study_session', 'Library, KCL', 28, 16, 2),
            ('Group Study – SEG', 'study_session', 'Library, KCL', 5, 15, 2),
            ('SEG Team Meeting', 'meeting', 'Bush House, KCL', 3, 11, 1),
            ('Supervisor Check-in', 'meeting', 'Bush House, KCL', 10, 14, 1),
            ('Career Fair Prep', 'meeting', 'Bush House, KCL', 6, 13, 1),
        ]
        events = []
        for title, etype, loc, day, hour, dur in items:
            start, end = _days_offset(day, hour, 0, dur)
            events.append(dict(
                creator=johndoe, title=title, event_type=etype,
                start_datetime=start, end_datetime=end,
                location=loc, visibility='private', status='upcoming',
            ))
        return events

    def _create_global_events(self):
        """Create traditional recurring global events."""
        self.stdout.write('\n[12] Creating global recurring events...')
        global_events = [
            ("Christmas Day", 12, 25), ("Valentine's Day", 2, 14),
            ("New Year's Day", 1, 1), ("Halloween", 10, 31),
            ("New Year's Eve", 12, 31), ("Christmas Eve", 12, 24),
        ]
        year = timezone.now().year
        for title, month, day in global_events:
            start = make_aware(datetime(year, month, day, 0, 0))
            end = make_aware(datetime(year, month, day, 23, 59))
            Event.objects.get_or_create(
                title=title, start_datetime=start, end_datetime=end,
                is_global=True, recurrence="yearly",
                defaults={
                    "creator": None, "description": f"Global event: {title}",
                    "visibility": Event.Visibility.PUBLIC,
                },
            )
            self.stdout.write(f'  Global event: {title} ({start.date()})')
        self.stdout.write(self.style.SUCCESS(f'  Created {len(global_events)} global recurring events.'))

    def _create_notes(self, users):
        """Create notes with categories and time spent for all users."""
        self.stdout.write('\n[13] Creating notes for all users...')
        all_users = list(User.objects.all())
        now, count = timezone.now(), 0
        for user in all_users:
            user_events = list(user.created_events.all()[:10])
            for _ in range(random.randint(*NUM_NOTES_PER_USER)):
                self._create_single_note(user, user_events, now)
                count += 1
        self.stdout.write(self.style.SUCCESS(f'  Created {count} notes across {len(all_users)} users.'))

    def _create_single_note(self, user, user_events, now):
        """Create one note with random category, title, content, and metadata."""
        category = random.choice(NOTE_CATEGORIES)
        subject = random.choice(NOTE_SUBJECTS)
        title = self._build_note_title(category, subject)
        content = self._build_note_content(subject)
        due_date = self._random_due_date(category, now)
        created_at = now - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))
        event = random.choice(user_events) if (user_events and random.random() < 0.3) else None

        note = Note(
            owner=user, title=title[:200], content=content[:5000],
            category=category, event=event, is_pinned=random.random() < 0.15,
            due_date=due_date,
            time_spent_minutes=random.choice([0, 0, 0, 25, 25, 50, 50, 75, 100, 125, 150]),
        )
        note.save()
        Note.objects.filter(pk=note.pk).update(created_at=created_at)

    def _build_note_title(self, category, subject):
        """Generate a title from the category template."""
        template = random.choice(NOTE_TITLES[category])
        try:
            if '{}' not in template:
                return template
            if 'Week' in template:
                return template.format(random.randint(1, 12), subject)
            return template.format(subject)
        except (IndexError, KeyError):
            return f'{subject} Notes'

    def _build_note_content(self, subject):
        """Compose note content from random snippets."""
        parts = []
        for _ in range(random.randint(1, 3)):
            snippet = random.choice(NOTE_CONTENT_SNIPPETS)
            parts.append(snippet.format(subject) if '{}' in snippet else snippet)
        return '\n\n'.join(parts)

    def _random_due_date(self, category, now):
        """Return a due date or None based on category."""
        if category in ('todo', 'study_plan') and random.random() < 0.6:
            return now + timedelta(days=random.randint(-3, 14), hours=random.randint(8, 23))
        if random.random() < 0.15:
            return now + timedelta(days=random.randint(1, 30))
        return None

    def _create_study_logs(self, users):
        """Create study log entries for heatmap data."""
        self.stdout.write('\n[14] Creating study logs (heatmap data)...')
        all_users = list(User.objects.all())
        today = timezone.localtime(timezone.now()).date()
        count = 0
        for user in all_users:
            active_prob = random.choice([0.25, 0.5, 0.75])
            count += self._create_user_study_logs(user, today, active_prob)
        self.stdout.write(self.style.SUCCESS(f'  Created {count} study log entries.'))

    def _create_user_study_logs(self, user, today, active_prob):
        """Create study logs for one user over HEATMAP_WEEKS."""
        count = 0
        for day_offset in range(HEATMAP_WEEKS * 7):
            date = today - timedelta(days=day_offset)
            if random.random() > active_prob:
                continue
            if date.weekday() >= 5 and random.random() < 0.4:
                continue
            pomodoros = random.choices([0, 1, 2, 3, 4, 5, 6], weights=[10, 20, 25, 20, 15, 7, 3])[0]
            notes_created = random.choices([0, 1, 2, 3, 4], weights=[20, 35, 25, 15, 5])[0]
            focus_minutes = pomodoros * random.randint(20, 30) + random.randint(0, 15)
            if pomodoros == 0 and notes_created == 0 and focus_minutes == 0:
                continue
            StudyLog.objects.get_or_create(
                user=user, date=date,
                defaults={'pomodoros': pomodoros, 'notes_created': notes_created, 'focus_minutes': focus_minutes},
            )
            count += 1
        return count

    def _create_messages(self):
        """Seed conversations and messages between johndoe and random users."""
        self.stdout.write('\n[15] Creating messages for johndoe...')
        johndoe = User.objects.filter(username=SUPERUSER_USERNAME).first()
        if not johndoe:
            self.stdout.write(self.style.WARNING('  johndoe not found, skipping.'))
            return
        other_users = list(User.objects.exclude(username=SUPERUSER_USERNAME))
        targets = random.sample(other_users, min(24, len(other_users)))
        conv_count, msg_count = 0, 0
        for i, other in enumerate(targets):
            conv_count += 1
            msg_count += self._create_conversation(johndoe, other, i)
        self.stdout.write(self.style.SUCCESS(f'  Created {conv_count} conversations, {msg_count} messages.'))

    def _create_conversation(self, johndoe, other_user, index):
        """Create a single conversation with 1-3 messages."""
        conv = Conversation.objects.create()
        conv.participants.add(johndoe, other_user)
        opening, reply = MESSAGE_PAIRS[index % len(MESSAGE_PAIRS)]
        Message.objects.create(
            conversation=conv, sender=other_user,
            content=opening, is_read=random.choice([True, False]),
        )
        if random.random() < 0.7:
            Message.objects.create(
                conversation=conv, sender=johndoe, content=reply, is_read=True,
            )
        if random.random() < 0.4:
            Message.objects.create(
                conversation=conv, sender=other_user,
                content=fake.sentence(nb_words=random.randint(6, 12)), is_read=False,
            )
        self.stdout.write(f'  Conversation with @{other_user.username}')
        return conv.messages.count()

    def _set_gamification_stats(self, users):
        """Set XP, streaks, and daily goals for all users."""
        self.stdout.write('\n[16] Setting gamification stats...')
        all_users = list(User.objects.all())
        today = timezone.localtime(timezone.now()).date()
        for user in all_users:
            self._set_user_gamification(user, today)
        self.stdout.write(self.style.SUCCESS(f'  Set gamification stats for {len(all_users)} users.'))

    def _set_user_gamification(self, user, today):
        """Set XP, streak, and goals for a single user."""
        log_count = StudyLog.objects.filter(user=user).count()
        note_count = Note.objects.filter(owner=user).count()
        user.xp = log_count * random.randint(15, 35) + note_count * 10 + random.randint(0, 200)

        streak = self._calculate_streak(user, today)
        user.note_streak = streak
        user.longest_note_streak = max(streak, random.randint(streak, streak + 10))
        user.last_note_date = today if streak > 0 else (today - timedelta(days=random.randint(2, 10)))
        user.daily_pomo_goal = random.choice([2, 3, 4, 5, 6])
        user.daily_notes_goal = random.choice([1, 2, 3, 4])
        user.daily_focus_goal = random.choice([60, 90, 120, 150, 180])
        user.save(update_fields=[
            'xp', 'note_streak', 'longest_note_streak', 'last_note_date',
            'daily_pomo_goal', 'daily_notes_goal', 'daily_focus_goal',
        ])

    def _calculate_streak(self, user, today):
        """Count consecutive days with study logs ending at today."""
        streak, check_date = 0, today
        while StudyLog.objects.filter(user=user, date=check_date).exists():
            streak += 1
            check_date -= timedelta(days=1)
        return streak
