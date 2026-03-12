"""
Custom management command to clear seeded data from the database.

Usage:
    python manage.py unseed          # Keep superuser @johndoe
    python manage.py unseed --all    # Remove everyone including superusers
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from timeout.models import Note, StudyLog

User = get_user_model()

SUPERUSER_USERNAME = 'johndoe'


class Command(BaseCommand):
    help = 'Remove all seeded data from the database (preserves @johndoe by default).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            dest='remove_all',
            help='Remove ALL users including the superuser @johndoe.',
        )

    def handle(self, *args, **options):
        remove_all = options['remove_all']
        total_users_before = User.objects.count()

        if total_users_before == 0:
            self.stdout.write(self.style.WARNING('Database is already empty.'))
            return

        # Clear notes and study logs first (cascade would handle it, but be explicit)
        if remove_all:
            self.stdout.write(self.style.WARNING(
                'Mode: Removing ALL data (including superusers)'
            ))
            notes_deleted = Note.objects.all().delete()[0]
            logs_deleted = StudyLog.objects.all().delete()[0]
            User.objects.all().delete()
        else:
            self.stdout.write('Mode: Removing seeded data (keeping @johndoe)')
            excluded_users = User.objects.filter(username=SUPERUSER_USERNAME)
            notes_deleted = Note.objects.exclude(owner__in=excluded_users).delete()[0]
            logs_deleted = StudyLog.objects.exclude(user__in=excluded_users).delete()[0]
            User.objects.exclude(username=SUPERUSER_USERNAME).delete()

        total_users_after = User.objects.count()
        users_removed = total_users_before - total_users_after

        self.stdout.write(self.style.SUCCESS(
            f'Removed {users_removed} user(s), {notes_deleted} notes, {logs_deleted} study logs.'
        ))
        self.stdout.write(f'Remaining users: {total_users_after}')
