from flask_caching import Cache
from functools import wraps
from datetime import timedelta

cache = Cache(config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': 'redis://localhost:6379/0',
    'CACHE_DEFAULT_TIMEOUT': 300
})

def cache_with_args(*args, **kwargs):
    """Decorator for caching function results with arguments"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = f"{f.__name__}:{str(args)}:{str(kwargs)}"
            rv = cache.get(cache_key)
            if rv is not None:
                return rv
            rv = f(*args, **kwargs)
            cache.set(cache_key, rv, timeout=kwargs.get('timeout', 300))
            return rv
        return decorated_function
    return decorator

def invalidate_cache_pattern(pattern):
    """Invalidate all cache keys matching a pattern"""
    cache.delete_many(pattern)

# Common cache timeouts
CACHE_TIMEOUTS = {
    'SHORT': 300,  # 5 minutes
    'MEDIUM': 1800,  # 30 minutes
    'LONG': 86400,  # 24 hours
    'VERY_LONG': 604800  # 1 week
} 