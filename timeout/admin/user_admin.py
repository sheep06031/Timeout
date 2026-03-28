"""
user_admin.py - Admin interface for User model in Timeout application.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from timeout.models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""
    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'university', 'year_of_study', 'is_staff',
    )
    list_filter = BaseUserAdmin.list_filter + (
        'university', 'year_of_study', 'management_style', 'privacy_private',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'university')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile', {
            'fields': (
                'middle_name', 'bio', 'university', 'year_of_study',
                'profile_picture', 'academic_interests',
            ),
        }),
        ('Preferences', {
            'fields': ('privacy_private', 'management_style'),
        }),
        ('Social', {
            'fields': ('following',),
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Profile', {
            'fields': (
                'email', 'first_name', 'last_name', 'university', 'year_of_study',
            ),
        }),
    )
