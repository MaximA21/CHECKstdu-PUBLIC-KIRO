"""Tests for monitoring components."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.shared.monitoring.error_monitor import AlertSeverity, ErrorAlert, ErrorMonitor
from src.shared.monitoring.health_check import ComponentHealth, HealthCheckRegistry, HealthStatus


class TestErrorMonitor:
    @pytest.fixture
    def error_monitor(self):
        """Create ErrorMonitor instance."""
        return ErrorMonitor(
            alert_thresholds={
                "critical_errors": 1,
                "high_errors": 3,
                "medium_errors": 10,
                "total_errors": 20,
            }
        )

    def test_error_monitor_initialization(self, error_monitor):
        """Test ErrorMonitor initialization."""
        assert error_monitor.alert_thresholds["critical_errors"] == 1
        assert error_monitor.alert_thresholds["high_errors"] == 3
        assert len(error_monitor.error_history) == 0
        assert len(error_monitor.active_alerts) == 0

    def test_record_error(self, error_monitor):
        """Test recording an error."""
        error = ValueError("Test error")
        context = {"component": "test", "operation": "test_op"}

        error_monitor.record_error(error, context)

        assert len(error_monitor.error_history) == 1
        assert error_monitor.metrics.total_errors == 1
        assert error_monitor.metrics.last_error_time is not None

    def test_record_multiple_errors(self, error_monitor):
        """Test recording multiple errors."""
        for i in range(5):
            error_monitor.record_error(ValueError(f"Error {i}"))

        assert len(error_monitor.error_history) == 5
        assert error_monitor.metrics.total_errors == 5

    def test_get_metrics(self, error_monitor):
        """Test getting error metrics."""
        error_monitor.record_error(ValueError("Test error"))

        metrics = error_monitor.get_metrics()
        assert metrics.total_errors == 1
        assert metrics.last_error_time is not None

    def test_get_active_alerts(self, error_monitor):
        """Test getting active alerts."""
        # Record enough errors to trigger an alert
        for i in range(5):
            error_monitor.record_error(ValueError(f"Error {i}"))

        alerts = error_monitor.get_active_alerts()
        assert len(alerts) > 0

    def test_resolve_alert(self, error_monitor):
        """Test resolving an alert."""
        # Record errors to create an alert
        for i in range(5):
            error_monitor.record_error(ValueError(f"Error {i}"))

        alerts = error_monitor.get_active_alerts()
        if alerts:
            alert_id = alerts[0].alert_id
            assert error_monitor.resolve_alert(alert_id) is True
            assert error_monitor.resolve_alert("non-existent") is False

    def test_clear_history(self, error_monitor):
        """Test clearing error history."""
        error_monitor.record_error(ValueError("Test error"))
        assert len(error_monitor.error_history) == 1

        error_monitor.clear_history()
        assert len(error_monitor.error_history) == 0
        assert error_monitor.metrics.total_errors == 0

    def test_get_summary(self, error_monitor):
        """Test getting monitoring summary."""
        error_monitor.record_error(ValueError("Test error"))

        summary = error_monitor.get_summary()
        assert "metrics" in summary
        assert "active_alerts" in summary
        assert "alert_thresholds" in summary


class TestHealthCheckRegistry:
    @pytest.fixture
    def health_check_registry(self):
        """Create HealthCheckRegistry instance."""
        return HealthCheckRegistry()

    @pytest.fixture
    def mock_health_check(self):
        """Create mock health check."""
        health_check = Mock()
        health_check.name = "test_component"
        health_check.execute_check = AsyncMock(
            return_value=ComponentHealth(
                name="test_component", status=HealthStatus.HEALTHY, message="Test component is healthy"
            )
        )
        return health_check

    def test_health_check_registry_initialization(self, health_check_registry):
        """Test HealthCheckRegistry initialization."""
        assert len(health_check_registry.health_checks) == 0
        assert len(health_check_registry.last_results) == 0

    def test_register_health_check(self, health_check_registry, mock_health_check):
        """Test registering a health check."""
        health_check_registry.register(mock_health_check)

        assert "test_component" in health_check_registry.health_checks
        assert health_check_registry.health_checks["test_component"] == mock_health_check

    def test_unregister_health_check(self, health_check_registry, mock_health_check):
        """Test unregistering a health check."""
        health_check_registry.register(mock_health_check)
        assert "test_component" in health_check_registry.health_checks

        assert health_check_registry.unregister("test_component") is True
        assert "test_component" not in health_check_registry.health_checks

        assert health_check_registry.unregister("non-existent") is False

    @pytest.mark.asyncio
    async def test_check_all(self, health_check_registry, mock_health_check):
        """Test checking all health checks."""
        health_check_registry.register(mock_health_check)

        results = await health_check_registry.check_all()

        assert "test_component" in results
        assert results["test_component"].status == HealthStatus.HEALTHY
        assert mock_health_check.execute_check.called

    @pytest.mark.asyncio
    async def test_check_component(self, health_check_registry, mock_health_check):
        """Test checking a specific component."""
        health_check_registry.register(mock_health_check)

        result = await health_check_registry.check_component("test_component")

        assert result is not None
        assert result.status == HealthStatus.HEALTHY
        assert mock_health_check.execute_check.called

    def test_get_overall_status_empty(self, health_check_registry):
        """Test getting overall status with no health checks."""
        status = health_check_registry.get_overall_status()
        assert status == HealthStatus.UNKNOWN

    def test_get_overall_status_healthy(self, health_check_registry):
        """Test getting overall status with healthy components."""
        health_check_registry.last_results = {
            "comp1": ComponentHealth("comp1", HealthStatus.HEALTHY),
            "comp2": ComponentHealth("comp2", HealthStatus.HEALTHY),
        }

        status = health_check_registry.get_overall_status()
        assert status == HealthStatus.HEALTHY

    def test_get_overall_status_degraded(self, health_check_registry):
        """Test getting overall status with degraded components."""
        health_check_registry.last_results = {
            "comp1": ComponentHealth("comp1", HealthStatus.HEALTHY),
            "comp2": ComponentHealth("comp2", HealthStatus.DEGRADED),
        }

        status = health_check_registry.get_overall_status()
        assert status == HealthStatus.DEGRADED

    def test_get_overall_status_unhealthy(self, health_check_registry):
        """Test getting overall status with unhealthy components."""
        health_check_registry.last_results = {
            "comp1": ComponentHealth("comp1", HealthStatus.HEALTHY),
            "comp2": ComponentHealth("comp2", HealthStatus.UNHEALTHY),
        }

        status = health_check_registry.get_overall_status()
        assert status == HealthStatus.UNHEALTHY

    def test_get_health_summary(self, health_check_registry):
        """Test getting health summary."""
        health_check_registry.last_results = {
            "comp1": ComponentHealth("comp1", HealthStatus.HEALTHY, "Component 1 is healthy")
        }

        summary = health_check_registry.get_health_summary()

        assert "overall_status" in summary
        assert "timestamp" in summary
        assert "components" in summary
        assert "registered_checks" in summary
        assert summary["overall_status"] == HealthStatus.HEALTHY.value

    def test_get_unhealthy_components(self, health_check_registry):
        """Test getting unhealthy components."""
        health_check_registry.last_results = {
            "comp1": ComponentHealth("comp1", HealthStatus.HEALTHY),
            "comp2": ComponentHealth("comp2", HealthStatus.UNHEALTHY, "Component 2 is down"),
            "comp3": ComponentHealth("comp3", HealthStatus.DEGRADED),
        }

        unhealthy = health_check_registry.get_unhealthy_components()
        assert len(unhealthy) == 1
        assert unhealthy[0].name == "comp2"

    def test_get_degraded_components(self, health_check_registry):
        """Test getting degraded components."""
        health_check_registry.last_results = {
            "comp1": ComponentHealth("comp1", HealthStatus.HEALTHY),
            "comp2": ComponentHealth("comp2", HealthStatus.UNHEALTHY),
            "comp3": ComponentHealth("comp3", HealthStatus.DEGRADED, "Component 3 is slow"),
        }

        degraded = health_check_registry.get_degraded_components()
        assert len(degraded) == 1
        assert degraded[0].name == "comp3"
