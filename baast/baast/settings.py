from pathlib import Path
from loguru import logger
import sys
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment configuration
ENVIRONMENT = os.getenv('ENVIRONMENT', 'production').lower()
LOCAL = ENVIRONMENT == 'local'
TESTING = os.getenv('TESTING', 'False').lower() == 'true'

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'SECRET_KEY_HERE')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# Parse ALLOWED_HOSTS from environment variable
ALLOWED_HOSTS_STR = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,baast.app')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_STR.split(',')]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Behind nginx TLS termination — required for request.is_secure() / request.scheme
if not LOCAL:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_COOKIE_AGE = 7 * 24 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

HASH_SALT = os.getenv('HASH_SALT', 'HASH_SALT_HERE')

# Stripe Configuration
if TESTING:
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY_TEST')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY_TEST')
    STRIPE_ENDPOINT_SECRET = os.getenv('STRIPE_ENDPOINT_SECRET_TEST')
    
    # Parse price IDs from environment
    STRIPE_PRICE_ID_NORMAL_MONTHLY = os.getenv('STRIPE_PRICE_ID_NORMAL_MONTHLY')
    STRIPE_PRICE_ID_NORMAL_YEARLY = os.getenv('STRIPE_PRICE_ID_NORMAL_YEARLY')
    STRIPE_PRICE_ID_TRIO_MONTHLY = os.getenv('STRIPE_PRICE_ID_TRIO_MONTHLY')
    STRIPE_PRICE_ID_TRIO_YEARLY = os.getenv('STRIPE_PRICE_ID_TRIO_YEARLY')
    
    STRIPE_PRICE_ID = [
        STRIPE_PRICE_ID_NORMAL_MONTHLY,
        STRIPE_PRICE_ID_NORMAL_YEARLY,
        STRIPE_PRICE_ID_TRIO_MONTHLY,
        STRIPE_PRICE_ID_TRIO_YEARLY
    ]
    
    STRIPE_PRODUCT_ID = [
        os.getenv('STRIPE_PRODUCT_ID_NORMAL'),
        os.getenv('STRIPE_PRODUCT_ID_TRIO')
    ]
else:
    # LIVE
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY_LIVE')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY_LIVE')
    STRIPE_ENDPOINT_SECRET = os.getenv('STRIPE_ENDPOINT_SECRET_LIVE')
    
    # Parse price IDs from environment
    STRIPE_PRICE_ID_NORMAL_MONTHLY = os.getenv('STRIPE_PRICE_ID_NORMAL_MONTHLY')
    STRIPE_PRICE_ID_NORMAL_YEARLY = os.getenv('STRIPE_PRICE_ID_NORMAL_YEARLY')
    STRIPE_PRICE_ID_TRIO_MONTHLY = os.getenv('STRIPE_PRICE_ID_TRIO_MONTHLY')
    STRIPE_PRICE_ID_TRIO_YEARLY = os.getenv('STRIPE_PRICE_ID_TRIO_YEARLY')
    
    STRIPE_PRICE_ID = [
        STRIPE_PRICE_ID_NORMAL_MONTHLY,
        STRIPE_PRICE_ID_NORMAL_YEARLY,
        STRIPE_PRICE_ID_TRIO_MONTHLY,
        STRIPE_PRICE_ID_TRIO_YEARLY
    ]
    
    STRIPE_PRODUCT_ID = [
        os.getenv('STRIPE_PRODUCT_ID_NORMAL'),
        os.getenv('STRIPE_PRODUCT_ID_TRIO')
    ]


# Discord Configuration
CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
CLIENT_TOKEN = os.getenv('DISCORD_TOKEN')

DISCORD_SUPPORT_SERVER = "https://discord.gg/RNrA9Gtxmm"

# Discord OAuth URLs
if LOCAL:
    AUTH_URL = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri=http%3A%2F%2Flocalhost%2Flogin%2Fredirect&response_type=code&scope=identify%20guilds%20guilds.members.read"
    REDIRECT_URL = "http://localhost/login/redirect"
else:
    AUTH_URL = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri=https%3A%2F%2Fbaast.app%2Flogin%2Fredirect&response_type=code&scope=identify%20guilds%20guilds.members.read"
    REDIRECT_URL = "https://baast.app/login/redirect"
    
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', './baast-337223-6450ec332d4f.json')

CSRF_TRUSTED_ORIGINS = ['https://*.baast.app','https://*.localhost']

AUTHENTICATION_BACKENDS = [
    'discord.auth.DiscordAuthenticationBackend'
]

# Application definition
ROOT_URLCONF = 'baast.urls'

LOGIN_URL = '/login/'

INSTALLED_APPS = [
    'channels',
    'app.apps.BaastConfig',
    'discord.apps.DiscordConfig',
    'discord.templatetags',
    'cache.apps.CacheConfig',
    #'documentation.apps.DocumentationConfig',

    #'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Caching
CACHE_MIDDLEWARE_SECONDS = 60 * 10
# Redis Configuration
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/1",
        "TIMEOUT": CACHE_MIDDLEWARE_SECONDS,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

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
                'discord.context_processors.nav_data',
            ],
        },
    },
]


# Configure loguru
logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
)

# Add file logging if needed
# logger.add(
#     "logs/baast.log",
#     rotation="1 day",
#     retention="30 days",
#     format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
#     level="INFO"
# )

# Intercept Django's logging and redirect to loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
            
        if "fixed bucket" in record.getMessage():
            return

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# Configure Django to use loguru
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

# Configure specific loggers
logging.getLogger("django").handlers = [InterceptHandler()]
logging.getLogger("django.template").handlers = [InterceptHandler()]
logging.getLogger("django.db.backends").handlers = [InterceptHandler()]
logging.getLogger("uvicorn").handlers = [InterceptHandler()]


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

# Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django_prometheus.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

MEDIA_URL = 'http://localhost:80/media/' if LOCAL else '/media/'
MEDIA_ROOT = './media/'

STATIC_URL = 'http://localhost:80/static/' if LOCAL else '/static/'
STATIC_ROOT = './static/'


# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# URL Configuration
APPEND_SLASH = False  # Disable automatic trailing slash redirects

ASGI_APPLICATION = 'baast.asgi.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/1"],
        },
    }
}


#PROMETHEUS_LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 25.0, 50.0, 75.0, float("inf"),)
#PROMETHEUS_METRIC_NAMESPACE = "baast"

# Connection Pool Settings
DISCORD_MAX_CONNECTIONS = 10  # Maximum pooled connections
DISCORD_CONNECTION_TIMEOUT = 300  # Connection timeout in seconds
DISCORD_CLEANUP_INTERVAL = 60  # Cleanup interval in seconds
DISCORD_HEALTH_CHECK_INTERVAL = 30

# Cache Settings
DISCORD_GUILD_CACHE_TTL = 300
DISCORD_USER_CACHE_TTL = 180
DISCORD_TEMPLATE_CACHE_TTL = 600

# Rate Limiting
DISCORD_RATE_LIMIT_ENABLED = True
DISCORD_RATE_LIMIT_RPM = 60
DISCORD_RATE_LIMIT_BURST = 10