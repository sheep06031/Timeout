"""
URL patterns for the timeout app's social features.
"""

from django.urls import path
from timeout.views import social_posts, social_profile, social_follow, social_api, moderation

urlpatterns = [
    # Feed
    path('feed/', social_posts.feed, name='social_feed'),
    path('feed/more/', social_posts.feed_more, name='feed_more'),

    # Posts
    path('post/create/', social_posts.create_post, name='create_post'),
    path('post/<int:post_id>/delete/', social_posts.delete_post, name='delete_post'),
    path('post/<int:post_id>/like/', social_posts.like_post, name='like_post'),
    path('post/<int:post_id>/bookmark/', social_posts.bookmark_post, name='bookmark_post'),

    # Comments
    path('post/<int:post_id>/comment/', social_posts.add_comment, name='add_comment'),
    path('comment/<int:comment_id>/delete/', social_posts.delete_comment, name='delete_comment'),

    # Flagging & moderation
    path('post/<int:post_id>/flag/', moderation.flag_post, name='flag_post'),
    path('flag/<int:flag_id>/approve/', moderation.approve_flag, name='approve_flag'),
    path('flag/<int:flag_id>/deny/', moderation.deny_flag, name='deny_flag'),
    path('user/<str:username>/ban/', moderation.ban_user, name='ban_user'),
    path('user/<str:username>/unban/', moderation.unban_user, name='unban_user'),

    # Bookmarks
    path('bookmarks/', social_posts.bookmarks, name='bookmarks'),

    # User profiles and following
    path('user/<str:username>/follow/accept/', social.accept_follow_request, name='accept_follow_request'),
    path('user/<str:username>/follow/reject/', social.reject_follow_request, name='reject_follow_request'),
    path('user/<str:username>/follow/', social.follow_user, name='follow_user'),
    path('user/<str:username>/block/', social.block_user, name='block_user'),
    path('user/<str:username>/', social.user_profile, name='user_profile'),  
    path('status/update/', social.update_status, name='update_status'), 
    path('focus/reset-timer/', social.reset_focus_timer, name='reset_focus_timer'),

    # Friends & follow lists (own)
    path('friends/', social_api.friends_api, name='friends_api'),
    path('followers/', social_api.followers_api, name='followers_api'),
    path('following/', social_api.following_api, name='following_api'),
    path('blocked/', social_follow.blocked_users_api, name='blocked_users_api'),

    # User search
    path('search/', social_follow.search_users, name='search_users'),

    # Friends & follow lists (other users)
    path('user/<str:username>/friends/', social_api.user_friends_api, name='user_friends_api'),
    path('user/<str:username>/followers/', social_api.user_followers_api, name='user_followers_api'),
    path('user/<str:username>/following/', social_api.user_following_api, name='user_following_api'),
]
