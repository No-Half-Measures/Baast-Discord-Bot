"""
Prometheus metrics endpoint for Discord connection pool monitoring.
Provides a dedicated endpoint for Prometheus to scrape Discord-specific metrics.
"""

import time
from django.http import HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from .prometheus_metrics import get_discord_registry
from .health_monitor import get_pool_health_status
from .connection_pool import get_connection_pool
from .decorators import public_endpoint

@method_decorator(csrf_exempt, name='dispatch')
@public_endpoint
class DiscordMetricsView(View):
    """
    Prometheus metrics endpoint for Discord connection pool.
    Provides metrics in Prometheus format for monitoring.
    """
    
    def get(self, request):
        """Return Prometheus metrics for Discord connection pool."""
        try:
            # Ensure pool and metrics are initialized
            pool = get_connection_pool()
            
            # Ensure metrics instance exists and is initialized
            if pool._metrics is None:
                from .prometheus_metrics import get_metrics_instance
                pool._metrics = get_metrics_instance(pool)
            
            # Update pool metrics before generating
            pool.update_metrics()
            
            # Generate metrics
            registry = get_discord_registry()
            metrics_data = generate_latest(registry)
            
            return HttpResponse(
                metrics_data,
                content_type=CONTENT_TYPE_LATEST
            )
        except Exception as e:
            import traceback
            error_msg = f"Error generating metrics: {e}\n{traceback.format_exc()}"
            print(error_msg)
            
            # Try to return at least basic metrics even on error
            try:
                registry = get_discord_registry()
                metrics_data = generate_latest(registry)
                return HttpResponse(
                    metrics_data,
                    content_type=CONTENT_TYPE_LATEST
                )
            except:
                # Return error metrics if something goes wrong
                error_metrics = f"""# HELP discord_metrics_error_total Total number of errors generating metrics
# TYPE discord_metrics_error_total counter
discord_metrics_error_total{{error_type="generation_failed"}} 1
# HELP discord_metrics_last_error_timestamp_seconds Timestamp of last error
# TYPE discord_metrics_last_error_timestamp_seconds gauge
discord_metrics_last_error_timestamp_seconds {int(time.time())}
"""
                return HttpResponse(
                    error_metrics,
                    content_type=CONTENT_TYPE_LATEST,
                    status=500
                )

@public_endpoint
class DiscordHealthView(View):
    """
    Health check endpoint for Discord connection pool.
    Returns JSON health status for monitoring systems.
    """
    
    async def get(self, request):
        """Return health status of Discord connection pool."""
        try:
            health_status = await get_pool_health_status()
            
            # Determine HTTP status based on health score
            if health_status['score'] >= 80:
                status_code = 200
            elif health_status['score'] >= 60:
                status_code = 206  # Partial Content
            else:
                status_code = 503  # Service Unavailable
            
            from django.http import JsonResponse
            return JsonResponse(health_status, status=status_code)
            
        except Exception as e:
            from django.http import JsonResponse
            return JsonResponse({
                'error': str(e),
                'score': 0,
                'status': 'error'
            }, status=500)

@public_endpoint
class DiscordPoolStatusView(View):
    """
    Detailed pool status endpoint for debugging and monitoring.
    Returns comprehensive information about the connection pool.
    """
    
    async def get(self, request):
        """Return detailed pool status."""
        try:
            pool = get_connection_pool()
            health_status = await get_pool_health_status()
            
            # Get detailed pool information
            pool_info = {
                'pool_size': len(pool._pool),
                'max_connections': pool._max_connections,
                'connection_timeout': pool._connection_timeout,
                'utilization_ratio': len(pool._pool) / pool._max_connections if pool._max_connections > 0 else 0,
                'active_tokens': list(pool._pool.keys()),
                'connection_ages': {},
                'health': health_status
            }
            
            # Add connection ages
            now = time.time()
            for token, connection_time in pool._connection_times.items():
                age_seconds = (now - connection_time.timestamp())
                pool_info['connection_ages'][token[:8] + '...'] = round(age_seconds, 2)
            
            from django.http import JsonResponse
            return JsonResponse(pool_info)
            
        except Exception as e:
            from django.http import JsonResponse
            return JsonResponse({
                'error': str(e),
                'status': 'error'
            }, status=500)
