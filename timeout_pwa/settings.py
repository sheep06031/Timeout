"""
Django settings for timeout_pwa project.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-change-this-in-production-use-environment-variable'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # Third-party apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    # Local apps
    'timeout',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'timeout_pwa.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'timeout_pwa.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Custom User Model
AUTH_USER_MODEL = 'timeout.User'


# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]


# Sites framework (required by allauth)
SITE_ID = 1


# Password hashing — Argon2 is the primary hasher
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
]


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'

# Directory where collectstatic will collect static files for deployment
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Additional locations of static files (for development)
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]


# Media files (User uploaded content)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Login/Logout URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/complete-profile/'
LOGOUT_REDIRECT_URL = 'landing'


# =============================================================================
# django-allauth configuration
# =============================================================================

# Account settings
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_SIGNUP_REDIRECT_URL = '/complete-profile/'
# ACCOUNT_USERNAME_REQUIRED = False is expressed via ACCOUNT_SIGNUP_FIELDS above (that setting is deprecated in allauth >= 0.56; SIGNUP_FIELDS is the new API)
ACCOUNT_ADAPTER = 'timeout.adapters.TimeoutAccountAdapter'

# Social account settings
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_ADAPTER = 'timeout.adapters.TimeoutSocialAccountAdapter'
SOCIALACCOUNT_STORE_TOKENS = True

# The button click goes straight to Google's OAuth consent screen.
SOCIALACCOUNT_LOGIN_ON_GET = True

# Provider-specific configuration
# ─────────────────────────────────────────────────────────────────────────────
# Credentials are loaded from the database (Django Admin ▸ Social Applications).
#
# Do NOT add an 'APP' dict here with empty client_id / secret — allauth will
# use it *instead of* the database record, sending an empty client_id to Google.
#
# Setup checklist:
#   1. Django Admin ▸ Social Applications ▸ Add
#      • Provider: Google
#      • Client ID:  <your OAuth 2.0 Client ID>
#      • Secret key: <your Client Secret>
#      • Sites:      select "127.0.0.1:8000" (must match SITE_ID = 1)
#
#   2. Google Cloud Console ▸ APIs & Services ▸ Credentials
#      • Authorised redirect URI:
#        http://127.0.0.1:8000/accounts/google/login/callback/
# ─────────────────────────────────────────────────────────────────────────────
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {
            'access_type': 'online',
            'prompt': 'select_account',   # always show the account-picker
        },
        'FETCH_USERINFO': True,            # pull name/avatar from userinfo endpoint
    },
}
