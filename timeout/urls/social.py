"""
URL patterns for the timeout app's social features.
Includes:
- feed: Main social feed showing posts from followed users.
- create_post: Endpoint to create a new post.
- delete_post: Endpoint to delete a post.
- like_post: Endpoint to like/unlike a post.
- bookmark_post: Endpoint to bookmark/unbookmark a post.
- add_comment: Endpoint to add a comment to a post.
- delete_comment: Endpoint to delete a comment.
- flag_post: Endpoint to flag a post for moderation.
- approve_flag: Endpoint for moderators to approve a flagged post.
- deny_flag: Endpoint for moderators to deny a flagged post.
- ban_user: Endpoint for moderators to ban a user.
- unban_user: Endpoint for moderators to unban a user.
- bookmarks: View to show the current user's bookmarked posts.
- user_profile: View to show a user's profile and their posts.
- follow_user: Endpoint to follow/unfollow a user.
- block_user: Endpoint to block/unblock a user.
- accept_follow_request: Endpoint to accept a follow request for private accounts.
- reject_follow_request: Endpoint to reject a follow request for private accounts.
- update_status: Endpoint to update the user's current status message.
- reset_focus_timer: Endpoint to reset the user's focus timer (if implemented).
- followers_api: API endpoint to get the current user's followers with follow-back status.
- following_api: API endpoint to get the users that the current user is following.
- user_followers_api: API endpoint to get a specific user's followers (respects privacy).
- user_following_api: API endpoint to get a specific user's following list (respects privacy).
- friends_api: API endpoint to get the current user's mutual follows (friends).
- user_friends_api: API endpoint to get a specific user's mutual follows (respects privacy).
"""
from django.urls import path
from timeout.views import social, social_api, moderation

urlpatterns = [
    # Feed
    path('feed/', social.feed, name='social_feed'),
    path('feed/more/', social.feed_more, name='feed_more'),

    # Posts
    path('post/create/', social.create_post, name='create_post'),
    path('post/<int:post_id>/delete/', social.delete_post, name='delete_post'),
    path('post/<int:post_id>/like/', social.like_post, name='like_post'),
    path('post/<int:post_id>/bookmark/', social.bookmark_post, name='bookmark_post'),

    # Comments
    path('post/<int:post_id>/comment/', social.add_comment, name='add_comment'),
    path('comment/<int:comment_id>/delete/', social.delete_comment, name='delete_comment'),

    # Flagging & moderation
    path('post/<int:post_id>/flag/', moderation.flag_post, name='flag_post'),
    path('flag/<int:flag_id>/approve/', moderation.approve_flag, name='approve_flag'),
    path('flag/<int:flag_id>/deny/', moderation.deny_flag, name='deny_flag'),
    path('user/<str:username>/ban/', moderation.ban_user, name='ban_user'),
    path('user/<str:username>/unban/', moderation.unban_user, name='unban_user'),

    # Bookmarks
    path('bookmarks/', social.bookmarks, name='bookmarks'),

    # User profiles and following
    path('user/<str:username>/', social.user_profile, name='user_profile'),
    path('user/<str:username>/follow/', social.follow_user, name='follow_user'),
    path('user/<str:username>/block/', social.block_user, name='block_user'),
    path('user/<str:username>/follow/accept/', social.accept_follow_request, name='accept_follow_request'),
    path('user/<str:username>/follow/reject/', social.reject_follow_request, name='reject_follow_request'),
    path('status/update/', social.update_status, name='update_status'),
    path('focus/reset-timer/', social.reset_focus_timer, name='reset_focus_timer'),

    # Friends & follow lists (own)
    path('friends/', social_api.friends_api, name='friends_api'),
    path('followers/', social_api.followers_api, name='followers_api'),
    path('following/', social_api.following_api, name='following_api'),
    path('blocked/', social.blocked_users_api, name='blocked_users_api'),


    # User search
    path('search/', social.search_users, name='search_users'),

    # Friends & follow lists (other users)
    path('user/<str:username>/friends/', social_api.user_friends_api, name='user_friends_api'),
    path('user/<str:username>/followers/', social_api.user_followers_api, name='user_followers_api'),
    path('user/<str:username>/following/', social_api.user_following_api, name='user_following_api'),
]
