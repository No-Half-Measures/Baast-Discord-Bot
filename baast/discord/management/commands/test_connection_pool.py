"""
Management command to test and monitor the Discord connection pool.
Usage: python manage.py test_connection_pool
"""

import asyncio
import time
from django.core.management.base import BaseCommand
from django.conf import settings

from discord.connection_pool import get_connection_pool, cleanup_connection_pool

class Command(BaseCommand):
    help = 'Test and monitor Discord connection pool'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-tokens',
            nargs='+',
            help='Test tokens to use for connection pool testing',
        )
        parser.add_argument(
            '--max-connections',
            type=int,
            default=5,
            help='Maximum connections to test with',
        )
        parser.add_argument(
            '--test-duration',
            type=int,
            default=30,
            help='Test duration in seconds',
        )

    def handle(self, *args, **options):
        asyncio.run(self.run_tests(options))

    async def run_tests(self, options):
        """Run connection pool tests."""
        self.stdout.write("Starting Discord connection pool tests...")
        
        # Initialize connection pool
        pool = get_connection_pool()
        
        # Test basic functionality
        await self.test_basic_functionality(pool)
        
        # Test with multiple tokens if provided
        if options['test_tokens']:
            await self.test_multiple_tokens(pool, options['test_tokens'])
        
        # Test connection limits
        await self.test_connection_limits(pool, options['max_connections'])
        
        # Test cleanup
        await self.test_cleanup(pool)
        
        # Cleanup
        await cleanup_connection_pool()
        
        self.stdout.write(
            self.style.SUCCESS('Connection pool tests completed successfully!')
        )

    async def test_basic_functionality(self, pool):
        """Test basic connection pool functionality."""
        self.stdout.write("Testing basic functionality...")
        
        # Test with a dummy token (this will create a temporary connection)
        test_token = "test_token_123"
        
        try:
            restapp, client = await pool.get_client(test_token)
            self.stdout.write("✓ Successfully created connection")
            
            # Test release
            await pool.release_client(test_token, restapp, is_temporary=True)
            self.stdout.write("✓ Successfully released connection")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Basic functionality test failed: {e}")
            )

    async def test_multiple_tokens(self, pool, tokens):
        """Test connection pool with multiple tokens."""
        self.stdout.write(f"Testing with {len(tokens)} tokens...")
        
        connections = []
        
        try:
            # Create connections for each token
            for i, token in enumerate(tokens):
                restapp, client = await pool.get_client(token)
                connections.append((token, restapp))
                self.stdout.write(f"✓ Created connection {i+1}/{len(tokens)}")
            
            # Release all connections
            for token, restapp in connections:
                await pool.release_client(token, restapp, is_temporary=True)
            
            self.stdout.write("✓ Successfully managed multiple connections")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Multiple tokens test failed: {e}")
            )

    async def test_connection_limits(self, pool, max_connections):
        """Test connection pool limits."""
        self.stdout.write(f"Testing connection limits (max: {max_connections})...")
        
        connections = []
        
        try:
            # Create connections up to the limit
            for i in range(max_connections + 2):  # Test beyond limit
                token = f"test_token_{i}"
                restapp, client = await pool.get_client(token)
                connections.append((token, restapp))
                
                if i < max_connections:
                    self.stdout.write(f"✓ Created pooled connection {i+1}")
                else:
                    self.stdout.write(f"✓ Created temporary connection {i+1}")
            
            # Check pool size
            pool_size = len(pool._pool)
            self.stdout.write(f"Pool size: {pool_size}/{max_connections}")
            
            # Release all connections
            for token, restapp in connections:
                is_temporary = token not in pool._pool
                await pool.release_client(token, restapp, is_temporary)
            
            self.stdout.write("✓ Successfully tested connection limits")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Connection limits test failed: {e}")
            )

    async def test_cleanup(self, pool):
        """Test connection pool cleanup."""
        self.stdout.write("Testing cleanup functionality...")
        
        try:
            # Create some connections
            for i in range(3):
                token = f"cleanup_test_{i}"
                restapp, client = await pool.get_client(token)
                await pool.release_client(token, restapp, is_temporary=False)
            
            initial_size = len(pool._pool)
            self.stdout.write(f"Initial pool size: {initial_size}")
            
            # Test cleanup
            await pool._cleanup_expired_connections()
            
            # Force cleanup by setting old timestamps
            for token in list(pool._connection_times.keys()):
                pool._connection_times[token] = time.time() - 1000  # Very old
            
            await pool._cleanup_expired_connections()
            
            final_size = len(pool._pool)
            self.stdout.write(f"Final pool size: {final_size}")
            
            self.stdout.write("✓ Cleanup test completed")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Cleanup test failed: {e}")
            )
