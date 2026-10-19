"""
Health monitoring service for Discord connection pool.
Provides periodic health checks and metrics updates.
"""

import asyncio
import logging
import time
from typing import Optional
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache

from .connection_pool import get_connection_pool
from .prometheus_metrics import get_metrics_instance

from loguru import logger

class ConnectionPoolHealthMonitor:
    """Health monitoring service for the Discord connection pool."""
    
    def __init__(self, update_interval: int = 30):
        self.update_interval = update_interval
        self.pool = get_connection_pool()
        self.metrics = get_metrics_instance(self.pool)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the health monitoring service."""
        if self._running:
            logger.warning("Health monitor is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started connection pool health monitor (interval: {self.update_interval}s)")
    
    async def stop(self):
        """Stop the health monitoring service."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped connection pool health monitor")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")
                await asyncio.sleep(5)  # Short delay before retry
    
    async def _perform_health_check(self):
        """Perform a comprehensive health check."""
        try:
            # Update basic metrics
            self.pool.update_metrics()
            
            # Check pool health
            health_status = await self._check_pool_health()
            
            # Log health status if there are issues
            if health_status['score'] < 80:
                logger.warning(f"Connection pool health score: {health_status['score']}/100")
                logger.warning(f"Health issues: {health_status['issues']}")
            
            # Update cache with health status
            cache.set('discord_pool_health', health_status, timeout=60)
            
        except Exception as e:
            logger.error(f"Error performing health check: {e}")
            self.metrics.record_error("health_check_failed")
    
    async def _check_pool_health(self) -> dict:
        """Check the health of the connection pool."""
        health_status = {
            'score': 100,
            'issues': [],
            'timestamp': datetime.now().isoformat(),
            'pool_size': len(self.pool._pool),
            'max_size': self.pool._max_connections,
            'utilization': 0,
            'connection_ages': []
        }
        
        # Calculate utilization
        if self.pool._max_connections > 0:
            utilization = len(self.pool._pool) / self.pool._max_connections
            health_status['utilization'] = utilization
            
            # Check for high utilization
            if utilization > 0.9:
                health_status['score'] -= 20
                health_status['issues'].append("High pool utilization (>90%)")
            elif utilization > 0.8:
                health_status['score'] -= 10
                health_status['issues'].append("Moderate pool utilization (>80%)")
        
        # Check connection ages
        now = datetime.now()
        for token, connection_time in self.pool._connection_times.items():
            age_seconds = (now - connection_time).total_seconds()
            health_status['connection_ages'].append(age_seconds)
            
            # Check for very old connections
            if age_seconds > self.pool._connection_timeout * 0.8:
                health_status['score'] -= 5
                health_status['issues'].append(f"Old connection detected (age: {age_seconds:.1f}s)")
        
        # Check for connection errors (this would need to be tracked over time)
        # For now, we'll use a simple heuristic based on pool state
        
        # Ensure score is within bounds
        health_status['score'] = max(0, min(100, health_status['score']))
        
        return health_status
    
    async def get_health_status(self) -> dict:
        """Get the current health status."""
        cached_status = cache.get('discord_pool_health')
        if cached_status:
            return cached_status
        
        # If no cached status, perform a quick check
        return await self._check_pool_health()
    
    async def force_cleanup(self):
        """Force a cleanup of expired connections."""
        try:
            await self.pool._cleanup_expired_connections()
            logger.info("Forced cleanup of expired connections")
        except Exception as e:
            logger.error(f"Error during forced cleanup: {e}")
            self.metrics.record_error("cleanup_failed")

# Global health monitor instance
_health_monitor: Optional[ConnectionPoolHealthMonitor] = None

def get_health_monitor() -> ConnectionPoolHealthMonitor:
    """Get the global health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        update_interval = getattr(settings, 'DISCORD_HEALTH_CHECK_INTERVAL', 30)
        _health_monitor = ConnectionPoolHealthMonitor(update_interval)
    return _health_monitor

async def start_health_monitoring():
    """Start the health monitoring service."""
    monitor = get_health_monitor()
    await monitor.start()

async def stop_health_monitoring():
    """Stop the health monitoring service."""
    monitor = get_health_monitor()
    await monitor.stop()

async def get_pool_health_status() -> dict:
    """Get the current pool health status."""
    monitor = get_health_monitor()
    return await monitor.get_health_status()
