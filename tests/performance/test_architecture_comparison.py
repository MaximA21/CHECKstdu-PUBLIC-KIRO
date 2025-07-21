"""Performance tests comparing old vs new architecture."""

import pytest
import pytest_asyncio
import asyncio
import time
import statistics
from datetime import datetime
from unittest.mock import patch, MagicMock
import json

from src.shared.dependency_injection.bootstrap import get_container
from src.presentation.lambda_handlers.search_handler import SearchHandler
from src.presentation.lambda_handlers.share_api_handler import ShareApiHandler


class TestArchitecturePerformance:
    """Performance comparison tests between old and new architecture."""
    
    @pytest.fixture
    def mock_lambda_context(self):
        """Create a mock Lambda context."""
        context = MagicMock()
        context.function_name = "perf-test-function"
        context.function_version = "$LATEST"
        context.memory_limit_in_mb = "512"
        context.remaining_time_in_millis = lambda: 30000
        context.aws_request_id = "perf-test-request-id"
        return context
    
    @pytest.fixture
    def test_event(self):
        """Create a standard test event for performance testing."""
        return {
            'body': json.dumps({
                'address': {
                    'street': 'Performancestraße',
                    'house_number': '123',
                    'city': 'Berlin',
                    'postal_code': '10115',
                    'country': 'DE'
                },
                'connection_id': 'perf-test-connection'
            }),
            'httpMethod': 'POST',
            'path': '/search',
            'headers': {'Content-Type': 'application/json'}
        }
    
    @pytest.fixture
    def share_event(self):
        """Create a share event for performance testing."""
        return {
            'pathParameters': {
                'share_token': 'test-share-token-123'
            },
            'httpMethod': 'GET',
            'path': '/share/test-share-token-123'
        }
    
    def measure_execution_time(self, func, *args, **kwargs):
        """Measure execution time of a function."""
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        return result, (end_time - start_time) * 1000  # Return result and time in milliseconds
    
    async def measure_async_execution_time(self, func, *args, **kwargs):
        """Measure execution time of an async function."""
        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()
        return result, (end_time - start_time) * 1000  # Return result and time in milliseconds
    
    @pytest.mark.asyncio
    async def test_dependency_injection_initialization_performance(self):
        """Test performance of dependency injection container initialization."""
        initialization_times = []
        
        # Test multiple cold starts
        for i in range(10):
            with patch.dict('os.environ', {'ENVIRONMENT': 'test', 'USE_MOCK_SERVICES': 'true'}):
                start_time = time.perf_counter()
                container = get_container()
                end_time = time.perf_counter()
                
                initialization_time = (end_time - start_time) * 1000
                initialization_times.append(initialization_time)
        
        # Calculate statistics
        avg_init_time = statistics.mean(initialization_times)
        median_init_time = statistics.median(initialization_times)
        max_init_time = max(initialization_times)
        min_init_time = min(initialization_times)
        
        print(f"DI Container Initialization Performance:")
        print(f"  Average: {avg_init_time:.2f}ms")
        print(f"  Median: {median_init_time:.2f}ms")
        print(f"  Min: {min_init_time:.2f}ms")
        print(f"  Max: {max_init_time:.2f}ms")
        
        # Assert reasonable performance
        assert avg_init_time < 500  # Should initialize in less than 500ms
        assert max_init_time < 1000  # No initialization should take more than 1 second
    
    @pytest.mark.asyncio
    async def test_search_handler_performance_with_di(self, test_event, mock_lambda_context):
        """Test search handler performance with dependency injection."""
        with patch.dict('os.environ', {'ENVIRONMENT': 'test', 'USE_MOCK_SERVICES': 'true'}):
            container = get_container()
            handler = SearchHandler(container)
            
            # Warm up
            await handler.handle(test_event, mock_lambda_context)
            
            # Measure performance over multiple requests
            execution_times = []
            for i in range(50):
                _, exec_time = await self.measure_async_execution_time(
                    handler.handle, test_event, mock_lambda_context
                )
                execution_times.append(exec_time)
            
            # Calculate statistics
            avg_time = statistics.mean(execution_times)
            median_time = statistics.median(execution_times)
            p95_time = statistics.quantiles(execution_times, n=20)[18]  # 95th percentile
            p99_time = statistics.quantiles(execution_times, n=100)[98]  # 99th percentile
            
            print(f"Search Handler Performance (with DI):")
            print(f"  Average: {avg_time:.2f}ms")
            print(f"  Median: {median_time:.2f}ms")
            print(f"  95th percentile: {p95_time:.2f}ms")
            print(f"  99th percentile: {p99_time:.2f}ms")
            
            # Assert reasonable performance
            assert avg_time < 100  # Should complete in less than 100ms with mocks
            assert p95_time < 200  # 95% of requests should complete in less than 200ms
    
    @pytest.mark.asyncio
    async def test_concurrent_request_performance(self, test_event, mock_lambda_context):
        """Test performance under concurrent load."""
        with patch.dict('os.environ', {'ENVIRONMENT': 'test', 'USE_MOCK_SERVICES': 'true'}):
            container = get_container()
            handler = SearchHandler(container)
            
            # Test concurrent requests
            concurrent_requests = 20
            
            async def make_request():
                start_time = time.perf_counter()
                response = await handler.handle(test_event, mock_lambda_context)
                end_time = time.perf_counter()
                return response, (end_time - start_time) * 1000
            
            # Execute concurrent requests
            start_time = time.perf_counter()
            tasks = [make_request() for _ in range(concurrent_requests)]
            results = await asyncio.gather(*tasks)
            total_time = (time.perf_counter() - start_time) * 1000
            
            # Analyze results
            execution_times = [result[1] for result in results]
            successful_requests = sum(1 for result in results if result[0]['statusCode'] == 200)
            
            avg_time = statistics.mean(execution_times)
            throughput = (concurrent_requests / total_time) * 1000  # requests per second
            
            print(f"Concurrent Request Performance:")
            print(f"  Concurrent requests: {concurrent_requests}")
            print(f"  Successful requests: {successful_requests}")
            print(f"  Total time: {total_time:.2f}ms")
            print(f"  Average request time: {avg_time:.2f}ms")
            print(f"  Throughput: {throughput:.2f} requests/second")
            
            # Assert performance
            assert successful_requests == concurrent_requests
            assert avg_time < 150  # Should handle concurrent load well
            assert throughput > 50  # Should handle at least 50 requests per second
    
    @pytest.mark.asyncio
    async def test_memory_usage_comparison(self, test_event, mock_lambda_context):
        """Test memory usage of new architecture."""
        import psutil
        import gc
        
        with patch.dict('os.environ', {'ENVIRONMENT': 'test', 'USE_MOCK_SERVICES': 'true'}):
            # Measure memory before initialization
            gc.collect()
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Initialize container
            container = get_container()
            handler = SearchHandler(container)
            
            # Measure memory after initialization
            gc.collect()
            memory_after_init = process.memory_info().rss / 1024 / 1024  # MB
            
            # Execute requests and measure memory
            for i in range(10):
                await handler.handle(test_event, mock_lambda_context)
            
            gc.collect()
            memory_after_requests = process.memory_info().rss / 1024 / 1024  # MB
            
            initialization_memory = memory_after_init - memory_before
            request_memory_growth = memory_after_requests - memory_after_init
            
            print(f"Memory Usage Analysis:")
            print(f"  Memory before: {memory_before:.2f}MB")
            print(f"  Memory after init: {memory_after_init:.2f}MB")
            print(f"  Memory after requests: {memory_after_requests:.2f}MB")
            print(f"  Initialization overhead: {initialization_memory:.2f}MB")
            print(f"  Request memory growth: {request_memory_growth:.2f}MB")
            
            # Assert reasonable memory usage
            assert initialization_memory < 50  # Should not use more than 50MB for initialization
            assert request_memory_growth < 10  # Should not grow more than 10MB during requests
    
    @pytest.mark.asyncio
    async def test_service_resolution_performance(self):
        """Test performance of service resolution from DI container."""
        with patch.dict('os.environ', {'ENVIRONMENT': 'test', 'USE_MOCK_SERVICES': 'true'}):
            container = get_container()
            
            # Test service resolution performance
            resolution_times = []
            service_types = [
                'ISearchResultRepository',
                'IConnectionRepository',
                'IMessageQueue',
                'IConnectionManager',
                'IProviderRegistry',
                'ILoggerFactory'
            ]
            
            for _ in range(100):
                for service_type in service_types:
                    start_time = time.perf_counter()
                    service = container.resolve(service_type)
                    end_time = time.perf_counter()
                    
                    resolution_time = (end_time - start_time) * 1000000  # microseconds
                    resolution_times.append(resolution_time)
                    
                    assert service is not None
            
            avg_resolution_time = statistics.mean(resolution_times)
            max_resolution_time = max(resolution_times)
            
            print(f"Service Resolution Performance:")
            print(f"  Average resolution time: {avg_resolution_time:.2f}μs")
            print(f"  Max resolution time: {max_resolution_time:.2f}μs")
            print(f"  Total resolutions tested: {len(resolution_times)}")
            
            # Assert fast service resolution
            assert avg_resolution_time < 100  # Should resolve in less than 100 microseconds
            assert max_resolution_time < 1000  # No resolution should take more than 1ms
    
    @pytest.mark.asyncio
    async def test_error_handling_performance(self, mock_lambda_context):
        """Test performance of error handling in new architecture."""
        with patch.dict('os.environ', {'ENVIRONMENT': 'test', 'USE_MOCK_SERVICES': 'true'}):
            container = get_container()
            handler = SearchHandler(container)
            
            # Test with invalid events
            invalid_events = [
                {'body': '{"invalid": "json"}'},  # Missing required fields
                {'body': 'invalid json'},  # Invalid JSON
                {'body': json.dumps({'address': 'not an object'})},  # Invalid address
                {}  # Empty event
            ]
            
            error_handling_times = []
            
            for invalid_event in invalid_events:
                for _ in range(10):  # Test each error scenario multiple times
                    _, exec_time = await self.measure_async_execution_time(
                        handler.handle, invalid_event, mock_lambda_context
                    )
                    error_handling_times.append(exec_time)
            
            avg_error_time = statistics.mean(error_handling_times)
            max_error_time = max(error_handling_times)
            
            print(f"Error Handling Performance:")
            print(f"  Average error handling time: {avg_error_time:.2f}ms")
            print(f"  Max error handling time: {max_error_time:.2f}ms")
            print(f"  Error scenarios tested: {len(error_handling_times)}")
            
            # Error handling should be fast
            assert avg_error_time < 50  # Should handle errors in less than 50ms
            assert max_error_time < 100  # No error should take more than 100ms
    
    @pytest.mark.asyncio
    async def test_scalability_simulation(self, test_event, mock_lambda_context):
        """Simulate scaling behavior under increasing load."""
        with patch.dict('os.environ', {'ENVIRONMENT': 'test', 'USE_MOCK_SERVICES': 'true'}):
            container = get_container()
            handler = SearchHandler(container)
            
            # Test with increasing concurrent loads
            load_levels = [1, 5, 10, 20, 50]
            results = {}
            
            for load_level in load_levels:
                async def make_request():
                    start_time = time.perf_counter()
                    response = await handler.handle(test_event, mock_lambda_context)
                    end_time = time.perf_counter()
                    return response['statusCode'] == 200, (end_time - start_time) * 1000
                
                # Execute concurrent requests
                start_time = time.perf_counter()
                tasks = [make_request() for _ in range(load_level)]
                request_results = await asyncio.gather(*tasks)
                total_time = (time.perf_counter() - start_time) * 1000
                
                # Analyze results
                successful_requests = sum(1 for success, _ in request_results if success)
                execution_times = [time for _, time in request_results]
                avg_time = statistics.mean(execution_times)
                throughput = (load_level / total_time) * 1000
                
                results[load_level] = {
                    'success_rate': successful_requests / load_level,
                    'avg_response_time': avg_time,
                    'throughput': throughput,
                    'total_time': total_time
                }
                
                print(f"Load Level {load_level}:")
                print(f"  Success rate: {results[load_level]['success_rate']:.2%}")
                print(f"  Avg response time: {avg_time:.2f}ms")
                print(f"  Throughput: {throughput:.2f} req/s")
                print(f"  Total time: {total_time:.2f}ms")
                print()
            
            # Verify scalability
            for load_level in load_levels:
                assert results[load_level]['success_rate'] >= 0.95  # At least 95% success rate
                assert results[load_level]['avg_response_time'] < 200  # Response time under 200ms
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_performance(self, test_event, mock_lambda_context):
        """Test performance of resource cleanup and garbage collection."""
        import gc
        
        with patch.dict('os.environ', {'ENVIRONMENT': 'test', 'USE_MOCK_SERVICES': 'true'}):
            # Create multiple containers to test cleanup
            containers = []
            handlers = []
            
            creation_times = []
            cleanup_times = []
            
            # Create and cleanup multiple instances
            for i in range(10):
                # Measure creation time
                start_time = time.perf_counter()
                container = get_container()
                handler = SearchHandler(container)
                creation_time = (time.perf_counter() - start_time) * 1000
                creation_times.append(creation_time)
                
                containers.append(container)
                handlers.append(handler)
                
                # Execute a request
                await handler.handle(test_event, mock_lambda_context)
            
            # Measure cleanup time
            start_time = time.perf_counter()
            
            # Clear references
            containers.clear()
            handlers.clear()
            
            # Force garbage collection
            gc.collect()
            
            cleanup_time = (time.perf_counter() - start_time) * 1000
            
            avg_creation_time = statistics.mean(creation_times)
            
            print(f"Resource Management Performance:")
            print(f"  Average creation time: {avg_creation_time:.2f}ms")
            print(f"  Cleanup time: {cleanup_time:.2f}ms")
            print(f"  Instances created/cleaned: 10")
            
            # Assert reasonable resource management
            assert avg_creation_time < 200  # Should create instances quickly
            assert cleanup_time < 100  # Should cleanup quickly


if __name__ == "__main__":
    pytest.main([__file__])