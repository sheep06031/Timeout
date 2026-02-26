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
from timeout.models import Event, Post, Comment, Like, Bookmark

User = get_user_model()
fake = Faker()

NUM_USERS = 25
NUM_EVENTS = 15
NUM_POSTS = 40
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

        total_users = User.objects.count()
        total_posts = Post.objects.count()
        total_events = Event.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Users: {total_users}, '
            f'Posts: {total_posts}, Events: {total_events}'
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
