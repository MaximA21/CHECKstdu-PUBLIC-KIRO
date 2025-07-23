"""Tests for ConnectionSession entity."""

import pytest
from datetime import datetime, timedelta
from src.domain.entities.connection_session import ConnectionSession, ConnectionStatus, SessionConnectionType


class TestConnectionSession:
    """Test cases for ConnectionSession entity."""
    
    def test_connection_session_creation(self):
        """Test creating a connection session."""
        session = ConnectionSession(
            connection_id="test-connection-123",
            connection_type=SessionConnectionType.WEBSOCKET,
            status=ConnectionStatus.CONNECTING
        )
        
        assert session.connection_id == "test-connection-123"
        assert session.connection_type == SessionConnectionType.WEBSOCKET
        assert session.status == ConnectionStatus.CONNECTING
        assert session.connected_at is None
        assert session.last_activity_at is None
        assert session.disconnected_at is None
        assert session.client_info == {}
        assert session.session_data == {}
        assert session.subscribed_topics == set()
    
    def test_create_new_class_method(self):
        """Test creating a new connection session using class method."""
        session = ConnectionSession.create_new("test-connection-456")
        
        assert session.connection_id == "test-connection-456"
        assert session.connection_type == SessionConnectionType.WEBSOCKET
        assert session.status == ConnectionStatus.CONNECTING
    
    def test_create_new_with_connection_type(self):
        """Test creating a new connection session with specific connection type."""
        session = ConnectionSession.create_new(
            "test-connection-789", 
            SessionConnectionType.HTTP_POLLING
        )
        
        assert session.connection_id == "test-connection-789"
        assert session.connection_type == SessionConnectionType.HTTP_POLLING
        assert session.status == ConnectionStatus.CONNECTING
    
    def test_connect(self):
        """Test connecting a session."""
        session = ConnectionSession.create_new("test-connection")
        
        # Initially connecting
        assert session.status == ConnectionStatus.CONNECTING
        assert session.connected_at is None
        assert session.last_activity_at is None
        
        # Connect the session
        session.connect()
        
        assert session.status == ConnectionStatus.CONNECTED
        assert session.connected_at is not None
        assert session.last_activity_at is not None
        assert session.connected_at == session.last_activity_at
    
    def test_connect_already_connected(self):
        """Test connecting an already connected session."""
        session = ConnectionSession.create_new("test-connection")
        session.connect()
        
        with pytest.raises(ValueError, match="Connection is already connected"):
            session.connect()
    
    def test_connect_disconnected_session(self):
        """Test connecting a disconnected session."""
        session = ConnectionSession.create_new("test-connection")
        session.connect()
        session.disconnect()
        
        with pytest.raises(ValueError, match="Cannot reconnect a disconnected session"):
            session.connect()
    
    def test_disconnect(self):
        """Test disconnecting a session."""
        session = ConnectionSession.create_new("test-connection")
        session.connect()
        
        # Disconnect the session
        session.disconnect("User requested disconnect")
        
        assert session.status == ConnectionStatus.DISCONNECTED
        assert session.disconnected_at is not None
        assert session.get_session_data("disconnect_reason") == "User requested disconnect"
    
    def test_disconnect_already_disconnected(self):
        """Test disconnecting an already disconnected session."""
        session = ConnectionSession.create_new("test-connection")
        session.connect()
        session.disconnect()
        
        # Should not raise error, just return
        session.disconnect()
        assert session.status == ConnectionStatus.DISCONNECTED
    
    def test_mark_error(self):
        """Test marking a session as having an error."""
        session = ConnectionSession.create_new("test-connection")
        session.connect()
        
        error_message = "WebSocket connection failed"
        session.mark_error(error_message)
        
        assert session.status == ConnectionStatus.ERROR
        assert session.get_session_data("error_message") == error_message
        assert session.get_session_data("error_timestamp") is not None
    
    def test_update_activity(self):
        """Test updating activity timestamp."""
        session = ConnectionSession.create_new("test-connection")
        session.connect()
        
        original_activity = session.last_activity_at
        
        # Wait a bit and update activity
        import time
        time.sleep(0.01)  # Small delay
        session.update_activity()
        
        assert session.last_activity_at > original_activity
    
    def test_update_activity_not_connected(self):
        """Test updating activity on non-connected session."""
        session = ConnectionSession.create_new("test-connection")
        
        with pytest.raises(ValueError, match="Cannot update activity for non-connected session"):
            session.update_activity()
    
    def test_client_info(self):
        """Test client information management."""
        session = ConnectionSession.create_new("test-connection")
        
        session.add_client_info("user_agent", "Mozilla/5.0")
        session.add_client_info("ip_address", "192.168.1.1")
        
        assert session.get_client_info("user_agent") == "Mozilla/5.0"
        assert session.get_client_info("ip_address") == "192.168.1.1"
        assert session.get_client_info("nonexistent") is None
        assert session.get_client_info("nonexistent", "default") == "default"
    
    def test_add_client_info_empty_key(self):
        """Test adding client info with empty key."""
        session = ConnectionSession.create_new("test-connection")
        
        with pytest.raises(ValueError, match="Client info key cannot be empty"):
            session.add_client_info("", "value")
    
    def test_session_data(self):
        """Test session data management."""
        session = ConnectionSession.create_new("test-connection")
        
        session.add_session_data("user_id", "user123")
        session.add_session_data("room_id", "room456")
        
        assert session.get_session_data("user_id") == "user123"
        assert session.get_session_data("room_id") == "room456"
        assert session.get_session_data("nonexistent") is None
        assert session.get_session_data("nonexistent", "default") == "default"
    
    def test_add_session_data_empty_key(self):
        """Test adding session data with empty key."""
        session = ConnectionSession.create_new("test-connection")
        
        with pytest.raises(ValueError, match="Session data key cannot be empty"):
            session.add_session_data("", "value")
    
    def test_topic_subscription(self):
        """Test topic subscription management."""
        session = ConnectionSession.create_new("test-connection")
        
        # Subscribe to topics
        session.subscribe_to_topic("search_results")
        session.subscribe_to_topic("notifications")
        session.subscribe_to_topic("  whitespace_topic  ")  # Should be trimmed
        
        assert session.is_subscribed_to("search_results") is True
        assert session.is_subscribed_to("notifications") is True
        assert session.is_subscribed_to("whitespace_topic") is True
        assert session.is_subscribed_to("nonexistent") is False
        
        # Unsubscribe from topic
        session.unsubscribe_from_topic("notifications")
        assert session.is_subscribed_to("notifications") is False
        assert session.is_subscribed_to("search_results") is True
    
    def test_subscribe_empty_topic(self):
        """Test subscribing to empty topic."""
        session = ConnectionSession.create_new("test-connection")
        
        with pytest.raises(ValueError, match="Topic cannot be empty"):
            session.subscribe_to_topic("")
        
        with pytest.raises(ValueError, match="Topic cannot be empty"):
            session.subscribe_to_topic("   ")  # Only whitespace
    
    def test_status_properties(self):
        """Test status check properties."""
        session = ConnectionSession.create_new("test-connection")
        
        # Initially connecting
        assert session.is_connected is False
        assert session.is_disconnected is False
        assert session.has_error is False
        
        # Connect
        session.connect()
        assert session.is_connected is True
        assert session.is_disconnected is False
        assert session.has_error is False
        
        # Disconnect
        session.disconnect()
        assert session.is_connected is False
        assert session.is_disconnected is True
        assert session.has_error is False
        
        # Create new session and mark error
        error_session = ConnectionSession.create_new("error-connection")
        error_session.connect()
        error_session.mark_error("Test error")
        assert error_session.is_connected is False
        assert error_session.is_disconnected is False
        assert error_session.has_error is True
    
    def test_connection_duration(self):
        """Test connection duration calculation."""
        session = ConnectionSession.create_new("test-connection")
        
        # No connection duration before connecting
        assert session.connection_duration is None
        
        # Connect and check duration
        session.connect()
        duration = session.connection_duration
        assert duration is not None
        assert duration.total_seconds() >= 0
        
        # Disconnect and check duration
        import time
        time.sleep(0.01)  # Small delay
        session.disconnect()
        final_duration = session.connection_duration
        assert final_duration > duration
    
    def test_idle_duration(self):
        """Test idle duration calculation."""
        session = ConnectionSession.create_new("test-connection")
        
        # No idle duration before connecting
        assert session.idle_duration is None
        
        # Connect and check idle duration
        session.connect()
        import time
        time.sleep(0.01)  # Small delay
        
        idle_duration = session.idle_duration
        assert idle_duration is not None
        assert idle_duration.total_seconds() > 0
        
        # Update activity and check idle duration resets
        session.update_activity()
        new_idle_duration = session.idle_duration
        assert new_idle_duration < idle_duration
    
    def test_is_idle_for(self):
        """Test idle time checking."""
        session = ConnectionSession.create_new("test-connection")
        session.connect()
        
        # Should not be idle for any significant time initially
        assert session.is_idle_for(1) is False  # 1 minute
        
        # Manually set last activity to past time
        past_time = datetime.utcnow() - timedelta(minutes=5)
        object.__setattr__(session, 'last_activity_at', past_time)
        
        assert session.is_idle_for(3) is True   # Idle for more than 3 minutes
        assert session.is_idle_for(10) is False # Not idle for 10 minutes
    
    def test_should_timeout(self):
        """Test timeout checking."""
        session = ConnectionSession.create_new("test-connection")
        session.connect()
        
        # Should not timeout initially
        assert session.should_timeout(30) is False
        
        # Manually set last activity to past time
        past_time = datetime.utcnow() - timedelta(minutes=35)
        object.__setattr__(session, 'last_activity_at', past_time)
        
        assert session.should_timeout(30) is True   # Should timeout after 30 minutes
        assert session.should_timeout(40) is False  # Should not timeout after 40 minutes
    
    def test_get_connection_summary(self):
        """Test getting connection summary."""
        session = ConnectionSession.create_new("test-connection")
        session.add_client_info("user_agent", "Mozilla/5.0")
        session.add_session_data("user_id", "user123")
        session.subscribe_to_topic("notifications")
        session.connect()
        
        summary = session.get_connection_summary()
        
        assert summary["connection_id"] == "test-connection"
        assert summary["connection_type"] == "WebSocket"
        assert summary["status"] == "Connected"
        assert summary["connected_at"] is not None
        assert summary["disconnected_at"] is None
        assert summary["connection_duration_seconds"] is not None
        assert summary["idle_duration_seconds"] is not None
        assert summary["subscribed_topics_count"] == 1
        assert summary["has_client_info"] is True
        assert summary["has_session_data"] is True
    
    # Validation tests
    def test_empty_connection_id_validation(self):
        """Test validation of empty connection ID."""
        with pytest.raises(ValueError, match="Connection ID cannot be empty"):
            ConnectionSession(connection_id="")
        
        with pytest.raises(ValueError, match="Connection ID cannot be empty"):
            ConnectionSession(connection_id="   ")  # Only whitespace
    
    def test_long_connection_id_validation(self):
        """Test validation of too long connection ID."""
        long_id = "A" * 129  # 129 characters
        with pytest.raises(ValueError, match="Connection ID cannot exceed 128 characters"):
            ConnectionSession(connection_id=long_id)
    
    def test_connected_status_requires_timestamp(self):
        """Test that connected status requires connected_at timestamp."""
        with pytest.raises(ValueError, match="Connected status requires connected_at timestamp"):
            ConnectionSession(
                connection_id="test-connection",
                status=ConnectionStatus.CONNECTED
            )
    
    def test_disconnected_status_requires_timestamp(self):
        """Test that disconnected status requires disconnected_at timestamp."""
        with pytest.raises(ValueError, match="Disconnected status requires disconnected_at timestamp"):
            ConnectionSession(
                connection_id="test-connection",
                status=ConnectionStatus.DISCONNECTED
            )
    
    def test_timestamp_ordering_validation(self):
        """Test validation of timestamp ordering."""
        now = datetime.utcnow()
        past = now - timedelta(hours=1)
        
        # disconnected_at before connected_at
        with pytest.raises(ValueError, match="Disconnected timestamp must be after connected timestamp"):
            ConnectionSession(
                connection_id="test-connection",
                status=ConnectionStatus.DISCONNECTED,
                connected_at=now,
                disconnected_at=past
            )
        
        # last_activity_at before connected_at
        with pytest.raises(ValueError, match="Last activity timestamp cannot be before connected timestamp"):
            ConnectionSession(
                connection_id="test-connection",
                status=ConnectionStatus.CONNECTED,
                connected_at=now,
                last_activity_at=past
            )
    
    def test_auto_set_timestamps(self):
        """Test automatic timestamp setting."""
        # Connected status should auto-set connected_at and last_activity_at
        now = datetime.utcnow()
        session = ConnectionSession(
            connection_id="test-connection",
            status=ConnectionStatus.CONNECTED,
            connected_at=now
        )
        
        assert session.connected_at == now
        assert session.last_activity_at == now  # Should be set to connected_at
    
    def test_connection_session_with_all_fields(self):
        """Test creating connection session with all fields."""
        now = datetime.utcnow()
        connected_time = now - timedelta(minutes=10)
        disconnected_time = now - timedelta(minutes=5)
        
        session = ConnectionSession(
            connection_id="full-test-connection",
            connection_type=SessionConnectionType.HTTP_POLLING,
            status=ConnectionStatus.DISCONNECTED,
            connected_at=connected_time,
            last_activity_at=now - timedelta(minutes=6),
            disconnected_at=disconnected_time,
            client_info={"ip": "192.168.1.1"},
            session_data={"user_id": "user123"},
            subscribed_topics={"topic1", "topic2"}
        )
        
        assert session.connection_id == "full-test-connection"
        assert session.connection_type == SessionConnectionType.HTTP_POLLING
        assert session.status == ConnectionStatus.DISCONNECTED
        assert session.connected_at == connected_time
        assert session.disconnected_at == disconnected_time
        assert session.client_info == {"ip": "192.168.1.1"}
        assert session.session_data == {"user_id": "user123"}
        assert session.subscribed_topics == {"topic1", "topic2"}
    
    def test_result_count_increment(self):
        """Test result count increment functionality."""
        session = ConnectionSession.create_new("test-123")
        session.connect()
        
        # Initial result count should be 0
        assert session.result_count == 0
        
        # Increment result count
        new_count = session.increment_result_count()
        assert new_count == 1
        assert session.result_count == 1
        
        # Increment again
        new_count = session.increment_result_count()
        assert new_count == 2
        assert session.result_count == 2
    
    def test_should_disconnect_due_to_result_limit(self):
        """Test disconnection due to result limit."""
        session = ConnectionSession.create_new("test-123")
        session.connect()
        
        # Should not disconnect initially
        assert not session.should_disconnect_due_to_limits()
        
        # Increment to max results
        for i in range(5):
            session.increment_result_count()
        
        # Should disconnect after reaching max results
        assert session.should_disconnect_due_to_limits()
        assert "Result limit reached" in session.get_disconnect_reason_for_limits()
    
    def test_should_disconnect_due_to_time_limit(self):
        """Test disconnection due to time limit."""
        # Create session with past connected_at time
        past_time = datetime.utcnow() - timedelta(minutes=3)
        session = ConnectionSession(
            connection_id="test-123",
            status=ConnectionStatus.CONNECTED,
            connected_at=past_time,
            last_activity_at=past_time
        )
        
        # Should disconnect due to time limit
        assert session.should_disconnect_due_to_limits()
        assert "Time limit reached" in session.get_disconnect_reason_for_limits()
    
    def test_should_not_disconnect_within_limits(self):
        """Test that connection doesn't disconnect within limits."""
        session = ConnectionSession.create_new("test-123")
        session.connect()
        
        # Increment result count but stay under limit
        for i in range(3):
            session.increment_result_count()
        
        # Should not disconnect
        assert not session.should_disconnect_due_to_limits()
    
    def test_connection_summary_includes_limit_info(self):
        """Test that connection summary includes limit information."""
        session = ConnectionSession.create_new("test-123")
        session.connect()
        session.increment_result_count()
        session.increment_result_count()
        
        summary = session.get_connection_summary()
        
        assert "result_count" in summary
        assert "max_results" in summary
        assert "max_connection_minutes" in summary
        assert "should_disconnect_due_to_limits" in summary
        
        assert summary["result_count"] == 2
        assert summary["max_results"] == 5
        assert summary["max_connection_minutes"] == 2
        assert summary["should_disconnect_due_to_limits"] == False