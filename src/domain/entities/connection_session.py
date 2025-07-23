"""Connection session entity for managing WebSocket connections."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional, Set


class ConnectionStatus(Enum):
    """Enumeration of connection session statuses."""

    CONNECTING = "Connecting"
    CONNECTED = "Connected"
    DISCONNECTING = "Disconnecting"
    DISCONNECTED = "Disconnected"
    ERROR = "Error"


class SessionConnectionType(Enum):
    """Enumeration of session connection types."""

    WEBSOCKET = "WebSocket"
    HTTP_POLLING = "HTTP_Polling"
    SERVER_SENT_EVENTS = "Server_Sent_Events"


@dataclass
class ConnectionSession:
    """Entity representing a client connection session."""

    connection_id: str
    connection_type: SessionConnectionType = SessionConnectionType.WEBSOCKET
    status: ConnectionStatus = ConnectionStatus.CONNECTING
    connected_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    client_info: Dict[str, Any] = field(default_factory=dict)
    session_data: Dict[str, Any] = field(default_factory=dict)
    subscribed_topics: Set[str] = field(default_factory=set)
    result_count: int = 0
    max_results: int = 5
    max_connection_minutes: int = 2

    def __post_init__(self):
        """Initialize default values and validate the connection session."""
        # Validate first, then set defaults
        self._validate()

        # Set connected_at if status is connected and not already set
        if self.status == ConnectionStatus.CONNECTED and self.connected_at is None:
            object.__setattr__(self, "connected_at", datetime.utcnow())

        # Set last_activity_at to connected_at if not set
        if self.last_activity_at is None and self.connected_at is not None:
            object.__setattr__(self, "last_activity_at", self.connected_at)

    def _validate(self) -> None:
        """Validate connection session data."""
        if not self.connection_id or not self.connection_id.strip():
            raise ValueError("Connection ID cannot be empty")

        if len(self.connection_id) > 128:
            raise ValueError("Connection ID cannot exceed 128 characters")

        # Validate status transitions
        if self.status == ConnectionStatus.CONNECTED and self.connected_at is None:
            raise ValueError("Connected status requires connected_at timestamp")

        if self.status == ConnectionStatus.DISCONNECTED and self.disconnected_at is None:
            raise ValueError("Disconnected status requires disconnected_at timestamp")

        # Validate timestamp ordering
        if self.connected_at and self.disconnected_at and self.disconnected_at <= self.connected_at:
            raise ValueError("Disconnected timestamp must be after connected timestamp")

        if self.connected_at and self.last_activity_at and self.last_activity_at < self.connected_at:
            raise ValueError("Last activity timestamp cannot be before connected timestamp")

    @classmethod
    def create_new(
        cls, connection_id: str, connection_type: SessionConnectionType = SessionConnectionType.WEBSOCKET
    ) -> "ConnectionSession":
        """Create a new connection session."""
        return cls(connection_id=connection_id, connection_type=connection_type, status=ConnectionStatus.CONNECTING)

    def connect(self) -> None:
        """Mark the connection as connected."""
        if self.status == ConnectionStatus.CONNECTED:
            raise ValueError("Connection is already connected")

        if self.status == ConnectionStatus.DISCONNECTED:
            raise ValueError("Cannot reconnect a disconnected session")

        now = datetime.utcnow()
        object.__setattr__(self, "status", ConnectionStatus.CONNECTED)
        object.__setattr__(self, "connected_at", now)
        object.__setattr__(self, "last_activity_at", now)

    def disconnect(self, reason: Optional[str] = None) -> None:
        """Mark the connection as disconnected."""
        if self.status == ConnectionStatus.DISCONNECTED:
            return  # Already disconnected

        now = datetime.utcnow()
        object.__setattr__(self, "status", ConnectionStatus.DISCONNECTED)
        object.__setattr__(self, "disconnected_at", now)

        if reason:
            self.add_session_data("disconnect_reason", reason)

    def mark_error(self, error_message: str) -> None:
        """Mark the connection as having an error."""
        object.__setattr__(self, "status", ConnectionStatus.ERROR)
        self.add_session_data("error_message", error_message)
        self.add_session_data("error_timestamp", datetime.utcnow().isoformat())

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        if self.status != ConnectionStatus.CONNECTED:
            raise ValueError("Cannot update activity for non-connected session")

        object.__setattr__(self, "last_activity_at", datetime.utcnow())

    def add_client_info(self, key: str, value: Any) -> None:
        """Add client information."""
        if not key or not key.strip():
            raise ValueError("Client info key cannot be empty")

        self.client_info[key] = value

    def get_client_info(self, key: str, default: Any = None) -> Any:
        """Get client information by key."""
        return self.client_info.get(key, default)

    def add_session_data(self, key: str, value: Any) -> None:
        """Add session data."""
        if not key or not key.strip():
            raise ValueError("Session data key cannot be empty")

        self.session_data[key] = value

    def get_session_data(self, key: str, default: Any = None) -> Any:
        """Get session data by key."""
        return self.session_data.get(key, default)

    def subscribe_to_topic(self, topic: str) -> None:
        """Subscribe to a topic for notifications."""
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty")

        self.subscribed_topics.add(topic.strip())

    def unsubscribe_from_topic(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        self.subscribed_topics.discard(topic.strip())

    def is_subscribed_to(self, topic: str) -> bool:
        """Check if subscribed to a specific topic."""
        return topic.strip() in self.subscribed_topics

    @property
    def is_connected(self) -> bool:
        """Check if the connection is currently connected."""
        return self.status == ConnectionStatus.CONNECTED

    @property
    def is_disconnected(self) -> bool:
        """Check if the connection is disconnected."""
        return self.status == ConnectionStatus.DISCONNECTED

    @property
    def has_error(self) -> bool:
        """Check if the connection has an error."""
        return self.status == ConnectionStatus.ERROR

    @property
    def connection_duration(self) -> Optional[timedelta]:
        """Get the duration of the connection."""
        if not self.connected_at:
            return None

        end_time = self.disconnected_at or datetime.utcnow()
        return end_time - self.connected_at

    @property
    def idle_duration(self) -> Optional[timedelta]:
        """Get the duration since last activity."""
        if not self.last_activity_at or not self.is_connected:
            return None

        return datetime.utcnow() - self.last_activity_at

    def is_idle_for(self, minutes: int) -> bool:
        """Check if the connection has been idle for the specified minutes."""
        if not self.is_connected:
            return False

        idle_duration = self.idle_duration
        if idle_duration is None:
            return False

        return idle_duration >= timedelta(minutes=minutes)

    def should_timeout(self, timeout_minutes: int = 30) -> bool:
        """Check if the connection should be timed out due to inactivity."""
        return self.is_idle_for(timeout_minutes)

    def increment_result_count(self) -> int:
        """Increment the result count and return the new count."""
        object.__setattr__(self, "result_count", self.result_count + 1)
        self.update_activity()
        return self.result_count

    def should_disconnect_due_to_limits(self) -> bool:
        """Check if connection should be disconnected due to result or time limits."""
        if not self.is_connected:
            return False

        # Check result limit
        if self.result_count >= self.max_results:
            return True

        # Check time limit
        if self.connected_at:
            connection_duration = datetime.utcnow() - self.connected_at
            if connection_duration >= timedelta(minutes=self.max_connection_minutes):
                return True

        return False

    def get_disconnect_reason_for_limits(self) -> str:
        """Get the reason for disconnection due to limits."""
        if self.result_count >= self.max_results:
            return f"Result limit reached ({self.result_count}/{self.max_results})"

        if self.connected_at:
            connection_duration = datetime.utcnow() - self.connected_at
            if connection_duration >= timedelta(minutes=self.max_connection_minutes):
                return f"Time limit reached ({self.max_connection_minutes} minutes)"

        return "Limit enforcement"

    def get_connection_summary(self) -> Dict[str, Any]:
        """Get a summary of the connection session."""
        return {
            "connection_id": self.connection_id,
            "connection_type": self.connection_type.value,
            "status": self.status.value,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "disconnected_at": self.disconnected_at.isoformat() if self.disconnected_at else None,
            "connection_duration_seconds": (
                int(self.connection_duration.total_seconds()) if self.connection_duration else None
            ),
            "idle_duration_seconds": (int(self.idle_duration.total_seconds()) if self.idle_duration else None),
            "subscribed_topics_count": len(self.subscribed_topics),
            "has_client_info": len(self.client_info) > 0,
            "has_session_data": len(self.session_data) > 0,
            "result_count": self.result_count,
            "max_results": self.max_results,
            "max_connection_minutes": self.max_connection_minutes,
            "should_disconnect_due_to_limits": self.should_disconnect_due_to_limits(),
        }
