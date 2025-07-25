"""Tests for middleware components."""

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.shared.middleware.circuit_breaker import CircuitBreaker, CircuitBreakerState
from src.shared.middleware.error_handler import HttpErrorHandler, LambdaErrorHandler
from src.shared.middleware.retry_handler import ExponentialBackoffRetryHandler


class TestCircuitBreaker:
    @pytest.fixture
    def circuit_breaker(self):
        """Create CircuitBreaker instance."""
        return CircuitBreaker(
            service_name="test-service", failure_threshold=3, recovery_timeout=5.0, expected_exception=Exception
        )

    def test_circuit_breaker_initialization(self, circuit_breaker):
        """Test CircuitBreaker initialization."""
        assert circuit_breaker.service_name == "test-service"
        assert circuit_breaker.failure_threshold == 3
        assert circuit_breaker.recovery_timeout == 5.0
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_successful_call(self, circuit_breaker):
        """Test successful function call."""

        async def successful_function():
            return "success"

        result = await circuit_breaker.call(successful_function)
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_below_threshold(self, circuit_breaker):
        """Test failure below threshold."""

        async def failing_function():
            raise Exception("Test error")

        with pytest.raises(Exception):
            await circuit_breaker.call(failing_function)

        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self, circuit_breaker):
        """Test circuit breaker opens after failure threshold."""

        async def failing_function():
            raise Exception("Test error")

        # Fail 3 times to reach threshold
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_function)

        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 3

    def test_circuit_breaker_reset(self, circuit_breaker):
        """Test circuit breaker reset."""
        # Manually set to open state
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.failure_count = 3

        # Reset
        circuit_breaker.force_close()
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0


class TestErrorHandler:
    @pytest.fixture
    def lambda_error_handler(self):
        """Create LambdaErrorHandler instance."""
        return LambdaErrorHandler()

    @pytest.fixture
    def http_error_handler(self):
        """Create HttpErrorHandler instance."""
        return HttpErrorHandler()

    def test_lambda_error_handler_initialization(self, lambda_error_handler):
        """Test LambdaErrorHandler initialization."""
        assert lambda_error_handler.logger is None

    def test_lambda_error_handler_with_logger(self, lambda_error_handler):
        """Test LambdaErrorHandler with logger."""
        mock_logger = Mock()
        lambda_error_handler.logger = mock_logger

        error = ValueError("Test error")
        response = lambda_error_handler.handle_error(error)

        assert response["statusCode"] == 500
        assert "error" in response["body"]
        assert mock_logger.error.called

    def test_lambda_error_handler_unexpected_error(self, lambda_error_handler):
        """Test LambdaErrorHandler with unexpected error."""
        error = ValueError("Test error")
        response = lambda_error_handler.handle_error(error)

        assert response["statusCode"] == 500
        body = response["body"]
        assert "error" in body
        assert "error_code" in body
        assert "message" in body

    def test_http_error_handler_initialization(self, http_error_handler):
        """Test HttpErrorHandler initialization."""
        assert http_error_handler.logger is None

    def test_http_error_handler_unexpected_error(self, http_error_handler):
        """Test HttpErrorHandler with unexpected error."""
        error = ValueError("Test error")
        response = http_error_handler.handle_error(error)

        assert response["status_code"] == 500
        assert "data" in response
        assert "error" in response["data"]


class TestRetryHandler:
    @pytest.fixture
    def retry_handler(self):
        """Create ExponentialBackoffRetryHandler instance."""
        return ExponentialBackoffRetryHandler(
            max_retries=3, base_delay=1.0, max_delay=10.0, retryable_exceptions=[ValueError, TypeError]
        )

    def test_retry_handler_initialization(self, retry_handler):
        """Test RetryHandler initialization."""
        assert retry_handler.max_retries == 3
        assert retry_handler.base_delay == 1.0
        assert retry_handler.max_delay == 10.0
        assert ValueError in retry_handler.retryable_exceptions
        assert TypeError in retry_handler.retryable_exceptions

    @pytest.mark.asyncio
    async def test_retry_handler_success_on_first_try(self, retry_handler):
        """Test successful execution on first try."""

        async def successful_function():
            return "success"

        result = await retry_handler.execute_with_retry(successful_function)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_handler_success_after_retries(self, retry_handler):
        """Test successful execution after retries."""
        call_count = 0

        async def failing_then_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Error")
            return "success"

        result = await retry_handler.execute_with_retry(failing_then_successful)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_handler_max_retries_exceeded(self, retry_handler):
        """Test max retries exceeded."""

        async def always_failing():
            raise ValueError("Persistent error")

        with pytest.raises(ValueError):
            await retry_handler.execute_with_retry(always_failing)

    @pytest.mark.asyncio
    async def test_retry_handler_non_retryable_exception(self, retry_handler):
        """Test non-retryable exception."""

        async def non_retryable_error():
            raise RuntimeError("Non-retryable error")

        with pytest.raises(RuntimeError):
            await retry_handler.execute_with_retry(non_retryable_error)

    def test_retry_handler_exponential_backoff(self, retry_handler):
        """Test exponential backoff delay calculation."""
        delay = retry_handler.get_delay(1)
        assert delay >= retry_handler.base_delay

        delay = retry_handler.get_delay(2)
        assert delay >= retry_handler.base_delay * 2

        delay = retry_handler.get_delay(3)
        assert delay >= retry_handler.base_delay * 4

    def test_retry_handler_max_delay_limit(self, retry_handler):
        """Test max delay limit."""
        delay = retry_handler.get_delay(10)
        assert delay <= retry_handler.max_delay  # Should not exceed max_delay

    @pytest.mark.asyncio
    async def test_retry_handler_with_context(self, retry_handler):
        """Test retry handler with context."""
        call_count = 0

        async def failing_then_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Error")
            return "success"

        result = await retry_handler.execute_with_retry(failing_then_successful)
        assert result == "success"
        assert call_count == 2
