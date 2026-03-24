from django.urls import path
from timeout.views import social

urlpatterns = [
    # Feed
    path('feed/', social.feed, name='social_feed'),

    # Posts
    path('post/create/', social.create_post, name='create_post'),
    path('post/<int:post_id>/delete/', social.delete_post, name='delete_post'),
    path('post/<int:post_id>/like/', social.like_post, name='like_post'),
    path('post/<int:post_id>/bookmark/', social.bookmark_post, name='bookmark_post'),

    # Comments
    path('post/<int:post_id>/comment/', social.add_comment, name='add_comment'),
    path('comment/<int:comment_id>/delete/', social.delete_comment, name='delete_comment'),

    # Flagging
    path('post/<int:post_id>/flag/', social.flag_post, name='flag_post'),

    # Moderation
    path('user/<str:username>/ban/', social.ban_user, name='ban_user'),
    path('user/<str:username>/unban/', social.unban_user, name='unban_user'),

    # Bookmarks
    path('bookmarks/', social.bookmarks, name='bookmarks'),

    # User profiles and following
    path('user/<str:username>/', social.user_profile, name='user_profile'),
    path('user/<str:username>/follow/', social.follow_user, name='follow_user'),
    path('user/<str:username>/follow/accept/', social.accept_follow_request, name='accept_follow_request'),
    path('user/<str:username>/follow/reject/', social.reject_follow_request, name='reject_follow_request'),
    path('status/update/', social.update_status, name='update_status'),
    path('friends/', social.friends_api, name='friends_api'),
    path('user/<str:username>/friends/', social.user_friends_api, name='user_friends_api'),

    # Follow lists (own)
    path('followers/', social.followers_api, name='followers_api'),
    path('following/', social.following_api, name='following_api'),

    # User search
    path('search/', social.search_users, name='search_users'),
    # Follow lists (other users)
    path('user/<str:username>/followers/', social.user_followers_api, name='user_followers_api'),
    path('user/<str:username>/following/', social.user_following_api, name='user_following_api'),
]
