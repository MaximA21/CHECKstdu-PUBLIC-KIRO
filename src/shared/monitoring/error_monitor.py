"""Error monitoring and alerting system."""

import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque

from ..exceptions import (
    BaseApplicationException,
    ErrorSeverity,
    ErrorCategory
)
from ...application.interfaces.logging import ILogger


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorMetrics:
    """Error metrics for monitoring."""
    total_errors: int = 0
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    errors_by_component: Dict[str, int] = field(default_factory=dict)
    error_rate_per_minute: float = 0.0
    last_error_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'total_errors': self.total_errors,
            'errors_by_category': self.errors_by_category,
            'errors_by_severity': self.errors_by_severity,
            'errors_by_component': self.errors_by_component,
            'error_rate_per_minute': self.error_rate_per_minute,
            'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None
        }


@dataclass
class ErrorAlert:
    """Error alert information."""
    alert_id: str
    severity: AlertSeverity
    title: str
    message: str
    error_count: int
    time_window: timedelta
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            'alert_id': self.alert_id,
            'severity': self.severity.value,
            'title': self.title,
            'message': self.message,
            'error_count': self.error_count,
            'time_window_minutes': self.time_window.total_seconds() / 60,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved
        }


class ErrorMonitor:
    """Error monitoring and alerting system."""
    
    def __init__(
        self,
        logger: Optional[ILogger] = None,
        alert_thresholds: Optional[Dict[str, int]] = None,
        time_window_minutes: int = 5,
        max_history_size: int = 1000
    ):
        """Initialize error monitor.
        
        Args:
            logger: Logger instance for monitoring events
            alert_thresholds: Error count thresholds for different severities
            time_window_minutes: Time window for error rate calculations
            max_history_size: Maximum number of errors to keep in history
        """
        self.logger = logger
        self.time_window = timedelta(minutes=time_window_minutes)
        self.max_history_size = max_history_size
        
        # Default alert thresholds
        self.alert_thresholds = alert_thresholds or {
            'critical_errors': 1,      # 1 critical error triggers alert
            'high_errors': 5,          # 5 high severity errors in time window
            'medium_errors': 20,       # 20 medium severity errors in time window
            'total_errors': 50         # 50 total errors in time window
        }
        
        # Error tracking
        self.error_history: deque = deque(maxlen=max_history_size)
        self.metrics = ErrorMetrics()
        self.active_alerts: Dict[str, ErrorAlert] = {}
        self.alert_callbacks: List[Callable[[ErrorAlert], None]] = []
        
        # Rate limiting for alerts
        self.last_alert_times: Dict[str, datetime] = {}
        self.alert_cooldown = timedelta(minutes=10)
    
    def record_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Record an error for monitoring."""
        timestamp = datetime.utcnow()
        
        # Create error record
        error_record = {
            'timestamp': timestamp,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {}
        }
        
        # Add application exception details
        if isinstance(error, BaseApplicationException):
            error_record.update({
                'error_code': error.error_code,
                'severity': error.severity.value,
                'category': error.category.value,
                'recoverable': error.recoverable,
                'request_id': error.context.request_id,
                'component': error.context.component
            })
        else:
            # Default values for non-application exceptions
            error_record.update({
                'severity': ErrorSeverity.HIGH.value,
                'category': ErrorCategory.SYSTEM.value,
                'recoverable': False
            })
        
        # Add to history
        self.error_history.append(error_record)
        
        # Update metrics
        self._update_metrics(error_record)
        
        # Check for alerts
        self._check_alert_conditions(error_record)
        
        # Log the error
        if self.logger:
            self.logger.error(
                f"Error recorded: {error_record['error_type']}",
                error_record
            )
    
    def _update_metrics(self, error_record: Dict[str, Any]) -> None:
        """Update error metrics."""
        self.metrics.total_errors += 1
        self.metrics.last_error_time = error_record['timestamp']
        
        # Update category counts
        category = error_record.get('category', 'unknown')
        self.metrics.errors_by_category[category] = \
            self.metrics.errors_by_category.get(category, 0) + 1
        
        # Update severity counts
        severity = error_record.get('severity', 'unknown')
        self.metrics.errors_by_severity[severity] = \
            self.metrics.errors_by_severity.get(severity, 0) + 1
        
        # Update component counts
        component = error_record.get('component', 'unknown')
        self.metrics.errors_by_component[component] = \
            self.metrics.errors_by_component.get(component, 0) + 1
        
        # Calculate error rate
        self._calculate_error_rate()
    
    def _calculate_error_rate(self) -> None:
        """Calculate error rate per minute."""
        now = datetime.utcnow()
        cutoff_time = now - self.time_window
        
        # Count errors in time window
        recent_errors = [
            error for error in self.error_history
            if error['timestamp'] >= cutoff_time
        ]
        
        # Calculate rate per minute
        time_window_minutes = self.time_window.total_seconds() / 60
        self.metrics.error_rate_per_minute = len(recent_errors) / time_window_minutes
    
    def _check_alert_conditions(self, error_record: Dict[str, Any]) -> None:
        """Check if error conditions warrant alerts."""
        now = datetime.utcnow()
        cutoff_time = now - self.time_window
        
        # Get recent errors
        recent_errors = [
            error for error in self.error_history
            if error['timestamp'] >= cutoff_time
        ]
        
        # Check critical error alert
        if error_record.get('severity') == ErrorSeverity.CRITICAL.value:
            self._trigger_alert(
                'critical_error',
                AlertSeverity.CRITICAL,
                'Critical Error Detected',
                f"Critical error occurred: {error_record['error_message']}",
                1
            )
        
        # Check high severity error threshold
        high_errors = [
            error for error in recent_errors
            if error.get('severity') == ErrorSeverity.HIGH.value
        ]
        if len(high_errors) >= self.alert_thresholds['high_errors']:
            self._trigger_alert(
                'high_error_threshold',
                AlertSeverity.ERROR,
                'High Error Threshold Exceeded',
                f"{len(high_errors)} high severity errors in {self.time_window.total_seconds()/60} minutes",
                len(high_errors)
            )
        
        # Check medium severity error threshold
        medium_errors = [
            error for error in recent_errors
            if error.get('severity') == ErrorSeverity.MEDIUM.value
        ]
        if len(medium_errors) >= self.alert_thresholds['medium_errors']:
            self._trigger_alert(
                'medium_error_threshold',
                AlertSeverity.WARNING,
                'Medium Error Threshold Exceeded',
                f"{len(medium_errors)} medium severity errors in {self.time_window.total_seconds()/60} minutes",
                len(medium_errors)
            )
        
        # Check total error threshold
        if len(recent_errors) >= self.alert_thresholds['total_errors']:
            self._trigger_alert(
                'total_error_threshold',
                AlertSeverity.ERROR,
                'Total Error Threshold Exceeded',
                f"{len(recent_errors)} total errors in {self.time_window.total_seconds()/60} minutes",
                len(recent_errors)
            )
    
    def _trigger_alert(
        self,
        alert_type: str,
        severity: AlertSeverity,
        title: str,
        message: str,
        error_count: int
    ) -> None:
        """Trigger an alert if not in cooldown period."""
        now = datetime.utcnow()
        
        # Check cooldown
        if alert_type in self.last_alert_times:
            time_since_last = now - self.last_alert_times[alert_type]
            if time_since_last < self.alert_cooldown:
                return  # Still in cooldown
        
        # Create alert
        alert_id = f"{alert_type}_{int(now.timestamp())}"
        alert = ErrorAlert(
            alert_id=alert_id,
            severity=severity,
            title=title,
            message=message,
            error_count=error_count,
            time_window=self.time_window,
            timestamp=now
        )
        
        # Store alert
        self.active_alerts[alert_id] = alert
        self.last_alert_times[alert_type] = now
        
        # Log alert
        if self.logger:
            self.logger.error(
                f"Alert triggered: {title}",
                alert.to_dict()
            )
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Error in alert callback: {str(e)}",
                        {'callback': callback.__name__, 'alert_id': alert_id}
                    )
    
    def add_alert_callback(self, callback: Callable[[ErrorAlert], None]) -> None:
        """Add callback function for alert notifications."""
        self.alert_callbacks.append(callback)
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert."""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolved = True
            if self.logger:
                self.logger.info(
                    f"Alert resolved: {alert_id}",
                    {'alert_id': alert_id}
                )
            return True
        return False
    
    def get_metrics(self) -> ErrorMetrics:
        """Get current error metrics."""
        self._calculate_error_rate()  # Refresh rate calculation
        return self.metrics
    
    def get_active_alerts(self) -> List[ErrorAlert]:
        """Get list of active (unresolved) alerts."""
        return [
            alert for alert in self.active_alerts.values()
            if not alert.resolved
        ]
    
    def get_error_history(
        self,
        limit: Optional[int] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get error history with optional filtering."""
        errors = list(self.error_history)
        
        # Filter by time if specified
        if since:
            errors = [error for error in errors if error['timestamp'] >= since]
        
        # Sort by timestamp (most recent first)
        errors.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Apply limit if specified
        if limit:
            errors = errors[:limit]
        
        return errors
    
    def clear_history(self) -> None:
        """Clear error history and reset metrics."""
        self.error_history.clear()
        self.metrics = ErrorMetrics()
        self.active_alerts.clear()
        self.last_alert_times.clear()
        
        if self.logger:
            self.logger.info("Error monitoring history cleared")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive monitoring summary."""
        return {
            'metrics': self.metrics.to_dict(),
            'active_alerts': [alert.to_dict() for alert in self.get_active_alerts()],
            'alert_thresholds': self.alert_thresholds,
            'time_window_minutes': self.time_window.total_seconds() / 60,
            'history_size': len(self.error_history)
        }