"""
unseed.py - Management command to clear seeded data from the database.

Deletes all users (cascading to events, posts, comments, etc.), notes,
study logs, global events, the allauth Site record, and the Google SocialApp.

Usage:
    python manage.py unseed
    python manage.py unseed --keep-super  # Keep superuser @johndoe
"""

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

from allauth.socialaccount.models import SocialApp
from timeout.models import Note, StudyLog, Event

User = get_user_model()

SUPERUSER_USERNAME = 'johndoe'


class Command(BaseCommand):
    """Management command to remove all seeded data from the database."""
    help = 'Remove all seeded data from the database (including superuser by default).'

    def add_arguments(self, parser):
        """Add optional argument to keep the superuser."""
        parser.add_argument(
            '--keep-super',
            action='store_true',
            dest='keep_super',
            help='Keep the superuser @johndoe instead of deleting.',
        )

    def handle(self, *args, **options):
        """Delete all seeded data: users, notes, study logs, global events, Site, and SocialApp."""
        keep_super = options['keep_super']
        total_users_before = User.objects.count()
        if total_users_before == 0:
            self.stdout.write(self.style.WARNING('Database is already empty.'))
            return
        if keep_super:
            self.stdout.write('Mode: Removing seeded data (keeping @johndoe)')
            excluded_users = User.objects.filter(username=SUPERUSER_USERNAME)
            notes_deleted = Note.objects.exclude(owner__in=excluded_users).delete()[0]
            logs_deleted = StudyLog.objects.exclude(user__in=excluded_users).delete()[0]
            User.objects.exclude(username=SUPERUSER_USERNAME).delete()
        else:
            self.stdout.write(self.style.WARNING(
                'Mode: Removing ALL data (including superusers)'))
            notes_deleted = Note.objects.all().delete()[0]
            logs_deleted = StudyLog.objects.all().delete()[0]
            User.objects.all().delete()

        global_events_deleted = Event.objects.filter(is_global=True).delete()[0]
        SocialApp.objects.filter(provider='google').delete()
        Site.objects.filter(id=1).delete()

        total_users_after = User.objects.count()
        users_removed = total_users_before - total_users_after

        self.stdout.write(self.style.SUCCESS(
            f'Removed {users_removed} user(s), {notes_deleted} notes, '
            f'{logs_deleted} study logs, {global_events_deleted} global events, '
            f'Site(id=1), and Google SocialApp.'))
        self.stdout.write(f'Remaining users: {total_users_after}')
