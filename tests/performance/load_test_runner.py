"""Load testing runner for performance testing."""

import asyncio
import json
import logging
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LoadTestResult:
    """Results from a load test execution."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    min_response_time: float
    max_response_time: float
    percentile_95: float
    percentile_99: float
    requests_per_second: float
    error_rate: float
    errors: List[str]
    duration_seconds: float


@dataclass
class LoadTestConfig:
    """Configuration for load testing."""

    concurrent_users: int = 10
    requests_per_user: int = 10
    ramp_up_time: float = 1.0  # seconds
    test_duration: Optional[float] = None  # seconds, None for request-based
    target_function: Optional[Callable] = None
    test_data_generator: Optional[Callable] = None


class LoadTestRunner:
    """Load test runner for performance testing."""

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[float] = []
        self.errors: List[str] = []
        self.start_time: float = 0
        self.end_time: float = 0

    async def run_async_load_test(self, async_target_function: Callable) -> LoadTestResult:
        """Run load test with async target function."""
        logger.info(
            f"Starting async load test with {self.config.concurrent_users} users, "
            f"{self.config.requests_per_user} requests per user"
        )

        self.start_time = time.time()

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.config.concurrent_users)

        # Generate tasks
        tasks = []
        for user_id in range(self.config.concurrent_users):
            for request_id in range(self.config.requests_per_user):
                task = self._create_async_task(semaphore, async_target_function, user_id, request_id)
                tasks.append(task)

        # Execute all tasks
        await asyncio.gather(*tasks, return_exceptions=True)

        self.end_time = time.time()
        return self._calculate_results()

    def run_sync_load_test(self, sync_target_function: Callable) -> LoadTestResult:
        """Run load test with synchronous target function."""
        logger.info(
            f"Starting sync load test with {self.config.concurrent_users} users, "
            f"{self.config.requests_per_user} requests per user"
        )

        self.start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.config.concurrent_users) as executor:
            # Submit all tasks
            futures = []
            for user_id in range(self.config.concurrent_users):
                for request_id in range(self.config.requests_per_user):
                    future = executor.submit(self._execute_sync_request, sync_target_function, user_id, request_id)
                    futures.append(future)

            # Wait for all tasks to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.errors.append(str(e))

        self.end_time = time.time()
        return self._calculate_results()

    async def _create_async_task(self, semaphore: asyncio.Semaphore, target_function: Callable, user_id: int, request_id: int):
        """Create and execute async task with semaphore."""
        async with semaphore:
            # Add ramp-up delay
            if self.config.ramp_up_time > 0:
                delay = (user_id * self.config.ramp_up_time) / self.config.concurrent_users
                await asyncio.sleep(delay)

            await self._execute_async_request(target_function, user_id, request_id)

    async def _execute_async_request(self, target_function: Callable, user_id: int, request_id: int):
        """Execute single async request and record timing."""
        start_time = time.time()
        try:
            # Generate test data if generator provided
            test_data = None
            if self.config.test_data_generator:
                test_data = self.config.test_data_generator(user_id, request_id)

            # Execute target function
            if test_data:
                await target_function(test_data)
            else:
                await target_function()

            # Record successful request time
            response_time = time.time() - start_time
            self.results.append(response_time)

        except Exception as e:
            self.errors.append(f"User {user_id}, Request {request_id}: {str(e)}")
            logger.error(f"Request failed: {e}")

    def _execute_sync_request(self, target_function: Callable, user_id: int, request_id: int):
        """Execute single sync request and record timing."""
        # Add ramp-up delay
        if self.config.ramp_up_time > 0:
            delay = (user_id * self.config.ramp_up_time) / self.config.concurrent_users
            time.sleep(delay)

        start_time = time.time()
        try:
            # Generate test data if generator provided
            test_data = None
            if self.config.test_data_generator:
                test_data = self.config.test_data_generator(user_id, request_id)

            # Execute target function
            if test_data:
                target_function(test_data)
            else:
                target_function()

            # Record successful request time
            response_time = time.time() - start_time
            self.results.append(response_time)

        except Exception as e:
            self.errors.append(f"User {user_id}, Request {request_id}: {str(e)}")
            logger.error(f"Request failed: {e}")

    def _calculate_results(self) -> LoadTestResult:
        """Calculate and return load test results."""
        total_requests = self.config.concurrent_users * self.config.requests_per_user
        successful_requests = len(self.results)
        failed_requests = len(self.errors)
        duration = self.end_time - self.start_time

        if not self.results:
            # No successful requests
            return LoadTestResult(
                total_requests=total_requests,
                successful_requests=0,
                failed_requests=failed_requests,
                average_response_time=0.0,
                min_response_time=0.0,
                max_response_time=0.0,
                percentile_95=0.0,
                percentile_99=0.0,
                requests_per_second=0.0,
                error_rate=100.0,
                errors=self.errors,
                duration_seconds=duration,
            )

        # Calculate statistics
        avg_response_time = statistics.mean(self.results)
        min_response_time = min(self.results)
        max_response_time = max(self.results)

        # Calculate percentiles
        sorted_results = sorted(self.results)
        percentile_95 = sorted_results[int(len(sorted_results) * 0.95)]
        percentile_99 = sorted_results[int(len(sorted_results) * 0.99)]

        # Calculate throughput
        requests_per_second = successful_requests / duration if duration > 0 else 0
        error_rate = (failed_requests / total_requests) * 100 if total_requests > 0 else 0

        return LoadTestResult(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            average_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            percentile_95=percentile_95,
            percentile_99=percentile_99,
            requests_per_second=requests_per_second,
            error_rate=error_rate,
            errors=self.errors,
            duration_seconds=duration,
        )

    def print_results(self, result: LoadTestResult):
        """Print formatted load test results."""
        print("\n" + "=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)
        print(f"Total Requests:        {result.total_requests}")
        print(f"Successful Requests:   {result.successful_requests}")
        print(f"Failed Requests:       {result.failed_requests}")
        print(f"Error Rate:            {result.error_rate:.2f}%")
        print(f"Test Duration:         {result.duration_seconds:.2f}s")
        print(f"Requests/Second:       {result.requests_per_second:.2f}")
        print("\nResponse Times:")
        print(f"  Average:             {result.average_response_time*1000:.2f}ms")
        print(f"  Minimum:             {result.min_response_time*1000:.2f}ms")
        print(f"  Maximum:             {result.max_response_time*1000:.2f}ms")
        print(f"  95th Percentile:     {result.percentile_95*1000:.2f}ms")
        print(f"  99th Percentile:     {result.percentile_99*1000:.2f}ms")

        if result.errors:
            print(f"\nFirst 5 Errors:")
            for error in result.errors[:5]:
                print(f"  - {error}")

        print("=" * 60)

    def save_results_to_file(self, result: LoadTestResult, filename: str):
        """Save results to JSON file."""
        result_dict = {
            "total_requests": result.total_requests,
            "successful_requests": result.successful_requests,
            "failed_requests": result.failed_requests,
            "average_response_time": result.average_response_time,
            "min_response_time": result.min_response_time,
            "max_response_time": result.max_response_time,
            "percentile_95": result.percentile_95,
            "percentile_99": result.percentile_99,
            "requests_per_second": result.requests_per_second,
            "error_rate": result.error_rate,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
            "timestamp": time.time(),
        }

        with open(filename, "w") as f:
            json.dump(result_dict, f, indent=2)

        logger.info(f"Results saved to {filename}")


# Example usage functions for testing different components
async def example_async_search_load_test():
    """Example load test for async search functionality."""
    from src.application.use_cases.search_offers_use_case import SearchOffersUseCase
    from src.shared.dependency_injection import get_container

    def test_data_generator(user_id: int, request_id: int) -> Dict[str, Any]:
        return {
            "address": {"street": f"Test Street {user_id}", "city": "Berlin", "postal_code": "10115", "country": "Germany"},
            "connection_id": f"test-conn-{user_id}-{request_id}",
        }

    async def search_target(test_data: Dict[str, Any]):
        container = get_container()
        search_use_case = container.resolve(SearchOffersUseCase)
        await search_use_case.execute(test_data)

    config = LoadTestConfig(
        concurrent_users=5, requests_per_user=10, ramp_up_time=2.0, test_data_generator=test_data_generator
    )

    runner = LoadTestRunner(config)
    result = await runner.run_async_load_test(search_target)
    runner.print_results(result)
    return result


def example_sync_di_container_load_test():
    """Example load test for DI container performance."""
    from src.application.interfaces.logging import ILogger
    from src.infrastructure.logging.console_logger import ConsoleLogger
    from src.shared.dependency_injection import DIContainer

    def container_target():
        container = DIContainer()
        container.register(ILogger, ConsoleLogger)
        logger = container.resolve(ILogger)
        logger.info("Test message")

    config = LoadTestConfig(concurrent_users=10, requests_per_user=50, ramp_up_time=1.0)

    runner = LoadTestRunner(config)
    result = runner.run_sync_load_test(container_target)
    runner.print_results(result)
    return result


if __name__ == "__main__":
    # Run example load tests
    print("Running DI Container Load Test...")
    example_sync_di_container_load_test()

    print("\nRunning Async Search Load Test...")
    asyncio.run(example_async_search_load_test())
