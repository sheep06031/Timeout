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

    # Bookmarks
    path('bookmarks/', social.bookmarks, name='bookmarks'),

    # User profiles and following
    path('user/<str:username>/', social.user_profile, name='user_profile'),
    path('user/<str:username>/follow/', social.follow_user, name='follow_user'),
    path('status/update/', social.update_status, name='update_status'),

    # Follow lists (own)
    path('followers/', social.followers_api, name='followers_api'),
    path('following/', social.following_api, name='following_api'),

<<<<<<< HEAD
    # User search
    path('search/', social.search_users, name='search_users'),
=======
    # Follow lists (other users)
    path('user/<str:username>/followers/', social.user_followers_api, name='user_followers_api'),
    path('user/<str:username>/following/', social.user_following_api, name='user_following_api'),
>>>>>>> origin/main
]
