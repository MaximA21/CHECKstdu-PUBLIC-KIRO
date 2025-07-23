"""
Load test runner for basic performance testing.
This module provides simple load testing capabilities for the application.
"""

import asyncio
import time
import statistics
import concurrent.futures
from typing import List, Dict, Any, Callable
from dataclasses import dataclass
from unittest.mock import patch
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.shared.dependency_injection.bootstrap import bootstrap_container
from src.application.use_cases.search_offers_use_case import SearchOffersUseCase
from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from src.domain.value_objects.address import Address


@dataclass
class LoadTestResult:
    """Results from a load test execution."""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    requests_per_second: float
    error_rate: float
    errors: List[str]


class LoadTestRunner:
    """Simple load test runner for basic performance validation."""
    
    def __init__(self):
        self.results: List[LoadTestResult] = []
    
    def run_concurrent_requests(
        self,
        test_function: Callable,
        num_requests: int,
        max_workers: int = 10,
        test_name: str = "Load Test"
    ) -> LoadTestResult:
        """Run concurrent requests and measure performance."""
        
        response_times = []
        errors = []
        successful_requests = 0
        failed_requests = 0
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all requests
            futures = []
            for i in range(num_requests):
                future = executor.submit(self._execute_request, test_function, i)
                futures.append(future)
            
            # Collect results
            for future in concurrent.futures.as_completed(futures):
                try:
                    response_time, error = future.result()
                    if error:
                        failed_requests += 1
                        errors.append(error)
                    else:
                        successful_requests += 1
                        response_times.append(response_time)
                except Exception as e:
                    failed_requests += 1
                    errors.append(str(e))
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Calculate statistics
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p95_response_time = self._percentile(response_times, 95)
        else:
            avg_response_time = min_response_time = max_response_time = p95_response_time = 0
        
        requests_per_second = num_requests / total_duration if total_duration > 0 else 0
        error_rate = (failed_requests / num_requests) * 100 if num_requests > 0 else 0
        
        result = LoadTestResult(
            test_name=test_name,
            total_requests=num_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate,
            errors=errors[:10]  # Keep only first 10 errors
        )
        
        self.results.append(result)
        return result
    
    def _execute_request(self, test_function: Callable, request_id: int) -> tuple:
        """Execute a single request and measure response time."""
        start_time = time.time()
        error = None
        
        try:
            test_function(request_id)
        except Exception as e:
            error = f"Request {request_id}: {str(e)}"
        
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        return response_time, error
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of a dataset."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        if index >= len(sorted_data):
            index = len(sorted_data) - 1
        return sorted_data[index]
    
    def print_results(self):
        """Print load test results in a readable format."""
        print("\n" + "="*80)
        print("LOAD TEST RESULTS")
        print("="*80)
        
        for result in self.results:
            print(f"\nTest: {result.test_name}")
            print(f"Total Requests: {result.total_requests}")
            print(f"Successful: {result.successful_requests}")
            print(f"Failed: {result.failed_requests}")
            print(f"Error Rate: {result.error_rate:.2f}%")
            print(f"Requests/Second: {result.requests_per_second:.2f}")
            print(f"Response Times (ms):")
            print(f"  Average: {result.avg_response_time:.2f}")
            print(f"  Min: {result.min_response_time:.2f}")
            print(f"  Max: {result.max_response_time:.2f}")
            print(f"  95th Percentile: {result.p95_response_time:.2f}")
            
            if result.errors:
                print(f"Sample Errors:")
                for error in result.errors[:5]:
                    print(f"  - {error}")
            
            # Performance assertions
            if result.error_rate > 5.0:
                print(f"⚠️  High error rate: {result.error_rate:.2f}%")
            if result.avg_response_time > 1000:
                print(f"⚠️  High average response time: {result.avg_response_time:.2f}ms")
            if result.requests_per_second < 10:
                print(f"⚠️  Low throughput: {result.requests_per_second:.2f} RPS")


def run_basic_load_tests():
    """Run basic load tests for key application components."""
    
    print("Starting basic load tests...")
    
    # Set up test environment
    test_env = {
        'ENVIRONMENT': 'test',
        'USE_MOCK_SERVICES': 'true',
        'AWS_REGION': 'us-east-1'
    }
    
    with patch.dict(os.environ, test_env):
        runner = LoadTestRunner()
        
        # Test 1: Search offers load test
        def search_offers_test(request_id: int):
            container = bootstrap_container()
            search_use_case = container.get(SearchOffersUseCase)
            
            address = Address(
                street=f"Test Street {request_id}",
                house_number=str(request_id % 100),
                city="Berlin",
                postal_code="10115",
                country="DE"
            )
            
            # Execute search
            result = asyncio.run(search_use_case.execute(address))
            
            # Basic validation
            if not result or not hasattr(result, 'request_id'):
                raise Exception("Invalid search result")
        
        print("Running search offers load test...")
        search_result = runner.run_concurrent_requests(
            test_function=search_offers_test,
            num_requests=50,
            max_workers=10,
            test_name="Search Offers Load Test"
        )
        
        # Test 2: Connection management load test
        def connection_test(request_id: int):
            container = bootstrap_container()
            connection_use_case = container.get(ConnectionManagementUseCase)
            
            connection_id = f"test-connection-{request_id}"
            
            # Create connection
            session = asyncio.run(connection_use_case.create_connection(connection_id))
            
            # Validate connection
            if not session or not session.connection_id:
                raise Exception("Failed to create connection")
            
            # Close connection
            asyncio.run(connection_use_case.close_connection(connection_id))
        
        print("Running connection management load test...")
        connection_result = runner.run_concurrent_requests(
            test_function=connection_test,
            num_requests=30,
            max_workers=8,
            test_name="Connection Management Load Test"
        )
        
        # Test 3: Dependency injection container load test
        def di_container_test(request_id: int):
            # Test container resolution performance
            container = bootstrap_container()
            
            # Resolve multiple services
            search_use_case = container.get(SearchOffersUseCase)
            connection_use_case = container.get(ConnectionManagementUseCase)
            
            # Validate services
            if not search_use_case or not connection_use_case:
                raise Exception("Failed to resolve services from container")
        
        print("Running DI container load test...")
        di_result = runner.run_concurrent_requests(
            test_function=di_container_test,
            num_requests=100,
            max_workers=15,
            test_name="DI Container Load Test"
        )
        
        # Print all results
        runner.print_results()
        
        # Overall assessment
        print("\n" + "="*80)
        print("LOAD TEST ASSESSMENT")
        print("="*80)
        
        total_tests = len(runner.results)
        passed_tests = sum(1 for r in runner.results if r.error_rate <= 5.0 and r.avg_response_time <= 1000)
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed Tests: {passed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if passed_tests == total_tests:
            print("✅ All load tests passed performance criteria")
        else:
            print("⚠️ Some load tests exceeded performance thresholds")
            
        # Performance criteria validation
        performance_issues = []
        for result in runner.results:
            if result.error_rate > 5.0:
                performance_issues.append(f"{result.test_name}: High error rate ({result.error_rate:.1f}%)")
            if result.avg_response_time > 1000:
                performance_issues.append(f"{result.test_name}: High response time ({result.avg_response_time:.1f}ms)")
            if result.requests_per_second < 10:
                performance_issues.append(f"{result.test_name}: Low throughput ({result.requests_per_second:.1f} RPS)")
        
        if performance_issues:
            print("\nPerformance Issues Detected:")
            for issue in performance_issues:
                print(f"  - {issue}")
        
        return runner.results


if __name__ == "__main__":
    run_basic_load_tests()