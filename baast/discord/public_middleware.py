"""
Middleware to handle public endpoints that should bypass authentication.
"""

from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import logout
from django.http import JsonResponse

class PublicEndpointMiddleware(MiddlewareMixin):
    """
    Middleware that allows certain endpoints to bypass authentication.
    This should be placed before authentication middleware.
    """
    
    # List of public endpoints that don't require authentication
    PUBLIC_PATHS = [
        '/panel/metrics/',
        '/panel/health/',
        '/panel/pool-status/',
    ]
    
    def process_request(self, request):
        """Check if the request is for a public endpoint."""
        # Check if this is a public endpoint
        if any(request.path.startswith(path) for path in self.PUBLIC_PATHS):
            # Mark the request as public
            request._public_endpoint = True
            # Skip authentication for this request
            return None
        
        # Check if the view has marked itself as public
        if hasattr(request, '_public_endpoint') and request._public_endpoint:
            return None
        
        return None
    
    def process_response(self, request, response):
        """Handle response for public endpoints."""
        # If this was a public endpoint, ensure we don't redirect to login
        if hasattr(request, '_public_endpoint') and request._public_endpoint:
            # If we got a redirect to login, return the actual content instead
            if response.status_code == 302 and '/panel/' in response.get('Location', ''):
                # This is likely a redirect to login, let's handle it
                if request.path == '/panel/metrics/':
                    from .metrics_view import DiscordMetricsView
                    view = DiscordMetricsView()
                    return view.get(request)
                elif request.path == '/panel/health/':
                    from .metrics_view import DiscordHealthView
                    view = DiscordHealthView()
                    import asyncio
                    return asyncio.run(view.get(request))
                elif request.path == '/panel/pool-status/':
                    from .metrics_view import DiscordPoolStatusView
                    view = DiscordPoolStatusView()
                    import asyncio
                    return asyncio.run(view.get(request))
        
        return response
