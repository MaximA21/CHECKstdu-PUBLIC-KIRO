"""Unit tests for circuit breaker middleware."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.application.interfaces.logging import ILogger
from src.shared.exceptions import (
    BaseApplicationException,
    ErrorSeverity,
    ExternalServiceException,
    ValidationException,
)
from src.shared.middleware.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerException,
    CircuitBreakerRegistry,
    CircuitBreakerState,
    circuit_breaker,
)


class TestCircuitBreakerException:
    """Test cases for CircuitBreakerException."""

    def test_init_with_service_name(self):
        """Test CircuitBreakerException initialization."""
        exception = CircuitBreakerException("test_service")

        assert "test_service" in str(exception)
        assert exception.service_name == "test_service"
        assert exception.severity == ErrorSeverity.HIGH
        assert exception.recoverable is True
        assert "temporarily unavailable" in exception.user_message


class TestCircuitBreaker:
    """Test cases for CircuitBreaker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=ILogger)
        self.circuit_breaker = CircuitBreaker(
            service_name="test_service", failure_threshold=3, recovery_timeout=1.0, logger=self.mock_logger
        )

    def test_init_with_defaults(self):
        """Test CircuitBreaker initialization with defaults."""
        cb = CircuitBreaker("test_service")

        assert cb.service_name == "test_service"
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60.0
        assert cb.expected_exception == Exception
        assert cb.logger is None
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.state == CircuitBreakerState.CLOSED

    def test_init_with_custom_parameters(self):
        """Test CircuitBreaker initialization with custom parameters."""
        cb = CircuitBreaker(
            service_name="custom_service",
            failure_threshold=2,
            recovery_timeout=30.0,
            expected_exception=ValueError,
            logger=self.mock_logger,
        )

        assert cb.service_name == "custom_service"
        assert cb.failure_threshold == 2
        assert cb.recovery_timeout == 30.0
        assert cb.expected_exception == ValueError
        assert cb.logger is self.mock_logger

    @pytest.mark.asyncio
    async def test_call_success_closed_state(self):
        """Test successful call in closed state."""

        async def test_func():
            return "success"

        result = await self.circuit_breaker.call(test_func)

        assert result == "success"
        assert self.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert self.circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_call_sync_function(self):
        """Test calling synchronous function."""

        def sync_func():
            return "sync_success"

        result = await self.circuit_breaker.call(sync_func)

        assert result == "sync_success"

    @pytest.mark.asyncio
    async def test_call_failure_below_threshold(self):
        """Test failure below threshold keeps circuit closed."""

        async def failing_func():
            raise ValueError("Test error")

        # First failure
        with pytest.raises(ValueError):
            await self.circuit_breaker.call(failing_func)

        assert self.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert self.circuit_breaker.failure_count == 1

        # Second failure
        with pytest.raises(ValueError):
            await self.circuit_breaker.call(failing_func)

        assert self.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert self.circuit_breaker.failure_count == 2

    @pytest.mark.asyncio
    async def test_call_failure_reaches_threshold(self):
        """Test failure reaching threshold opens circuit."""

        async def failing_func():
            raise ValueError("Test error")

        # Reach failure threshold
        for i in range(3):
            with pytest.raises(ValueError):
                await self.circuit_breaker.call(failing_func)

        assert self.circuit_breaker.state == CircuitBreakerState.OPEN
        assert self.circuit_breaker.failure_count == 3

        # Verify logger was called
        self.mock_logger.error.assert_called()
        log_call = self.mock_logger.error.call_args
        assert "opened due to failures" in log_call[0][0]

    @pytest.mark.asyncio
    async def test_call_open_state_fails_fast(self):
        """Test that open circuit fails fast."""
        # Force circuit to open state
        self.circuit_breaker.force_open()

        async def test_func():
            return "should_not_execute"

        with pytest.raises(CircuitBreakerException) as exc_info:
            await self.circuit_breaker.call(test_func)

        assert exc_info.value.service_name == "test_service"

        # Verify logger was called
        self.mock_logger.warning.assert_called()
        log_call = self.mock_logger.warning.call_args
        assert "is OPEN, failing fast" in log_call[0][0]

    @pytest.mark.asyncio
    async def test_call_half_open_success_resets_circuit(self):
        """Test successful call in half-open state resets circuit."""
        # Set up half-open state
        self.circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        self.circuit_breaker.failure_count = 2

        async def success_func():
            return "recovery_success"

        result = await self.circuit_breaker.call(success_func)

        assert result == "recovery_success"
        assert self.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert self.circuit_breaker.failure_count == 0

        # Verify logger was called
        self.mock_logger.info.assert_called()
        log_call = self.mock_logger.info.call_args
        assert "reset to CLOSED" in log_call[0][0]

    @pytest.mark.asyncio
    async def test_call_half_open_failure_reopens_circuit(self):
        """Test failure in half-open state reopens circuit."""
        # Set up half-open state
        self.circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        self.circuit_breaker.failure_count = 2

        async def failing_func():
            raise ValueError("Recovery failed")

        with pytest.raises(ValueError):
            await self.circuit_breaker.call(failing_func)

        assert self.circuit_breaker.state == CircuitBreakerState.OPEN
        assert self.circuit_breaker.failure_count == 3

        # Verify logger was called
        self.mock_logger.warning.assert_called()
        log_call = self.mock_logger.warning.call_args
        assert "failed during recovery, back to OPEN" in log_call[0][0]

    @pytest.mark.asyncio
    async def test_call_recovery_timeout_moves_to_half_open(self):
        """Test that recovery timeout moves circuit to half-open."""
        # Force circuit to open state
        self.circuit_breaker.force_open()

        # Mock time to simulate timeout passage
        with patch("time.time") as mock_time:
            # Set initial time
            mock_time.return_value = 1000.0
            self.circuit_breaker.last_failure_time = 1000.0

            # Advance time beyond recovery timeout
            mock_time.return_value = 1002.0  # 2 seconds later (> 1.0 timeout)

            async def test_func():
                return "recovery_attempt"

            result = await self.circuit_breaker.call(test_func)

            assert result == "recovery_attempt"
            # Should have moved to half-open and then closed on success
            assert self.circuit_breaker.state == CircuitBreakerState.CLOSED

    def test_should_attempt_reset_with_no_failure_time(self):
        """Test should_attempt_reset with no previous failure time."""
        self.circuit_breaker.last_failure_time = None
        assert self.circuit_breaker._should_attempt_reset() is True

    def test_should_attempt_reset_within_timeout(self):
        """Test should_attempt_reset within timeout period."""
        with patch("time.time", return_value=1000.0):
            self.circuit_breaker.last_failure_time = 999.5  # 0.5 seconds ago
            assert self.circuit_breaker._should_attempt_reset() is False

    def test_should_attempt_reset_after_timeout(self):
        """Test should_attempt_reset after timeout period."""
        with patch("time.time", return_value=1000.0):
            self.circuit_breaker.last_failure_time = 998.0  # 2 seconds ago
            assert self.circuit_breaker._should_attempt_reset() is True

    def test_is_failure_with_expected_exception(self):
        """Test is_failure with expected exception type."""
        error = ValueError("Test error")
        assert self.circuit_breaker._is_failure(error) is True

    def test_is_failure_with_application_exception_high_severity(self):
        """Test is_failure with high severity application exception."""
        error = ExternalServiceException("Service error")
        assert self.circuit_breaker._is_failure(error) is True

    def test_is_failure_with_application_exception_low_severity(self):
        """Test is_failure with low severity application exception."""
        error = ValidationException("Validation error")
        assert self.circuit_breaker._is_failure(error) is False

    def test_is_failure_with_unexpected_exception(self):
        """Test is_failure with unexpected exception type."""
        # Set expected exception to ValueError
        self.circuit_breaker.expected_exception = ValueError
        error = TypeError("Type error")
        assert self.circuit_breaker._is_failure(error) is False

    def test_record_failure(self):
        """Test recording a failure."""
        with patch("time.time", return_value=1000.0):
            self.circuit_breaker._record_failure()

            assert self.circuit_breaker.failure_count == 1
            assert self.circuit_breaker.last_failure_time == 1000.0

    def test_reset(self):
        """Test resetting circuit breaker."""
        # Set up some failure state
        self.circuit_breaker.failure_count = 3
        self.circuit_breaker.last_failure_time = 1000.0
        self.circuit_breaker.state = CircuitBreakerState.OPEN

        self.circuit_breaker._reset()

        assert self.circuit_breaker.failure_count == 0
        assert self.circuit_breaker.last_failure_time is None
        assert self.circuit_breaker.state == CircuitBreakerState.CLOSED

    def test_get_state(self):
        """Test getting circuit breaker state."""
        assert self.circuit_breaker.get_state() == CircuitBreakerState.CLOSED

        self.circuit_breaker.state = CircuitBreakerState.OPEN
        assert self.circuit_breaker.get_state() == CircuitBreakerState.OPEN

    def test_get_failure_count(self):
        """Test getting failure count."""
        assert self.circuit_breaker.get_failure_count() == 0

        self.circuit_breaker.failure_count = 5
        assert self.circuit_breaker.get_failure_count() == 5

    def test_force_open(self):
        """Test forcing circuit breaker to open state."""
        with patch("time.time", return_value=1000.0):
            self.circuit_breaker.force_open()

            assert self.circuit_breaker.state == CircuitBreakerState.OPEN
            assert self.circuit_breaker.last_failure_time == 1000.0

            # Verify logger was called
            self.mock_logger.warning.assert_called()
            log_call = self.mock_logger.warning.call_args
            assert "forced to OPEN" in log_call[0][0]

    def test_force_close(self):
        """Test forcing circuit breaker to closed state."""
        # Set up open state
        self.circuit_breaker.state = CircuitBreakerState.OPEN
        self.circuit_breaker.failure_count = 3
        self.circuit_breaker.last_failure_time = 1000.0

        self.circuit_breaker.force_close()

        assert self.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert self.circuit_breaker.failure_count == 0
        assert self.circuit_breaker.last_failure_time is None

        # Verify logger was called
        self.mock_logger.info.assert_called()
        log_call = self.mock_logger.info.call_args
        assert "forced to CLOSED" in log_call[0][0]


class TestCircuitBreakerRegistry:
    """Test cases for CircuitBreakerRegistry."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=ILogger)
        self.registry = CircuitBreakerRegistry(self.mock_logger)

    def test_init_with_logger(self):
        """Test CircuitBreakerRegistry initialization with logger."""
        registry = CircuitBreakerRegistry(self.mock_logger)
        assert registry.logger is self.mock_logger
        assert len(registry.circuit_breakers) == 0

    def test_init_without_logger(self):
        """Test CircuitBreakerRegistry initialization without logger."""
        registry = CircuitBreakerRegistry()
        assert registry.logger is None
        assert len(registry.circuit_breakers) == 0

    def test_get_circuit_breaker_creates_new(self):
        """Test getting circuit breaker creates new instance."""
        cb = self.registry.get_circuit_breaker("service1")

        assert isinstance(cb, CircuitBreaker)
        assert cb.service_name == "service1"
        assert cb.failure_threshold == 5  # Default value
        assert cb.logger is self.mock_logger
        assert "service1" in self.registry.circuit_breakers

    def test_get_circuit_breaker_returns_existing(self):
        """Test getting circuit breaker returns existing instance."""
        cb1 = self.registry.get_circuit_breaker("service1")
        cb2 = self.registry.get_circuit_breaker("service1")

        assert cb1 is cb2

    def test_get_circuit_breaker_with_custom_parameters(self):
        """Test getting circuit breaker with custom parameters."""
        cb = self.registry.get_circuit_breaker(
            "service2", failure_threshold=3, recovery_timeout=30.0, expected_exception=ValueError
        )

        assert cb.service_name == "service2"
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30.0
        assert cb.expected_exception == ValueError

    def test_get_all_states(self):
        """Test getting all circuit breaker states."""
        cb1 = self.registry.get_circuit_breaker("service1")
        cb2 = self.registry.get_circuit_breaker("service2")

        # Force different states
        cb1.force_open()
        cb2.state = CircuitBreakerState.HALF_OPEN

        states = self.registry.get_all_states()

        assert states["service1"] == CircuitBreakerState.OPEN
        assert states["service2"] == CircuitBreakerState.HALF_OPEN

    def test_get_all_states_empty_registry(self):
        """Test getting all states from empty registry."""
        states = self.registry.get_all_states()
        assert states == {}

    def test_reset_all(self):
        """Test resetting all circuit breakers."""
        cb1 = self.registry.get_circuit_breaker("service1")
        cb2 = self.registry.get_circuit_breaker("service2")

        # Force different states
        cb1.force_open()
        cb2.force_open()

        self.registry.reset_all()

        assert cb1.get_state() == CircuitBreakerState.CLOSED
        assert cb2.get_state() == CircuitBreakerState.CLOSED

        # Verify logger was called
        self.mock_logger.info.assert_called()
        log_call = self.mock_logger.info.call_args
        assert "All circuit breakers reset" in log_call[0][0]

    def test_reset_all_empty_registry(self):
        """Test resetting all circuit breakers in empty registry."""
        # Should not raise any exceptions
        self.registry.reset_all()

        # Verify logger was still called
        self.mock_logger.info.assert_called()


class TestCircuitBreakerDecorator:
    """Test cases for circuit breaker decorator."""

    @pytest.mark.asyncio
    async def test_decorator_async_function_success(self):
        """Test decorator with successful async function."""

        @circuit_breaker("test_service", failure_threshold=2)
        async def async_func():
            return "async_success"

        result = await async_func()
        assert result == "async_success"

    @pytest.mark.asyncio
    async def test_decorator_async_function_failure(self):
        """Test decorator with failing async function."""

        @circuit_breaker("test_service", failure_threshold=2)
        async def failing_async_func():
            raise ValueError("Async failure")

        # First failure
        with pytest.raises(ValueError):
            await failing_async_func()

        # Second failure should open circuit
        with pytest.raises(ValueError):
            await failing_async_func()

        # Third call should fail fast with CircuitBreakerException
        with pytest.raises(CircuitBreakerException):
            await failing_async_func()

    def test_decorator_sync_function_success(self):
        """Test decorator with successful sync function."""

        @circuit_breaker("test_service", failure_threshold=2)
        def sync_func():
            return "sync_success"

        result = sync_func()
        assert result == "sync_success"

    def test_decorator_sync_function_failure(self):
        """Test decorator with failing sync function."""

        @circuit_breaker("test_service", failure_threshold=2)
        def failing_sync_func():
            raise ValueError("Sync failure")

        # First failure
        with pytest.raises(ValueError):
            failing_sync_func()

        # Second failure should open circuit
        with pytest.raises(ValueError):
            failing_sync_func()

        # Third call should fail fast with CircuitBreakerException
        with pytest.raises(CircuitBreakerException):
            failing_sync_func()

    def test_decorator_with_custom_parameters(self):
        """Test decorator with custom parameters."""

        @circuit_breaker("custom_service", failure_threshold=1, recovery_timeout=0.1, expected_exception=RuntimeError)
        def custom_func():
            raise RuntimeError("Custom error")

        # First failure should open circuit (threshold=1)
        with pytest.raises(RuntimeError):
            custom_func()

        # Second call should fail fast
        with pytest.raises(CircuitBreakerException):
            custom_func()

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""

        @circuit_breaker("test_service")
        async def documented_func():
            """This is a test function."""
            return "test"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a test function."


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_cycle(self):
        """Test complete circuit breaker recovery cycle."""
        cb = CircuitBreaker(
            "integration_service",
            failure_threshold=2,
            recovery_timeout=0.1,  # Short timeout for testing
            logger=Mock(spec=ILogger),
        )

        call_count = 0

        async def intermittent_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError(f"Failure {call_count}")
            return f"Success {call_count}"

        # First two calls should fail and open circuit
        with pytest.raises(ValueError):
            await cb.call(intermittent_func)

        with pytest.raises(ValueError):
            await cb.call(intermittent_func)

        assert cb.get_state() == CircuitBreakerState.OPEN

        # Immediate call should fail fast
        with pytest.raises(CircuitBreakerException):
            await cb.call(intermittent_func)

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should succeed and reset circuit
        result = await cb.call(intermittent_func)
        assert result == "Success 3"
        assert cb.get_state() == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_multiple_circuit_breakers_independence(self):
        """Test that multiple circuit breakers operate independently."""
        registry = CircuitBreakerRegistry()

        cb1 = registry.get_circuit_breaker("service1", failure_threshold=1)
        cb2 = registry.get_circuit_breaker("service2", failure_threshold=1)

        async def failing_func():
            raise ValueError("Service failure")

        async def success_func():
            return "success"

        # Fail service1
        with pytest.raises(ValueError):
            await cb1.call(failing_func)

        assert cb1.get_state() == CircuitBreakerState.OPEN
        assert cb2.get_state() == CircuitBreakerState.CLOSED

        # Service2 should still work
        result = await cb2.call(success_func)
        assert result == "success"
        assert cb2.get_state() == CircuitBreakerState.CLOSED

        # Service1 should fail fast
        with pytest.raises(CircuitBreakerException):
            await cb1.call(success_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_different_exception_types(self):
        """Test circuit breaker behavior with different exception types."""
        cb = CircuitBreaker("exception_service", failure_threshold=2, expected_exception=ValueError)

        # ValueError should count as failure
        with pytest.raises(ValueError):
            await cb.call(lambda: (_ for _ in ()).throw(ValueError("Test")))

        assert cb.get_failure_count() == 1

        # TypeError should not count as failure
        with pytest.raises(TypeError):
            await cb.call(lambda: (_ for _ in ()).throw(TypeError("Test")))

        assert cb.get_failure_count() == 1  # Should not increment
        assert cb.get_state() == CircuitBreakerState.CLOSED
