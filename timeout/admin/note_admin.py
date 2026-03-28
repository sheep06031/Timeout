"""
note_admin.py - Admin interface for Note model in Timeout application.

Provides a customized admin view for managing user notes, including:
    - Displaying key fields in the list view (owner, title preview, category, etc.)
    - Filtering by category, pinned status, and creation date
    - Searching by title, content, and owner's username
    - Readonly timestamps and raw ID fields for related models
"""

from django.contrib import admin
from timeout.models import Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    """Admin interface for Note model."""

    list_display = (
        'id', 'owner', 'title_preview', 'category',
        'is_pinned', 'event', 'created_at',
    )
    list_filter = ('category', 'is_pinned', 'created_at')
    search_fields = ('title', 'content', 'owner__username')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('owner', 'event')

    fieldsets = (
        ('Owner', {
            'fields': ('owner',)
        }),
        ('Content', {
            'fields': ('title', 'content', 'category', 'event')
        }),
        ('Settings', {
            'fields': ('is_pinned',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def title_preview(self, obj):
        """Show first 50 characters of title."""
        if len(obj.title) > 50:
            return obj.title[:50] + '...'
        return obj.title

    title_preview.short_description = 'Title' # Display full title in admin list view
