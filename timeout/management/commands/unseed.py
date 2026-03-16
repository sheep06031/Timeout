"""
Custom management command to clear seeded data from the database.

Usage:
    python manage.py unseed              # Remove everything including superusers
    python manage.py unseed --keep-super  # Keep superuser @johndoe
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from timeout.models import Note, StudyLog

User = get_user_model()

SUPERUSER_USERNAME = 'johndoe'


class Command(BaseCommand):
    help = 'Remove all seeded data from the database (including superuser by default).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-super',
            action='store_true',
            dest='keep_super',
            help='Keep the superuser @johndoe instead of deleting.',
        )

    def handle(self, *args, **options):
        keep_super = options['keep_super']
        total_users_before = User.objects.count()

        if total_users_before == 0:
            self.stdout.write(self.style.WARNING('Database is already empty.'))
            return

        # Clear notes and study logs first (cascade would handle it, but be explicit)
        if keep_super:
            self.stdout.write('Mode: Removing seeded data (keeping @johndoe)')
            excluded_users = User.objects.filter(username=SUPERUSER_USERNAME)
            notes_deleted = Note.objects.exclude(owner__in=excluded_users).delete()[0]
            logs_deleted = StudyLog.objects.exclude(user__in=excluded_users).delete()[0]
            User.objects.exclude(username=SUPERUSER_USERNAME).delete()
        else:
            self.stdout.write(self.style.WARNING(
                'Mode: Removing ALL data (including superusers)'
            ))
            notes_deleted = Note.objects.all().delete()[0]
            logs_deleted = StudyLog.objects.all().delete()[0]
            User.objects.all().delete()

        total_users_after = User.objects.count()
        users_removed = total_users_before - total_users_after

        self.stdout.write(self.style.SUCCESS(
            f'Removed {users_removed} user(s), {notes_deleted} notes, {logs_deleted} study logs.'
        ))
        self.stdout.write(f'Remaining users: {total_users_after}')
