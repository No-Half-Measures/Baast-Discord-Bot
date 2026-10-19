"""
Custom decorators for Discord app.
"""

from functools import wraps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

def csrf_exempt_public(view_func):
    """
    Decorator that exempts a view from CSRF protection and authentication.
    Used for public endpoints like metrics that should be accessible without authentication.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Mark the request as not requiring authentication
        request._public_endpoint = True
        return view_func(request, *args, **kwargs)
    return csrf_exempt(wrapper)

def public_endpoint(view_class):
    """
    Class decorator for views that should be publicly accessible.
    Works correctly with other method decorators like csrf_exempt.
    """
    # Get the original dispatch method descriptor
    # This handles the case where method_decorator has already wrapped it
    original_dispatch_descriptor = view_class.dispatch
    
    # Create a new dispatch that marks the request as public
    def dispatch(self, request, *args, **kwargs):
        # Mark the request as not requiring authentication
        request._public_endpoint = True
        # Bind the original descriptor to self and call it
        # This properly handles the descriptor protocol for wrapped methods
        bound_method = original_dispatch_descriptor.__get__(self, view_class)
        return bound_method(request, *args, **kwargs)
    
    # Replace the dispatch method
    view_class.dispatch = dispatch
    return view_class
