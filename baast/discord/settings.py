"""
Discord app specific settings and configuration.
Centralizes Discord-related settings for better organization.
"""

from django.conf import settings

# Discord API Settings
DISCORD_SETTINGS = {
    'CLIENT_ID': getattr(settings, 'CLIENT_ID'),
    'CLIENT_SECRET': getattr(settings, 'CLIENT_SECRET'),
    'CLIENT_TOKEN': getattr(settings, 'CLIENT_TOKEN'),
    'AUTH_URL': getattr(settings, 'AUTH_URL'),
    'REDIRECT_URL': getattr(settings, 'REDIRECT_URL'),
    'HASH_SALT': getattr(settings, 'HASH_SALT'),
    'CACHE_TTL': getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', 300),
}

# Connection Pool Settings
CONNECTION_POOL_SETTINGS = {
    'MAX_CONNECTIONS': getattr(settings, 'DISCORD_MAX_CONNECTIONS', 10),
    'CONNECTION_TIMEOUT': getattr(settings, 'DISCORD_CONNECTION_TIMEOUT', 300),  # 5 minutes
    'CLEANUP_INTERVAL': getattr(settings, 'DISCORD_CLEANUP_INTERVAL', 60),  # 1 minute
}

# Cache Settings
CACHE_SETTINGS = {
    'GUILD_CACHE_TTL': getattr(settings, 'DISCORD_GUILD_CACHE_TTL', 300),
    'USER_CACHE_TTL': getattr(settings, 'DISCORD_USER_CACHE_TTL', 180),
    'TEMPLATE_CACHE_TTL': getattr(settings, 'DISCORD_TEMPLATE_CACHE_TTL', 600),
}

# Rate Limiting Settings
RATE_LIMIT_SETTINGS = {
    'ENABLED': getattr(settings, 'DISCORD_RATE_LIMIT_ENABLED', True),
    'REQUESTS_PER_MINUTE': getattr(settings, 'DISCORD_RATE_LIMIT_RPM', 60),
    'BURST_LIMIT': getattr(settings, 'DISCORD_RATE_LIMIT_BURST', 10),
}

# Error Handling Settings
ERROR_SETTINGS = {
    'LOG_API_ERRORS': getattr(settings, 'DISCORD_LOG_API_ERRORS', True),
    'RETRY_ATTEMPTS': getattr(settings, 'DISCORD_RETRY_ATTEMPTS', 3),
    'RETRY_DELAY': getattr(settings, 'DISCORD_RETRY_DELAY', 1.0),
}

def get_discord_setting(key: str, default=None):
    """Get a Discord-specific setting value."""
    return DISCORD_SETTINGS.get(key, default)

def get_connection_pool_setting(key: str, default=None):
    """Get a connection pool setting value."""
    return CONNECTION_POOL_SETTINGS.get(key, default)

def get_cache_setting(key: str, default=None):
    """Get a cache setting value."""
    return CACHE_SETTINGS.get(key, default)

def get_rate_limit_setting(key: str, default=None):
    """Get a rate limit setting value."""
    return RATE_LIMIT_SETTINGS.get(key, default)

def get_error_setting(key: str, default=None):
    """Get an error handling setting value."""
    return ERROR_SETTINGS.get(key, default)
