"""Unit tests for retry handler middleware."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.application.interfaces.logging import ILogger
from src.shared.exceptions import (
    BaseApplicationException,
    ErrorCategory,
    ErrorSeverity,
    ExternalServiceException,
    InfrastructureException,
    RetryableException,
    ValidationException,
)
from src.shared.exceptions.infrastructure import DatabaseConnectionException
from src.shared.middleware.retry_handler import (
    ExponentialBackoffRetryHandler,
    GracefulDegradationHandler,
    RetryHandler,
    retry_on_failure,
    with_fallback,
)


class TestRetryHandler:
    """Test cases for RetryHandler base class."""

    def test_init_with_defaults(self):
        """Test RetryHandler initialization with defaults."""

        class TestRetryHandler(RetryHandler):
            def get_delay(self, attempt):
                return self.base_delay

            def should_retry(self, error, attempt):
                return True

        handler = TestRetryHandler()

        assert handler.max_retries == 3
        assert handler.base_delay == 1.0
        assert handler.logger is None

    def test_init_with_custom_parameters(self):
        """Test RetryHandler initialization with custom parameters."""
        mock_logger = Mock(spec=ILogger)

        class TestRetryHandler(RetryHandler):
            def get_delay(self, attempt):
                return self.base_delay

            def should_retry(self, error, attempt):
                return True

        handler = TestRetryHandler(max_retries=5, base_delay=2.0, logger=mock_logger)

        assert handler.max_retries == 5
        assert handler.base_delay == 2.0
        assert handler.logger is mock_logger

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_first_attempt(self):
        """Test successful execution on first attempt."""

        class TestRetryHandler(RetryHandler):
            def get_delay(self, attempt):
                return 0.01  # Short delay for testing

            def should_retry(self, error, attempt):
                return True

        handler = TestRetryHandler()

        async def success_func():
            return "success"

        result = await handler.execute_with_retry(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_sync_function(self):
        """Test retry with synchronous function."""

        class TestRetryHandler(RetryHandler):
            def get_delay(self, attempt):
                return 0.01

            def should_retry(self, error, attempt):
                return True

        handler = TestRetryHandler()

        def sync_func():
            return "sync_success"

        result = await handler.execute_with_retry(sync_func)
        assert result == "sync_success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_failures(self):
        """Test successful execution after some failures."""
        mock_logger = Mock(spec=ILogger)

        class TestRetryHandler(RetryHandler):
            def get_delay(self, attempt):
                return 0.01

            def should_retry(self, error, attempt):
                return True

        handler = TestRetryHandler(logger=mock_logger)

        call_count = 0

        async def intermittent_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError(f"Failure {call_count}")
            return "success_after_retries"

        result = await handler.execute_with_retry(intermittent_func)

        assert result == "success_after_retries"
        assert call_count == 3

        # Verify retry warnings were logged
        assert mock_logger.warning.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_retry_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        mock_logger = Mock(spec=ILogger)

        class TestRetryHandler(RetryHandler):
            def get_delay(self, attempt):
                return 0.01

            def should_retry(self, error, attempt):
                return True

        handler = TestRetryHandler(max_retries=2, logger=mock_logger)

        call_count = 0

        async def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Failure {call_count}")

        with pytest.raises(ValueError, match="Failure 3"):
            await handler.execute_with_retry(always_failing_func)

        assert call_count == 3  # Initial call + 2 retries

        # Verify error was logged
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args
        assert "All retry attempts failed" in error_call[0][0]

    @pytest.mark.asyncio
    async def test_execute_with_retry_should_not_retry(self):
        """Test behavior when should_retry returns False."""
        mock_logger = Mock(spec=ILogger)

        class TestRetryHandler(RetryHandler):
            def get_delay(self, attempt):
                return 0.01

            def should_retry(self, error, attempt):
                return False  # Never retry

        handler = TestRetryHandler(logger=mock_logger)

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("No retry error")

        with pytest.raises(ValueError, match="No retry error"):
            await handler.execute_with_retry(failing_func)

        assert call_count == 1  # Only initial call, no retries

        # Should log error but no retry warnings
        mock_logger.error.assert_called()
        mock_logger.warning.assert_not_called()


class TestExponentialBackoffRetryHandler:
    """Test cases for ExponentialBackoffRetryHandler."""

    def test_init_with_defaults(self):
        """Test ExponentialBackoffRetryHandler initialization with defaults."""
        handler = ExponentialBackoffRetryHandler()

        assert handler.max_retries == 3
        assert handler.base_delay == 1.0
        assert handler.backoff_multiplier == 2.0
        assert handler.max_delay == 60.0
        assert handler.jitter is True
        assert RetryableException in handler.retryable_exceptions
        assert ExternalServiceException in handler.retryable_exceptions
        assert InfrastructureException in handler.retryable_exceptions

    def test_init_with_custom_parameters(self):
        """Test ExponentialBackoffRetryHandler initialization with custom parameters."""
        custom_exceptions = [ValueError, TypeError]
        mock_logger = Mock(spec=ILogger)

        handler = ExponentialBackoffRetryHandler(
            max_retries=5,
            base_delay=0.5,
            backoff_multiplier=3.0,
            max_delay=30.0,
            jitter=False,
            retryable_exceptions=custom_exceptions,
            logger=mock_logger,
        )

        assert handler.max_retries == 5
        assert handler.base_delay == 0.5
        assert handler.backoff_multiplier == 3.0
        assert handler.max_delay == 30.0
        assert handler.jitter is False
        assert handler.retryable_exceptions == custom_exceptions
        assert handler.logger is mock_logger

    def test_get_delay_exponential_backoff(self):
        """Test exponential backoff delay calculation."""
        handler = ExponentialBackoffRetryHandler(base_delay=1.0, backoff_multiplier=2.0, jitter=False)

        assert handler.get_delay(0) == 1.0  # 1.0 * 2^0
        assert handler.get_delay(1) == 2.0  # 1.0 * 2^1
        assert handler.get_delay(2) == 4.0  # 1.0 * 2^2
        assert handler.get_delay(3) == 8.0  # 1.0 * 2^3

    def test_get_delay_with_max_delay(self):
        """Test delay calculation with max delay limit."""
        handler = ExponentialBackoffRetryHandler(base_delay=1.0, backoff_multiplier=2.0, max_delay=5.0, jitter=False)

        assert handler.get_delay(0) == 1.0
        assert handler.get_delay(1) == 2.0
        assert handler.get_delay(2) == 4.0
        assert handler.get_delay(3) == 5.0  # Capped at max_delay
        assert handler.get_delay(4) == 5.0  # Still capped

    def test_get_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        handler = ExponentialBackoffRetryHandler(base_delay=2.0, backoff_multiplier=2.0, jitter=True)

        # With jitter, delay should be between 50% and 100% of calculated value
        delay = handler.get_delay(1)  # Base calculation: 2.0 * 2^1 = 4.0
        assert 2.0 <= delay <= 4.0  # Should be between 50% and 100% of 4.0

    def test_should_retry_with_retryable_exception(self):
        """Test should_retry with RetryableException."""
        handler = ExponentialBackoffRetryHandler()

        retryable_error = RetryableException("Retryable error")
        assert handler.should_retry(retryable_error, 0) is True

    def test_should_retry_with_retryable_exception_should_not_retry(self):
        """Test should_retry with RetryableException that should not retry."""
        handler = ExponentialBackoffRetryHandler()

        retryable_error = RetryableException("Non-retryable error")
        with patch.object(retryable_error, "should_retry", return_value=False):
            assert handler.should_retry(retryable_error, 0) is False

    def test_should_retry_with_external_service_exception(self):
        """Test should_retry with ExternalServiceException."""
        handler = ExponentialBackoffRetryHandler()

        external_error = ExternalServiceException("Service unavailable")
        assert handler.should_retry(external_error, 0) is True

    def test_should_retry_with_critical_application_exception(self):
        """Test should_retry with critical severity application exception."""
        handler = ExponentialBackoffRetryHandler()

        critical_error = BaseApplicationException(
            "Critical error", severity=ErrorSeverity.CRITICAL, category=ErrorCategory.SYSTEM
        )
        assert handler.should_retry(critical_error, 0) is False

    def test_should_retry_with_non_retryable_exception(self):
        """Test should_retry with non-retryable exception type."""
        handler = ExponentialBackoffRetryHandler(retryable_exceptions=[ValueError])

        type_error = TypeError("Type error")
        assert handler.should_retry(type_error, 0) is False

    def test_should_retry_with_validation_exception(self):
        """Test should_retry with ValidationException (not in default retryable list)."""
        handler = ExponentialBackoffRetryHandler()

        validation_error = ValidationException("Invalid input")
        assert handler.should_retry(validation_error, 0) is False

    @pytest.mark.asyncio
    async def test_integration_with_exponential_backoff(self):
        """Test integration with exponential backoff behavior."""
        handler = ExponentialBackoffRetryHandler(max_retries=2, base_delay=0.01, backoff_multiplier=2.0, jitter=False)

        call_count = 0
        delays = []

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ExternalServiceException(f"Failure {call_count}")
            return "success"

        # Mock sleep to capture delays
        with patch("asyncio.sleep") as mock_sleep:
            result = await handler.execute_with_retry(failing_func)

            assert result == "success"
            assert call_count == 3

            # Verify exponential backoff delays
            sleep_calls = mock_sleep.call_args_list
            assert len(sleep_calls) == 2  # Two retries
            assert sleep_calls[0][0][0] == 0.01  # First retry delay
            assert sleep_calls[1][0][0] == 0.02  # Second retry delay (doubled)


class TestGracefulDegradationHandler:
    """Test cases for GracefulDegradationHandler."""

    def test_init_with_defaults(self):
        """Test GracefulDegradationHandler initialization with defaults."""
        handler = GracefulDegradationHandler()

        assert handler.fallback_strategies == {}
        assert handler.logger is None
        assert handler.service_health == {}

    def test_init_with_fallback_strategies(self):
        """Test GracefulDegradationHandler initialization with fallback strategies."""
        mock_logger = Mock(spec=ILogger)
        fallback_func = Mock(return_value="fallback_result")
        strategies = {"service1": fallback_func}

        handler = GracefulDegradationHandler(strategies, mock_logger)

        assert handler.fallback_strategies == strategies
        assert handler.logger is mock_logger

    def test_register_fallback(self):
        """Test registering a fallback strategy."""
        handler = GracefulDegradationHandler()
        fallback_func = Mock(return_value="fallback")

        handler.register_fallback("test_service", fallback_func)

        assert "test_service" in handler.fallback_strategies
        assert handler.fallback_strategies["test_service"] is fallback_func

    def test_mark_service_unhealthy(self):
        """Test marking a service as unhealthy."""
        mock_logger = Mock(spec=ILogger)
        handler = GracefulDegradationHandler(logger=mock_logger)

        error = ValueError("Service error")

        with patch("time.time", return_value=1000.0):
            handler.mark_service_unhealthy("test_service", error)

        health_info = handler.service_health["test_service"]
        assert health_info["healthy"] is False
        assert health_info["last_error"] == "Service error"
        assert health_info["timestamp"] == 1000.0

        # Verify logging
        mock_logger.warning.assert_called()
        log_call = mock_logger.warning.call_args
        assert "marked as unhealthy" in log_call[0][0]

    def test_mark_service_healthy(self):
        """Test marking a service as healthy."""
        mock_logger = Mock(spec=ILogger)
        handler = GracefulDegradationHandler(logger=mock_logger)

        with patch("time.time", return_value=1000.0):
            handler.mark_service_healthy("test_service")

        health_info = handler.service_health["test_service"]
        assert health_info["healthy"] is True
        assert health_info["last_error"] is None
        assert health_info["timestamp"] == 1000.0

        # Verify logging
        mock_logger.info.assert_called()
        log_call = mock_logger.info.call_args
        assert "marked as healthy" in log_call[0][0]

    def test_is_service_healthy_default(self):
        """Test is_service_healthy returns True for unknown service."""
        handler = GracefulDegradationHandler()
        assert handler.is_service_healthy("unknown_service") is True

    def test_is_service_healthy_known_service(self):
        """Test is_service_healthy with known service."""
        handler = GracefulDegradationHandler()

        # Mark service as unhealthy
        handler.service_health["test_service"] = {"healthy": False}
        assert handler.is_service_healthy("test_service") is False

        # Mark service as healthy
        handler.service_health["test_service"] = {"healthy": True}
        assert handler.is_service_healthy("test_service") is True

    @pytest.mark.asyncio
    async def test_execute_with_fallback_success(self):
        """Test successful execution without fallback."""
        mock_logger = Mock(spec=ILogger)
        handler = GracefulDegradationHandler(logger=mock_logger)

        # Mark service as initially unhealthy
        handler.service_health["test_service"] = {"healthy": False}

        async def success_func():
            return "primary_success"

        result = await handler.execute_with_fallback("test_service", success_func)

        assert result == "primary_success"
        # Service should be marked as healthy after success
        assert handler.is_service_healthy("test_service") is True

    @pytest.mark.asyncio
    async def test_execute_with_fallback_sync_function(self):
        """Test execute_with_fallback with synchronous function."""
        handler = GracefulDegradationHandler()

        def sync_func():
            return "sync_success"

        result = await handler.execute_with_fallback("test_service", sync_func)
        assert result == "sync_success"

    @pytest.mark.asyncio
    async def test_execute_with_fallback_primary_fails_fallback_succeeds(self):
        """Test fallback execution when primary function fails."""
        mock_logger = Mock(spec=ILogger)
        fallback_func = AsyncMock(return_value="fallback_success")
        handler = GracefulDegradationHandler({"test_service": fallback_func}, mock_logger)

        async def failing_func():
            raise ValueError("Primary failure")

        result = await handler.execute_with_fallback("test_service", failing_func)

        assert result == "fallback_success"
        fallback_func.assert_called_once()

        # Service should be marked as unhealthy
        assert handler.is_service_healthy("test_service") is False

        # Verify logging
        mock_logger.info.assert_called()
        log_call = mock_logger.info.call_args
        assert "Using fallback strategy" in log_call[0][0]

    @pytest.mark.asyncio
    async def test_execute_with_fallback_sync_fallback(self):
        """Test fallback execution with synchronous fallback function."""
        mock_logger = Mock(spec=ILogger)
        fallback_func = Mock(return_value="sync_fallback")
        handler = GracefulDegradationHandler({"test_service": fallback_func}, mock_logger)

        async def failing_func():
            raise ValueError("Primary failure")

        result = await handler.execute_with_fallback("test_service", failing_func)

        assert result == "sync_fallback"
        fallback_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_fallback_both_fail(self):
        """Test behavior when both primary and fallback functions fail."""
        mock_logger = Mock(spec=ILogger)
        fallback_func = AsyncMock(side_effect=RuntimeError("Fallback failure"))
        handler = GracefulDegradationHandler({"test_service": fallback_func}, mock_logger)

        async def failing_func():
            raise ValueError("Primary failure")

        with pytest.raises(RuntimeError, match="Fallback failure"):
            await handler.execute_with_fallback("test_service", failing_func)

        # Verify error logging
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args
        assert "Fallback strategy failed" in error_call[0][0]

    @pytest.mark.asyncio
    async def test_execute_with_fallback_no_fallback_available(self):
        """Test behavior when no fallback is available."""
        mock_logger = Mock(spec=ILogger)
        handler = GracefulDegradationHandler(logger=mock_logger)

        async def failing_func():
            raise ValueError("Primary failure")

        with pytest.raises(ValueError, match="Primary failure"):
            await handler.execute_with_fallback("test_service", failing_func)

        # Verify error logging
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args
        assert "No fallback strategy available" in error_call[0][0]


class TestRetryDecorators:
    """Test cases for retry decorators."""

    @pytest.mark.asyncio
    async def test_retry_on_failure_decorator_async_success(self):
        """Test retry_on_failure decorator with successful async function."""

        @retry_on_failure(max_retries=2, base_delay=0.01)
        async def success_func():
            return "async_success"

        result = await success_func()
        assert result == "async_success"

    @pytest.mark.asyncio
    async def test_retry_on_failure_decorator_async_with_retries(self):
        """Test retry_on_failure decorator with async function that succeeds after retries."""
        call_count = 0

        @retry_on_failure(max_retries=2, base_delay=0.01)
        async def intermittent_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ExternalServiceException(f"Failure {call_count}")
            return "success_after_retries"

        result = await intermittent_func()
        assert result == "success_after_retries"
        assert call_count == 3

    def test_retry_on_failure_decorator_sync_success(self):
        """Test retry_on_failure decorator with successful sync function."""

        @retry_on_failure(max_retries=2, base_delay=0.01)
        def success_func():
            return "sync_success"

        result = success_func()
        assert result == "sync_success"

    def test_retry_on_failure_decorator_sync_with_retries(self):
        """Test retry_on_failure decorator with sync function that succeeds after retries."""
        call_count = 0

        @retry_on_failure(max_retries=2, base_delay=0.01)
        def intermittent_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ExternalServiceException(f"Failure {call_count}")
            return "success_after_retries"

        result = intermittent_func()
        assert result == "success_after_retries"
        assert call_count == 3

    def test_retry_on_failure_decorator_with_custom_exceptions(self):
        """Test retry_on_failure decorator with custom retryable exceptions."""
        call_count = 0

        @retry_on_failure(max_retries=1, base_delay=0.01, retryable_exceptions=[ValueError])
        def custom_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retryable error")
            return "success"

        result = custom_func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_with_fallback_decorator_async_success(self):
        """Test with_fallback decorator with successful async function."""

        async def fallback_func():
            return "fallback_result"

        @with_fallback("test_service", fallback_func)
        async def success_func():
            return "primary_success"

        result = await success_func()
        assert result == "primary_success"

    @pytest.mark.asyncio
    async def test_with_fallback_decorator_async_with_fallback(self):
        """Test with_fallback decorator with async function that uses fallback."""

        async def fallback_func():
            return "fallback_result"

        @with_fallback("test_service", fallback_func)
        async def failing_func():
            raise ValueError("Primary failure")

        result = await failing_func()
        assert result == "fallback_result"

    def test_with_fallback_decorator_sync_success(self):
        """Test with_fallback decorator with successful sync function."""

        def fallback_func():
            return "fallback_result"

        @with_fallback("test_service", fallback_func)
        def success_func():
            return "primary_success"

        result = success_func()
        assert result == "primary_success"

    def test_with_fallback_decorator_sync_with_fallback(self):
        """Test with_fallback decorator with sync function that uses fallback."""

        def fallback_func():
            return "fallback_result"

        @with_fallback("test_service", fallback_func)
        def failing_func():
            raise ValueError("Primary failure")

        result = failing_func()
        assert result == "fallback_result"


class TestRetryHandlerIntegration:
    """Integration tests for retry handler functionality."""

    @pytest.mark.asyncio
    async def test_combined_retry_and_fallback_strategies(self):
        """Test combining retry and fallback strategies."""
        # Create a service that fails consistently
        call_count = 0

        async def always_failing_service():
            nonlocal call_count
            call_count += 1
            raise ExternalServiceException(f"Service failure {call_count}")

        # Create fallback function
        async def fallback_service():
            return "fallback_success"

        # First, try with retry handler
        retry_handler = ExponentialBackoffRetryHandler(max_retries=2, base_delay=0.01)

        # This should fail after retries
        with pytest.raises(ExternalServiceException):
            await retry_handler.execute_with_retry(always_failing_service)

        assert call_count == 3  # Initial + 2 retries

        # Now use graceful degradation
        degradation_handler = GracefulDegradationHandler({"failing_service": fallback_service})

        result = await degradation_handler.execute_with_fallback("failing_service", always_failing_service)

        assert result == "fallback_success"
        assert not degradation_handler.is_service_healthy("failing_service")

    @pytest.mark.asyncio
    async def test_service_recovery_detection(self):
        """Test detection of service recovery."""
        degradation_handler = GracefulDegradationHandler()

        call_count = 0

        async def recovering_service():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError(f"Failure {call_count}")
            return f"Success {call_count}"

        # First call should fail and mark service unhealthy
        with pytest.raises(ValueError):
            await degradation_handler.execute_with_fallback("recovering_service", recovering_service)

        assert not degradation_handler.is_service_healthy("recovering_service")

        # Second call should also fail
        with pytest.raises(ValueError):
            await degradation_handler.execute_with_fallback("recovering_service", recovering_service)

        # Third call should succeed and mark service healthy
        result = await degradation_handler.execute_with_fallback("recovering_service", recovering_service)

        assert result == "Success 3"
        assert degradation_handler.is_service_healthy("recovering_service")

    @pytest.mark.asyncio
    async def test_multiple_services_health_tracking(self):
        """Test health tracking for multiple services."""
        degradation_handler = GracefulDegradationHandler()

        async def healthy_service():
            return "healthy_result"

        async def unhealthy_service():
            raise ValueError("Service down")

        # Test healthy service
        result = await degradation_handler.execute_with_fallback("healthy_service", healthy_service)
        assert result == "healthy_result"
        assert degradation_handler.is_service_healthy("healthy_service")

        # Test unhealthy service
        with pytest.raises(ValueError):
            await degradation_handler.execute_with_fallback("unhealthy_service", unhealthy_service)
        assert not degradation_handler.is_service_healthy("unhealthy_service")

        # Healthy service should still be healthy
        assert degradation_handler.is_service_healthy("healthy_service")
