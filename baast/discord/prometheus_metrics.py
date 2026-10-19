"""
Prometheus metrics for Discord connection pool monitoring.
Provides detailed metrics about connection pool health, performance, and usage.
"""

import time
from typing import Dict, Optional
from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry
from django.conf import settings

# Create a custom registry for Discord metrics
discord_registry = CollectorRegistry()

# Connection Pool Metrics
connection_pool_size = Gauge(
    'discord_connection_pool_size',
    'Current number of connections in the pool',
    registry=discord_registry
)

connection_pool_max_size = Gauge(
    'discord_connection_pool_max_size',
    'Maximum number of connections allowed in the pool',
    registry=discord_registry
)

connection_pool_connections_created_total = Counter(
    'discord_connection_pool_connections_created_total',
    'Total number of connections created',
    ['connection_type'],  # 'pooled' or 'temporary'
    registry=discord_registry
)

connection_pool_connections_reused_total = Counter(
    'discord_connection_pool_connections_reused_total',
    'Total number of connections reused from pool',
    registry=discord_registry
)

connection_pool_connections_closed_total = Counter(
    'discord_connection_pool_connections_closed_total',
    'Total number of connections closed',
    ['close_reason'],  # 'expired', 'error', 'shutdown', 'temporary'
    registry=discord_registry
)

connection_pool_connection_duration_seconds = Histogram(
    'discord_connection_pool_connection_duration_seconds',
    'Time spent using a connection',
    ['connection_type'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    registry=discord_registry
)

connection_pool_connection_creation_duration_seconds = Histogram(
    'discord_connection_pool_connection_creation_duration_seconds',
    'Time spent creating a new connection',
    ['connection_type'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=discord_registry
)

connection_pool_errors_total = Counter(
    'discord_connection_pool_errors_total',
    'Total number of connection pool errors',
    ['error_type'],  # 'creation_failed', 'connection_expired', 'cleanup_failed', 'release_failed'
    registry=discord_registry
)

connection_pool_cleanup_operations_total = Counter(
    'discord_connection_pool_cleanup_operations_total',
    'Total number of cleanup operations performed',
    registry=discord_registry
)

connection_pool_cleanup_connections_removed_total = Counter(
    'discord_connection_pool_cleanup_connections_removed_total',
    'Total number of connections removed during cleanup',
    ['removal_reason'],  # 'expired', 'error', 'manual'
    registry=discord_registry
)

# Discord API Metrics
discord_api_requests_total = Counter(
    'discord_api_requests_total',
    'Total number of Discord API requests',
    ['endpoint', 'method', 'status_code'],
    registry=discord_registry
)

discord_api_request_duration_seconds = Histogram(
    'discord_api_request_duration_seconds',
    'Duration of Discord API requests',
    ['endpoint', 'method'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    registry=discord_registry
)

discord_api_rate_limited_total = Counter(
    'discord_api_rate_limited_total',
    'Total number of Discord API rate limit hits',
    ['endpoint'],
    registry=discord_registry
)

# Authentication Metrics
discord_auth_sessions_valid = Gauge(
    'discord_auth_sessions_valid',
    'Number of valid authentication sessions',
    registry=discord_registry
)

discord_auth_sessions_expired_total = Counter(
    'discord_auth_sessions_expired_total',
    'Total number of expired authentication sessions',
    registry=discord_registry
)

# Pool Health Metrics
connection_pool_health_score = Gauge(
    'discord_connection_pool_health_score',
    'Health score of the connection pool (0-100)',
    registry=discord_registry
)

connection_pool_utilization_ratio = Gauge(
    'discord_connection_pool_utilization_ratio',
    'Current pool utilization ratio (0-1)',
    registry=discord_registry
)

# Connection Pool Info
connection_pool_info = Info(
    'discord_connection_pool_info',
    'Information about the connection pool configuration',
    registry=discord_registry
)

class ConnectionPoolMetrics:
    """Metrics collector for Discord connection pool."""
    
    def __init__(self, pool):
        self.pool = pool
        self._connection_start_times: Dict[str, float] = {}
        self._setup_info_metrics()
    
    def _setup_info_metrics(self):
        """Set up info metrics with pool configuration."""
        connection_pool_info.info({
            'max_connections': str(self.pool._max_connections),
            'connection_timeout': str(self.pool._connection_timeout),
            'version': '1.0.0'
        })
        # Initialize all metrics with default values to ensure they're exported
        self._initialize_metrics()
        self._metrics_initialized = True
    
    def _initialize_metrics(self):
        """Initialize all metrics with default/zero values to ensure they're exported."""
        # Initialize counters with labels (at least one label combination)
        connection_pool_connections_created_total.labels(connection_type='pooled').inc(0)
        connection_pool_connections_created_total.labels(connection_type='temporary').inc(0)
        
        connection_pool_connections_closed_total.labels(close_reason='expired').inc(0)
        connection_pool_connections_closed_total.labels(close_reason='error').inc(0)
        connection_pool_connections_closed_total.labels(close_reason='shutdown').inc(0)
        connection_pool_connections_closed_total.labels(close_reason='temporary').inc(0)
        
        connection_pool_errors_total.labels(error_type='creation_failed').inc(0)
        connection_pool_errors_total.labels(error_type='connection_expired').inc(0)
        connection_pool_errors_total.labels(error_type='cleanup_failed').inc(0)
        connection_pool_errors_total.labels(error_type='release_failed').inc(0)
        connection_pool_errors_total.labels(error_type='health_check_failed').inc(0)
        
        connection_pool_cleanup_connections_removed_total.labels(removal_reason='expired').inc(0)
        connection_pool_cleanup_connections_removed_total.labels(removal_reason='error').inc(0)
        connection_pool_cleanup_connections_removed_total.labels(removal_reason='manual').inc(0)
        connection_pool_cleanup_connections_removed_total.labels(removal_reason='shutdown').inc(0)
        
        # Initialize histograms with labels
        connection_pool_connection_duration_seconds.labels(connection_type='pooled').observe(0)
        connection_pool_connection_duration_seconds.labels(connection_type='temporary').observe(0)
        
        connection_pool_connection_creation_duration_seconds.labels(connection_type='pooled').observe(0)
        connection_pool_connection_creation_duration_seconds.labels(connection_type='temporary').observe(0)
        
        # Initialize gauges with default values
        connection_pool_size.set(0)
        connection_pool_max_size.set(self.pool._max_connections)
        connection_pool_utilization_ratio.set(0.0)
        connection_pool_health_score.set(100.0)
        discord_auth_sessions_valid.set(0)
        
        # Initialize counters without labels
        connection_pool_connections_reused_total.inc(0)
        connection_pool_cleanup_operations_total.inc(0)
        discord_auth_sessions_expired_total.inc(0)
    
    def record_connection_created(self, connection_type: str, duration: float):
        """Record a connection creation."""
        connection_pool_connections_created_total.labels(
            connection_type=connection_type
        ).inc()
        connection_pool_connection_creation_duration_seconds.labels(
            connection_type=connection_type
        ).observe(duration)
    
    def record_connection_reused(self):
        """Record a connection reuse."""
        connection_pool_connections_reused_total.inc()
    
    def record_connection_closed(self, close_reason: str):
        """Record a connection closure."""
        connection_pool_connections_closed_total.labels(
            close_reason=close_reason
        ).inc()
    
    def record_connection_start(self, access_token: str, connection_type: str):
        """Record the start of connection usage."""
        self._connection_start_times[access_token] = time.time()
    
    def record_connection_end(self, access_token: str, connection_type: str):
        """Record the end of connection usage."""
        if access_token in self._connection_start_times:
            duration = time.time() - self._connection_start_times[access_token]
            connection_pool_connection_duration_seconds.labels(
                connection_type=connection_type
            ).observe(duration)
            del self._connection_start_times[access_token]
    
    def record_error(self, error_type: str):
        """Record a connection pool error."""
        connection_pool_errors_total.labels(error_type=error_type).inc()
    
    def record_cleanup_operation(self, connections_removed: int, removal_reason: str):
        """Record a cleanup operation."""
        connection_pool_cleanup_operations_total.inc()
        connection_pool_cleanup_connections_removed_total.labels(
            removal_reason=removal_reason
        ).inc(connections_removed)
    
    def update_pool_metrics(self):
        """Update current pool state metrics."""
        # Ensure metrics are initialized (in case initialization was missed)
        if not hasattr(self, '_metrics_initialized'):
            self._initialize_metrics()
            self._metrics_initialized = True
        
        pool_size = len(self.pool._pool)
        max_size = self.pool._max_connections
        
        # Always set gauge values (even if zero) to ensure they're exported
        connection_pool_size.set(pool_size)
        connection_pool_max_size.set(max_size)
        
        # Calculate utilization ratio
        utilization = pool_size / max_size if max_size > 0 else 0.0
        connection_pool_utilization_ratio.set(utilization)
        
        # Calculate health score (0-100)
        health_score = self._calculate_health_score()
        connection_pool_health_score.set(health_score)
    
    def _calculate_health_score(self) -> float:
        """Calculate a health score for the connection pool (0-100)."""
        score = 100.0
        
        # Penalize for high utilization
        utilization = len(self.pool._pool) / self.pool._max_connections if self.pool._max_connections > 0 else 0
        if utilization > 0.9:
            score -= 20
        elif utilization > 0.8:
            score -= 10
        
        # Penalize for many errors (this would need to be tracked over time)
        # For now, we'll use a simple heuristic
        
        return max(0, min(100, score))
    
    def record_discord_api_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """Record a Discord API request."""
        discord_api_requests_total.labels(
            endpoint=endpoint,
            method=method,
            status_code=str(status_code)
        ).inc()
        discord_api_request_duration_seconds.labels(
            endpoint=endpoint,
            method=method
        ).observe(duration)
    
    def record_discord_api_rate_limit(self, endpoint: str):
        """Record a Discord API rate limit hit."""
        discord_api_rate_limited_total.labels(endpoint=endpoint).inc()
    
    def record_auth_session_expired(self):
        """Record an expired authentication session."""
        discord_auth_sessions_expired_total.inc()
    
    def update_auth_sessions_count(self, count: int):
        """Update the count of valid authentication sessions."""
        discord_auth_sessions_valid.set(count)

# Global metrics instance
_metrics_instance: Optional[ConnectionPoolMetrics] = None

def get_metrics_instance(pool) -> ConnectionPoolMetrics:
    """Get the global metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = ConnectionPoolMetrics(pool)
    return _metrics_instance

def get_discord_registry() -> CollectorRegistry:
    """Get the Discord metrics registry."""
    return discord_registry
