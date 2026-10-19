import asyncio
import logging
import time
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import weakref

from hikari import RESTApp, TokenType, UnauthorizedError
from django.conf import settings
from django.core.cache import cache

from .prometheus_metrics import get_metrics_instance

from loguru import logger

class DiscordConnectionPool:
    """
    Connection pool for Discord RESTApp instances to reduce overhead
    of creating/destroying connections for each request.
    """
    
    def __init__(self, max_connections: int = 10, connection_timeout: int = 300):
        self._pool: Dict[str, RESTApp] = {}
        self._connection_times: Dict[str, datetime] = {}
        self._max_connections = max_connections
        self._connection_timeout = connection_timeout  # 5 minutes default
        self._lock = asyncio.Lock()
        self._metrics = None  # Will be initialized after pool creation
        
    async def get_client(self, access_token: str) -> Tuple[RESTApp, any]:
        """
        Get a RESTApp client for the given access_token.
        Reuses existing connections when possible.
        """
        start_time = time.time()
        connection_type = "pooled"
        
        try:
            async with self._lock:
                # Check if we have a cached connection
                if access_token in self._pool:
                    restapp = self._pool[access_token]
                    connection_time = self._connection_times[access_token]
                    
                    # Check if connection is still valid (not expired)
                    if datetime.now() - connection_time < timedelta(seconds=self._connection_timeout):
                        try:
                            # Test if connection is still alive
                            async with restapp.acquire(access_token, TokenType.BEARER) as client:
                                # If we can acquire the client, connection is good
                                pass
                            
                            # Record connection reuse
                            if self._metrics:
                                self._metrics.record_connection_reused()
                                self._metrics.record_connection_start(access_token, connection_type)
                            
                            return restapp, restapp.acquire(access_token, TokenType.BEARER)
                        except (UnauthorizedError, Exception) as e:
                            logger.warning(f"Connection expired for token, removing from pool: {e}")
                            if self._metrics:
                                self._metrics.record_error("connection_expired")
                            await self._remove_connection(access_token)
                
                # Clean up expired connections
                await self._cleanup_expired_connections()
                
                # Create new connection if pool not full
                if len(self._pool) < self._max_connections:
                    restapp = RESTApp()
                    await restapp.start()
                    self._pool[access_token] = restapp
                    self._connection_times[access_token] = datetime.now()
                    
                    # Record connection creation
                    if self._metrics:
                        creation_duration = time.time() - start_time
                        self._metrics.record_connection_created(connection_type, creation_duration)
                        self._metrics.record_connection_start(access_token, connection_type)
                    
                    return restapp, restapp.acquire(access_token, TokenType.BEARER)
                else:
                    # Pool is full, create temporary connection
                    connection_type = "temporary"
                    logger.warning("Connection pool full, creating temporary connection")
                    restapp = RESTApp()
                    await restapp.start()
                    
                    # Record temporary connection creation
                    if self._metrics:
                        creation_duration = time.time() - start_time
                        self._metrics.record_connection_created(connection_type, creation_duration)
                        self._metrics.record_connection_start(access_token, connection_type)
                    
                    return restapp, restapp.acquire(access_token, TokenType.BEARER)
        
        except Exception as e:
            if self._metrics:
                self._metrics.record_error("creation_failed")
            logger.error(f"Error getting client for token: {e}")
            raise
    
    async def release_client(self, access_token: str, restapp: RESTApp, is_temporary: bool = False):
        """
        Release a client back to the pool.
        If is_temporary=True, the connection will be closed immediately.
        """
        connection_type = "temporary" if is_temporary else "pooled"
        
        # Record connection end
        if self._metrics:
            self._metrics.record_connection_end(access_token, connection_type)
        
        if is_temporary:
            try:
                await restapp.close()
                if self._metrics:
                    self._metrics.record_connection_closed("temporary")
            except Exception as e:
                logger.warning(f"Error closing temporary connection: {e}")
                if self._metrics:
                    self._metrics.record_error("release_failed")
        # For pooled connections, we don't close them here - they stay in the pool
    
    async def _remove_connection(self, access_token: str):
        """Remove a connection from the pool and close it."""
        if access_token in self._pool:
            restapp = self._pool.pop(access_token)
            self._connection_times.pop(access_token, None)
            try:
                await restapp.close()
                if self._metrics:
                    self._metrics.record_connection_closed("expired")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
                if self._metrics:
                    self._metrics.record_error("release_failed")
    
    async def _cleanup_expired_connections(self):
        """Remove expired connections from the pool."""
        now = datetime.now()
        expired_tokens = []
        
        for token, connection_time in self._connection_times.items():
            if now - connection_time >= timedelta(seconds=self._connection_timeout):
                expired_tokens.append(token)
        
        if expired_tokens:
            if self._metrics:
                self._metrics.record_cleanup_operation(len(expired_tokens), "expired")
        
        for token in expired_tokens:
            await self._remove_connection(token)
    
    async def close_all(self):
        """Close all connections in the pool."""
        async with self._lock:
            connection_count = len(self._pool)
            for restapp in self._pool.values():
                try:
                    await restapp.close()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
            
            if self._metrics and connection_count > 0:
                self._metrics.record_cleanup_operation(connection_count, "shutdown")
            
            self._pool.clear()
            self._connection_times.clear()
    
    def update_metrics(self):
        """Update Prometheus metrics for the connection pool."""
        if self._metrics:
            self._metrics.update_pool_metrics()

# Global connection pool instance
_connection_pool: Optional[DiscordConnectionPool] = None

def get_connection_pool() -> DiscordConnectionPool:
    """Get the global connection pool instance."""
    global _connection_pool
    if _connection_pool is None:
        max_connections = getattr(settings, 'DISCORD_MAX_CONNECTIONS', 10)
        connection_timeout = getattr(settings, 'DISCORD_CONNECTION_TIMEOUT', 300)
        _connection_pool = DiscordConnectionPool(max_connections, connection_timeout)
        # Initialize metrics after pool creation
        _connection_pool._metrics = get_metrics_instance(_connection_pool)
    return _connection_pool

async def cleanup_connection_pool():
    """Cleanup function to be called on application shutdown."""
    global _connection_pool
    if _connection_pool:
        await _connection_pool.close_all()
        _connection_pool = None
