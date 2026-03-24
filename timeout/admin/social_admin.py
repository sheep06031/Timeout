from django.contrib import admin
from timeout.models import Event, Post, Comment, Like, Bookmark, PostFlag


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Admin interface for Event model."""
    list_display = (
        'id', 'title', 'event_type', 'creator',
        'start_datetime', 'end_datetime', 'is_all_day'
    )
    list_filter = ('event_type', 'is_all_day', 'start_datetime')
    search_fields = ('title', 'description', 'creator__username')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('creator',)
    date_hierarchy = 'start_datetime'

    fieldsets = (
        ('Basic Info', {
            'fields': ('creator', 'title', 'description', 'event_type')
        }),
        ('Date & Time', {
            'fields': (
                'start_datetime', 'end_datetime', 'is_all_day'
            )
        }),
        ('Location', {
            'fields': ('location',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class CommentInline(admin.TabularInline):
    """Inline admin for comments on a post."""
    model = Comment
    extra = 0
    fields = ('author', 'content', 'parent', 'created_at')
    readonly_fields = ('created_at',)
    raw_id_fields = ('author', 'parent')


class LikeInline(admin.TabularInline):
    """Inline admin for likes on a post."""
    model = Like
    extra = 0
    fields = ('user', 'created_at')
    readonly_fields = ('created_at',)
    raw_id_fields = ('user',)


class BookmarkInline(admin.TabularInline):
    """Inline admin for bookmarks on a post."""
    model = Bookmark
    extra = 0
    fields = ('user', 'created_at')
    readonly_fields = ('created_at',)
    raw_id_fields = ('user',)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """Admin interface for Post model."""
    list_display = (
        'id', 'author', 'content_preview', 'event',
        'privacy', 'like_count', 'comment_count', 'created_at'
    )
    list_filter = ('privacy', 'created_at', 'updated_at')
    search_fields = ('content', 'author__username')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('author', 'event')
    date_hierarchy = 'created_at'
    inlines = [CommentInline, LikeInline, BookmarkInline]

    fieldsets = (
        ('Author', {
            'fields': ('author',)
        }),
        ('Content', {
            'fields': ('content', 'event')
        }),
        ('Settings', {
            'fields': ('privacy',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def content_preview(self, obj):
        """Show first 50 characters of content."""
        return obj.content[:50] + '...' if len(
            obj.content
        ) > 50 else obj.content
    content_preview.short_description = 'Content'

    def like_count(self, obj):
        """Count of likes on this post."""
        return obj.likes.count()
    like_count.short_description = 'Likes'

    def comment_count(self, obj):
        """Count of comments on this post."""
        return obj.comments.count()
    comment_count.short_description = 'Comments'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Admin interface for Comment model."""
    list_display = (
        'id', 'author', 'post_preview',
        'content_preview', 'parent', 'created_at'
    )
    list_filter = ('created_at',)
    search_fields = ('content', 'author__username', 'post__content')
    readonly_fields = ('created_at',)
    raw_id_fields = ('author', 'post', 'parent')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Author & Post', {
            'fields': ('author', 'post', 'parent')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )

    def post_preview(self, obj):
        """Show preview of the post this comment is on."""
        content = obj.post.content
        return content[:30] + '...' if len(content) > 30 else content
    post_preview.short_description = 'Post'

    def content_preview(self, obj):
        """Show first 50 characters of comment content."""
        return obj.content[:50] + '...' if len(
            obj.content
        ) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    """Admin interface for Like model."""
    list_display = ('id', 'user', 'post_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'post__content')
    readonly_fields = ('created_at',)
    raw_id_fields = ('user', 'post')
    date_hierarchy = 'created_at'

    def post_preview(self, obj):
        """Show preview of the liked post."""
        content = obj.post.content
        return content[:40] + '...' if len(content) > 40 else content
    post_preview.short_description = 'Post'


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    """Admin interface for Bookmark model."""
    list_display = ('id', 'user', 'post_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'post__content')
    readonly_fields = ('created_at',)
    raw_id_fields = ('user', 'post')
    date_hierarchy = 'created_at'

    def post_preview(self, obj):
        """Show preview of the bookmarked post."""
        content = obj.post.content
        return content[:40] + '...' if len(content) > 40 else content
    post_preview.short_description = 'Post'


@admin.register(PostFlag)
class PostFlagAdmin(admin.ModelAdmin):
    """Admin interface for PostFlag model."""
    list_display = ('id', 'post_preview', 'reporter', 'reason', 'created_at')
    list_filter = ('reason', 'created_at')
    search_fields = ('post__content', 'reporter__username', 'description')
    readonly_fields = ('created_at',)
    raw_id_fields = ('post', 'reporter')
    date_hierarchy = 'created_at'

    def post_preview(self, obj):
        """Show preview of the flagged post."""
        content = obj.post.content
        return content[:40] + '...' if len(content) > 40 else content
    post_preview.short_description = 'Post'
