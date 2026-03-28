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
from timeout.models import Note, StudyLog, Event, Conversation

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

    def _delete_user_data(self, excluded_users):
        """Delete notes and study logs for non-superusers, then remove those users."""
        notes = Note.objects.exclude(owner__in=excluded_users).delete()[0]
        logs = StudyLog.objects.exclude(user__in=excluded_users).delete()[0]
        # Conversations are M2M — delete those that won't have any remaining participants
        convs = Conversation.objects.exclude(participants__in=excluded_users).distinct().delete()[0]
        User.objects.exclude(username=SUPERUSER_USERNAME).delete()
        return notes, logs, convs

    def _delete_all_data(self):
        """Delete all notes, study logs, conversations, and users from the database."""
        notes = Note.objects.all().delete()[0]
        logs = StudyLog.objects.all().delete()[0]
        convs = Conversation.objects.all().delete()[0]
        User.objects.all().delete()
        return notes, logs, convs

    def _delete_global_records(self):
        """Delete global events, Google SocialApp, and Site(id=1)."""
        count = Event.objects.filter(is_global=True).delete()[0]
        SocialApp.objects.filter(provider='google').delete()
        Site.objects.filter(id=1).delete()
        return count

    def handle(self, *args, **options):
        """Delete all seeded data: users, notes, study logs, global events, Site, and SocialApp."""
        keep_super = options['keep_super']
        total_users_before = User.objects.count()
        if total_users_before == 0:
            self.stdout.write(self.style.WARNING('Database is already empty.'))
            return
        if keep_super:
            self.stdout.write('Mode: Removing seeded data (keeping @johndoe)')
            notes_deleted, logs_deleted, convs_deleted = self._delete_user_data(
                User.objects.filter(username=SUPERUSER_USERNAME))
        else:
            self.stdout.write(self.style.WARNING('Mode: Removing ALL data (including superusers)'))
            notes_deleted, logs_deleted, convs_deleted = self._delete_all_data()
        global_events_deleted = self._delete_global_records()
        users_removed = total_users_before - User.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'Removed {users_removed} user(s), {notes_deleted} notes, '
            f'{logs_deleted} study logs, {convs_deleted} conversation(s), '
            f'{global_events_deleted} global events, Site(id=1), and Google SocialApp.'))
        self.stdout.write(f'Remaining users: {User.objects.count()}')
