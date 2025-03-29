import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-h9j%w!3@wkc(^0r9+9fc2i#9rmt)=4igl9j_h7p(fz-!s$c=hm"

# JWT settings
JWT_SECRET = os.environ.get('JWT_SECRET', SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['192.168.21.75', '192.168.21.186', '*']


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',  # Add corsheaders app
    'prakriti_setu',
    'prakirti_admin',  # Added prakirti_admin app
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # Add CORS middleware (place it high in the list)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS settings
CORS_ALLOW_ALL_ORIGINS = True  # Allow all origins temporarily to test mobile access
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Your frontend URL
    "http://127.0.0.1:5173",
    "http://192.168.21.186:5173",  # Your local IP address for mobile access
    "https://192.168.21.186:5173",  # HTTPS version
]
CORS_ALLOW_CREDENTIALS = True  # Allow cookies in cross-origin requests

# Also allow requests from mobile browser without specific port
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://192\.168\.21\.186(:[0-9]+)?$",
]

ROOT_URLCONF = 'hackcrux_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'hackcrux_backend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': 'postgres',
        'PASSWORD': '12345678',
        'HOST': 'db.pljgitruprxxdppbwkac.supabase.co',
        'PORT': '5432',
    }
}

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

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email configuration settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # Change this based on your email provider
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'piyushdayal108@gmail.com'
EMAIL_HOST_PASSWORD = 'mxrf uchq efmw bjke'
DEFAULT_FROM_EMAIL = 'Sankat Mochan <sankat.mochan@gmail.com>'

# Frontend URL for email links
FRONTEND_URL = 'http://localhost:5173'  # Change to your React frontend URL in production