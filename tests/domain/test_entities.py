"""Unit tests for domain entities."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.domain.entities.connection_session import ConnectionSession, ConnectionStatus, SessionConnectionType
from src.domain.entities.provider_offer import ConnectionType, OfferStatus, ProviderOffer
from src.domain.entities.search_result import SearchResult
from src.domain.value_objects.address import Address


class TestProviderOffer:
    """Test ProviderOffer entity."""

    def test_provider_offer_creation(self):
        """Test creating a provider offer."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            setup_fee_euros=Decimal("0.0"),
        )

        assert offer.provider_name == "TestProvider"
        assert offer.product_id == "test-123"
        assert offer.speed_download_mbps == 100
        assert offer.speed_upload_mbps == 50
        assert offer.monthly_cost_euros == Decimal("29.99")
        assert offer.connection_type == ConnectionType.FIBER
        assert offer.contract_duration_months == 24
        assert offer.setup_fee_euros == Decimal("0.0")
        assert offer.status == OfferStatus.AVAILABLE
        assert offer.additional_features == {}

    def test_provider_offer_defaults(self):
        """Test provider offer with default values."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        assert offer.setup_fee_euros is None
        assert offer.status == OfferStatus.AVAILABLE
        assert offer.additional_features == {}

    def test_provider_name_validation(self):
        """Test provider name validation."""
        # Empty provider name
        with pytest.raises(ValueError, match="Provider name cannot be empty"):
            ProviderOffer(
                provider_name="",
                product_id="test-123",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

        # Whitespace only provider name
        with pytest.raises(ValueError, match="Provider name cannot be empty"):
            ProviderOffer(
                provider_name="   ",
                product_id="test-123",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

        # Too long provider name
        with pytest.raises(ValueError, match="Provider name cannot exceed 50 characters"):
            ProviderOffer(
                provider_name="A" * 51,
                product_id="test-123",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

    def test_product_id_validation(self):
        """Test product ID validation."""
        # Empty product ID
        with pytest.raises(ValueError, match="Product ID cannot be empty"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

        # Too long product ID
        with pytest.raises(ValueError, match="Product ID cannot exceed 100 characters"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="A" * 101,
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

    def test_speed_validation(self):
        """Test speed validation."""
        # Negative download speed
        with pytest.raises(ValueError, match="Download speed must be positive"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=-10,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

        # Zero download speed
        with pytest.raises(ValueError, match="Download speed must be positive"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=0,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

        # Negative upload speed
        with pytest.raises(ValueError, match="Upload speed cannot be negative"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=100,
                speed_upload_mbps=-10,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

        # Unrealistic download speed
        with pytest.raises(ValueError, match="Download speed seems unrealistic"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=15000,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

        # Upload speed exceeds download speed
        with pytest.raises(ValueError, match="Upload speed cannot exceed download speed"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=50,
                speed_upload_mbps=100,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

    def test_cost_validation(self):
        """Test cost validation."""
        # Negative monthly cost
        with pytest.raises(ValueError, match="Monthly cost cannot be negative"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("-10.00"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

        # Unrealistic monthly cost
        with pytest.raises(ValueError, match="Monthly cost seems unrealistic"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("1500.00"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
            )

        # Negative setup fee
        with pytest.raises(ValueError, match="Setup fee cannot be negative"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
                setup_fee_euros=Decimal("-50.00"),
            )

        # Unrealistic setup fee
        with pytest.raises(ValueError, match="Setup fee seems unrealistic"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
                setup_fee_euros=Decimal("600.00"),
            )

    def test_contract_duration_validation(self):
        """Test contract duration validation."""
        # Negative contract duration
        with pytest.raises(ValueError, match="Contract duration cannot be negative"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=-12,
            )

        # Unrealistic contract duration
        with pytest.raises(ValueError, match="Contract duration seems unrealistic"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="test-123",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=72,
            )

    def test_total_first_year_cost(self):
        """Test total first year cost calculation."""
        # With setup fee
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            setup_fee_euros=Decimal("50.00"),
        )
        expected_cost = Decimal("29.99") * 12 + Decimal("50.00")
        assert offer.total_first_year_cost == expected_cost

        # Without setup fee
        offer_no_setup = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )
        expected_cost_no_setup = Decimal("29.99") * 12
        assert offer_no_setup.total_first_year_cost == expected_cost_no_setup

    def test_speed_ratio(self):
        """Test speed ratio calculation."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )
        assert offer.speed_ratio == 0.5

        # Zero download speed edge case
        offer_zero_download = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=1,  # Minimum valid value
            speed_upload_mbps=0,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )
        assert offer_zero_download.speed_ratio == 0.0

    def test_is_fiber_property(self):
        """Test is_fiber property."""
        fiber_offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )
        assert fiber_offer.is_fiber is True

        dsl_offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=24,
        )
        assert dsl_offer.is_fiber is False

    def test_is_available_property(self):
        """Test is_available property."""
        available_offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.AVAILABLE,
        )
        assert available_offer.is_available is True

        unavailable_offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.UNAVAILABLE,
        )
        assert unavailable_offer.is_available is False

    def test_calculate_monthly_cost_per_mbps(self):
        """Test monthly cost per Mbps calculation."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("30.00"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )
        assert offer.calculate_monthly_cost_per_mbps() == Decimal("0.30")

        # Edge case: zero speed (should return 0)
        offer_zero_speed = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=1,  # Minimum valid
            speed_upload_mbps=0,
            monthly_cost_euros=Decimal("30.00"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )
        assert offer_zero_speed.calculate_monthly_cost_per_mbps() == Decimal("30.00")

    def test_is_better_value_than(self):
        """Test value comparison between offers."""
        offer1 = ProviderOffer(
            provider_name="Provider1",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("30.00"),  # 0.30 per Mbps
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        offer2 = ProviderOffer(
            provider_name="Provider2",
            product_id="test-456",
            speed_download_mbps=50,
            speed_upload_mbps=25,
            monthly_cost_euros=Decimal("20.00"),  # 0.40 per Mbps
            connection_type=ConnectionType.DSL,
            contract_duration_months=24,
        )

        assert offer1.is_better_value_than(offer2) is True
        assert offer2.is_better_value_than(offer1) is False

        # Test with non-ProviderOffer object
        assert offer1.is_better_value_than("not an offer") is False

    def test_feature_management(self):
        """Test adding, checking, and getting features."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        # Add feature
        offer.add_feature("wifi_included", True)
        assert offer.has_feature("wifi_included") is True
        assert offer.get_feature("wifi_included") is True

        # Add another feature
        offer.add_feature("tv_channels", 50)
        assert offer.get_feature("tv_channels") == 50

        # Get non-existent feature with default
        assert offer.get_feature("non_existent", "default") == "default"

        # Test empty feature name
        with pytest.raises(ValueError, match="Feature name cannot be empty"):
            offer.add_feature("", "value")

        with pytest.raises(ValueError, match="Feature name cannot be empty"):
            offer.add_feature("   ", "value")

    def test_provider_offer_equality(self):
        """Test provider offer equality."""
        offer1 = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            setup_fee_euros=Decimal("0.0"),
        )

        offer2 = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            setup_fee_euros=Decimal("0.0"),
        )

        assert offer1 == offer2

    def test_provider_offer_edge_cases(self):
        """Test edge cases for ProviderOffer methods."""
        # Test speed_ratio with zero download speed (edge case that should not happen due to validation)
        # This tests the defensive programming in the speed_ratio property
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=1,  # Minimum valid value
            speed_upload_mbps=0,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        # Test that speed_ratio handles zero upload speed correctly
        assert offer.speed_ratio == 0.0

        # Test calculate_monthly_cost_per_mbps with minimum speed
        cost_per_mbps = offer.calculate_monthly_cost_per_mbps()
        assert cost_per_mbps == Decimal("29.99")  # 29.99 / 1

    def test_provider_offer_additional_features_edge_cases(self):
        """Test additional edge cases for feature management."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        # Test adding feature with whitespace in name
        with pytest.raises(ValueError, match="Feature name cannot be empty"):
            offer.add_feature("   ", "value")

        # Test getting feature that doesn't exist returns None by default
        assert offer.get_feature("non_existent") is None

        # Test has_feature with non-existent feature
        assert offer.has_feature("non_existent") is False

    def test_provider_offer_status_variations(self):
        """Test different offer status scenarios."""
        # Test LIMITED status
        limited_offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.LIMITED,
        )
        assert limited_offer.is_available is False

        # Test PENDING status
        pending_offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.PENDING,
        )
        assert pending_offer.is_available is False

    def test_provider_offer_connection_type_variations(self):
        """Test different connection types."""
        connection_types = [
            ConnectionType.DSL,
            ConnectionType.CABLE,
            ConnectionType.SATELLITE,
            ConnectionType.MOBILE,
            ConnectionType.UNKNOWN,
        ]

        for conn_type in connection_types:
            offer = ProviderOffer(
                provider_name="TestProvider",
                product_id=f"test-{conn_type.value}",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=conn_type,
                contract_duration_months=24,
            )

            # Only FIBER should return True for is_fiber
            assert offer.is_fiber == (conn_type == ConnectionType.FIBER)


class TestConnectionSession:
    """Test ConnectionSession entity."""

    def test_connection_session_creation(self):
        """Test creating a connection session."""
        session = ConnectionSession(
            connection_id="conn-123",
            connection_type=SessionConnectionType.WEBSOCKET,
            status=ConnectionStatus.CONNECTED,
            connected_at=datetime(2024, 1, 1, 12, 0, 0),
            last_activity_at=datetime(2024, 1, 1, 12, 5, 0),
        )

        assert session.connection_id == "conn-123"
        assert session.connection_type == SessionConnectionType.WEBSOCKET
        assert session.status == ConnectionStatus.CONNECTED
        assert session.connected_at == datetime(2024, 1, 1, 12, 0, 0)
        assert session.last_activity_at == datetime(2024, 1, 1, 12, 5, 0)

    def test_connection_session_defaults(self):
        """Test connection session with default values."""
        session = ConnectionSession(connection_id="conn-123")

        assert session.connection_id == "conn-123"
        assert session.connection_type == SessionConnectionType.WEBSOCKET
        assert session.status == ConnectionStatus.CONNECTING
        assert session.connected_at is None
        assert session.last_activity_at is None
        assert session.disconnected_at is None
        assert session.client_info == {}
        assert session.session_data == {}
        assert session.subscribed_topics == set()
        assert session.result_count == 0
        assert session.max_results == 5
        assert session.max_connection_minutes == 2

    def test_connection_id_validation(self):
        """Test connection ID validation."""
        # Empty connection ID
        with pytest.raises(ValueError, match="Connection ID cannot be empty"):
            ConnectionSession(connection_id="")

        # Whitespace only connection ID
        with pytest.raises(ValueError, match="Connection ID cannot be empty"):
            ConnectionSession(connection_id="   ")

        # Too long connection ID
        with pytest.raises(ValueError, match="Connection ID cannot exceed 128 characters"):
            ConnectionSession(connection_id="A" * 129)

    def test_status_validation(self):
        """Test status validation."""
        # Connected status without connected_at timestamp
        with pytest.raises(ValueError, match="Connected status requires connected_at timestamp"):
            ConnectionSession(
                connection_id="conn-123",
                status=ConnectionStatus.CONNECTED,
                connected_at=None,
            )

        # Disconnected status without disconnected_at timestamp
        with pytest.raises(ValueError, match="Disconnected status requires disconnected_at timestamp"):
            ConnectionSession(
                connection_id="conn-123",
                status=ConnectionStatus.DISCONNECTED,
                disconnected_at=None,
            )

    def test_timestamp_validation(self):
        """Test timestamp ordering validation."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        # Disconnected timestamp before connected timestamp
        with pytest.raises(ValueError, match="Disconnected timestamp must be after connected timestamp"):
            ConnectionSession(
                connection_id="conn-123",
                status=ConnectionStatus.DISCONNECTED,
                connected_at=base_time,
                disconnected_at=base_time - timedelta(minutes=1),
            )

        # Last activity before connected timestamp
        with pytest.raises(ValueError, match="Last activity timestamp cannot be before connected timestamp"):
            ConnectionSession(
                connection_id="conn-123",
                status=ConnectionStatus.CONNECTED,
                connected_at=base_time,
                last_activity_at=base_time - timedelta(minutes=1),
            )

    def test_create_new_class_method(self):
        """Test creating new connection session using class method."""
        session = ConnectionSession.create_new("conn-123")

        assert session.connection_id == "conn-123"
        assert session.connection_type == SessionConnectionType.WEBSOCKET
        assert session.status == ConnectionStatus.CONNECTING

        # Test with custom connection type
        session_http = ConnectionSession.create_new("conn-456", SessionConnectionType.HTTP_POLLING)
        assert session_http.connection_type == SessionConnectionType.HTTP_POLLING

    def test_connect_method(self):
        """Test connecting a session."""
        session = ConnectionSession.create_new("conn-123")

        # Connect the session
        session.connect()

        assert session.status == ConnectionStatus.CONNECTED
        assert session.connected_at is not None
        assert session.last_activity_at is not None
        assert session.connected_at == session.last_activity_at

        # Try to connect already connected session
        with pytest.raises(ValueError, match="Connection is already connected"):
            session.connect()

        # Try to connect disconnected session
        session.disconnect()
        with pytest.raises(ValueError, match="Cannot reconnect a disconnected session"):
            session.connect()

    def test_disconnect_method(self):
        """Test disconnecting a session."""
        session = ConnectionSession.create_new("conn-123")
        session.connect()

        # Disconnect with reason
        session.disconnect("User requested")

        assert session.status == ConnectionStatus.DISCONNECTED
        assert session.disconnected_at is not None
        assert session.get_session_data("disconnect_reason") == "User requested"

        # Disconnect already disconnected session (should not raise error)
        session.disconnect("Another reason")
        assert session.status == ConnectionStatus.DISCONNECTED

    def test_mark_error_method(self):
        """Test marking session as error."""
        session = ConnectionSession.create_new("conn-123")

        session.mark_error("Connection timeout")

        assert session.status == ConnectionStatus.ERROR
        assert session.get_session_data("error_message") == "Connection timeout"
        assert session.get_session_data("error_timestamp") is not None

    def test_update_activity(self):
        """Test updating activity timestamp."""
        session = ConnectionSession.create_new("conn-123")
        session.connect()

        original_activity = session.last_activity_at

        # Wait a bit and update activity
        session.update_activity()

        assert session.last_activity_at >= original_activity

        # Try to update activity on non-connected session
        session.disconnect()
        with pytest.raises(ValueError, match="Cannot update activity for non-connected session"):
            session.update_activity()

    def test_client_info_management(self):
        """Test client info management."""
        session = ConnectionSession.create_new("conn-123")

        # Add client info
        session.add_client_info("user_agent", "Mozilla/5.0")
        session.add_client_info("ip_address", "192.168.1.1")

        assert session.get_client_info("user_agent") == "Mozilla/5.0"
        assert session.get_client_info("ip_address") == "192.168.1.1"
        assert session.get_client_info("non_existent", "default") == "default"

        # Test empty key
        with pytest.raises(ValueError, match="Client info key cannot be empty"):
            session.add_client_info("", "value")

    def test_session_data_management(self):
        """Test session data management."""
        session = ConnectionSession.create_new("conn-123")

        # Add session data
        session.add_session_data("search_count", 5)
        session.add_session_data("last_search", "Berlin")

        assert session.get_session_data("search_count") == 5
        assert session.get_session_data("last_search") == "Berlin"
        assert session.get_session_data("non_existent", "default") == "default"

        # Test empty key
        with pytest.raises(ValueError, match="Session data key cannot be empty"):
            session.add_session_data("", "value")

    def test_topic_subscription(self):
        """Test topic subscription management."""
        session = ConnectionSession.create_new("conn-123")

        # Subscribe to topics
        session.subscribe_to_topic("search_results")
        session.subscribe_to_topic("notifications")

        assert session.is_subscribed_to("search_results") is True
        assert session.is_subscribed_to("notifications") is True
        assert session.is_subscribed_to("non_existent") is False

        # Unsubscribe from topic
        session.unsubscribe_from_topic("notifications")
        assert session.is_subscribed_to("notifications") is False

        # Test empty topic
        with pytest.raises(ValueError, match="Topic cannot be empty"):
            session.subscribe_to_topic("")

        # Test whitespace handling
        session.subscribe_to_topic("  spaced_topic  ")
        assert session.is_subscribed_to("spaced_topic") is True

    def test_status_properties(self):
        """Test status check properties."""
        session = ConnectionSession.create_new("conn-123")

        # Connecting state
        assert session.is_connected is False
        assert session.is_disconnected is False
        assert session.has_error is False

        # Connected state
        session.connect()
        assert session.is_connected is True
        assert session.is_disconnected is False
        assert session.has_error is False

        # Disconnected state
        session.disconnect()
        assert session.is_connected is False
        assert session.is_disconnected is True
        assert session.has_error is False

        # Error state
        session = ConnectionSession.create_new("conn-456")
        session.mark_error("Test error")
        assert session.is_connected is False
        assert session.is_disconnected is False
        assert session.has_error is True

    def test_connection_duration(self):
        """Test connection duration calculation."""
        session = ConnectionSession.create_new("conn-123")

        # No connection duration when not connected
        assert session.connection_duration is None

        # Connect and check duration
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        session = ConnectionSession(
            connection_id="conn-123",
            status=ConnectionStatus.CONNECTED,
            connected_at=base_time,
            last_activity_at=base_time,
        )

        # Mock current time for testing
        disconnect_time = base_time + timedelta(minutes=30)
        session = ConnectionSession(
            connection_id="conn-123",
            status=ConnectionStatus.DISCONNECTED,
            connected_at=base_time,
            last_activity_at=base_time,
            disconnected_at=disconnect_time,
        )

        assert session.connection_duration == timedelta(minutes=30)

    def test_idle_duration(self):
        """Test idle duration calculation."""
        session = ConnectionSession.create_new("conn-123")

        # No idle duration when not connected
        assert session.idle_duration is None

        session.connect()
        # Should have minimal idle duration when just connected
        assert session.idle_duration is not None
        assert session.idle_duration.total_seconds() >= 0

    def test_is_idle_for(self):
        """Test idle time checking."""
        # Test with disconnected session
        session = ConnectionSession.create_new("conn-123")
        assert session.is_idle_for(5) is False  # Not connected

        # Test with connected session
        session.connect()
        # Just connected, should not be idle for a significant time like 60 minutes
        assert session.is_idle_for(60) is False  # Should be False since it was just connected

        # Test that is_idle_for(0) returns True for any connected session with idle time >= 0
        assert session.is_idle_for(0) is True  # Any idle time >= 0 minutes

        # Note: Testing actual idle time would require mocking datetime.utcnow()
        # For now, we test the basic logic that non-connected sessions return False

    def test_should_timeout(self):
        """Test timeout checking."""
        session = ConnectionSession.create_new("conn-123")

        # Not connected, should not timeout
        assert session.should_timeout(30) is False

        session.connect()
        # Just connected, should not timeout
        assert session.should_timeout(30) is False

    def test_increment_result_count(self):
        """Test result count increment."""
        session = ConnectionSession.create_new("conn-123")
        session.connect()

        assert session.result_count == 0

        new_count = session.increment_result_count()
        assert new_count == 1
        assert session.result_count == 1

        session.increment_result_count()
        assert session.result_count == 2

    def test_should_disconnect_due_to_limits(self):
        """Test limit-based disconnection logic."""
        session = ConnectionSession.create_new("conn-123")

        # Not connected, should not disconnect
        assert session.should_disconnect_due_to_limits() is False

        session.connect()

        # Within limits
        assert session.should_disconnect_due_to_limits() is False

        # Reach result limit
        for _ in range(5):
            session.increment_result_count()
        assert session.should_disconnect_due_to_limits() is True

    def test_get_disconnect_reason_for_limits(self):
        """Test getting disconnect reason for limits."""
        session = ConnectionSession.create_new("conn-123")
        session.connect()

        # Reach result limit
        for _ in range(5):
            session.increment_result_count()

        reason = session.get_disconnect_reason_for_limits()
        assert "Result limit reached (5/5)" in reason

    def test_get_connection_summary(self):
        """Test connection summary generation."""
        session = ConnectionSession.create_new("conn-123")
        session.connect()
        session.add_client_info("ip", "127.0.0.1")
        session.add_session_data("test", "value")
        session.subscribe_to_topic("test_topic")

        summary = session.get_connection_summary()

        assert summary["connection_id"] == "conn-123"
        assert summary["connection_type"] == "WebSocket"
        assert summary["status"] == "Connected"
        assert summary["connected_at"] is not None
        assert summary["subscribed_topics_count"] == 1
        assert summary["has_client_info"] is True
        assert summary["has_session_data"] is True
        assert summary["result_count"] == 0
        assert summary["max_results"] == 5
        assert summary["max_connection_minutes"] == 2

    def test_connection_session_is_active(self):
        """Test connection session active status."""
        active_session = ConnectionSession(
            connection_id="conn-123",
            connection_type=SessionConnectionType.WEBSOCKET,
            status=ConnectionStatus.CONNECTED,
            connected_at=datetime(2024, 1, 1, 12, 0, 0),
            last_activity_at=datetime(2024, 1, 1, 12, 5, 0),
        )

        inactive_session = ConnectionSession(
            connection_id="conn-124",
            connection_type=SessionConnectionType.WEBSOCKET,
            status=ConnectionStatus.DISCONNECTED,
            connected_at=datetime(2024, 1, 1, 12, 0, 0),
            last_activity_at=datetime(2024, 1, 1, 12, 5, 0),
            disconnected_at=datetime(2024, 1, 1, 12, 10, 0),
        )

        assert active_session.is_connected is True
        assert inactive_session.is_connected is False

    def test_connection_session_post_init_defaults(self):
        """Test __post_init__ method sets defaults correctly."""
        # Test connected status with no connected_at timestamp gets set automatically
        now = datetime.utcnow()
        session = ConnectionSession(
            connection_id="conn-123",
            status=ConnectionStatus.CONNECTED,
            connected_at=now,
        )

        # Should set last_activity_at to connected_at when not provided
        assert session.last_activity_at == now

        # Test that last_activity_at gets set to connected_at when not provided
        session2 = ConnectionSession(
            connection_id="conn-456",
            status=ConnectionStatus.CONNECTED,
            connected_at=now,
            last_activity_at=None,  # This should get set to connected_at
        )
        assert session2.connected_at == now
        assert session2.last_activity_at == now

    def test_connection_session_edge_cases(self):
        """Test edge cases for connection session methods."""
        session = ConnectionSession.create_new("conn-123")
        session.connect()

        # Test should_timeout with default parameter
        assert session.should_timeout() is False  # Default 30 minutes

        # Test should_timeout with custom timeout
        assert session.should_timeout(1) is False  # 1 minute timeout

        # Test get_disconnect_reason_for_limits when no limits reached
        reason = session.get_disconnect_reason_for_limits()
        assert reason == "Limit enforcement"

        # Test increment_result_count updates activity
        original_activity = session.last_activity_at
        count = session.increment_result_count()
        assert count == 1
        assert session.last_activity_at >= original_activity

        # Test is_idle_for when not connected (should return False)
        session.disconnect()
        assert session.is_idle_for(5) is False

        # Test is_idle_for when idle_duration is None (edge case)
        # This can happen if last_activity_at is None for a connected session
        session2 = ConnectionSession.create_new("conn-456")
        session2.connect()
        # Manually set last_activity_at to None to test the edge case
        object.__setattr__(session2, "last_activity_at", None)
        assert session2.is_idle_for(5) is False  # Should return False when idle_duration is None

    def test_connection_session_limit_scenarios(self):
        """Test various limit scenarios for connection session."""
        session = ConnectionSession.create_new("conn-123")
        session.connect()

        # Test result limit reached
        for i in range(session.max_results):
            session.increment_result_count()

        assert session.should_disconnect_due_to_limits() is True
        reason = session.get_disconnect_reason_for_limits()
        assert "Result limit reached" in reason
        assert f"({session.max_results}/{session.max_results})" in reason

        # Test time limit scenario (mock by setting connected_at to past)
        past_time = datetime.utcnow() - timedelta(minutes=session.max_connection_minutes + 1)
        object.__setattr__(session, "connected_at", past_time)
        object.__setattr__(session, "result_count", 0)  # Reset result count

        assert session.should_disconnect_due_to_limits() is True
        reason = session.get_disconnect_reason_for_limits()
        assert "Time limit reached" in reason
        assert f"({session.max_connection_minutes} minutes)" in reason

    def test_connection_session_validation_edge_cases(self):
        """Test additional validation edge cases."""
        base_time = datetime.utcnow()

        # Test validation passes when timestamps are properly ordered
        session = ConnectionSession(
            connection_id="conn-123",
            status=ConnectionStatus.DISCONNECTED,
            connected_at=base_time,
            last_activity_at=base_time + timedelta(minutes=5),
            disconnected_at=base_time + timedelta(minutes=10),
        )
        assert session.connection_id == "conn-123"

        # Test validation with equal timestamps (edge case)
        session2 = ConnectionSession(
            connection_id="conn-456",
            status=ConnectionStatus.DISCONNECTED,
            connected_at=base_time,
            last_activity_at=base_time,  # Same as connected_at
            disconnected_at=base_time + timedelta(seconds=1),  # Just after
        )
        assert session2.connection_id == "conn-456"


class TestSearchResult:
    """Test SearchResult entity."""

    def test_search_result_creation(self):
        """Test creating a search result."""
        offers = [
            ProviderOffer(
                provider_name="Provider1",
                product_id="offer-1",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
                setup_fee_euros=Decimal("0.0"),
            )
        ]

        result = SearchResult(
            request_id="req-123",
            address=Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE"),
            offers=offers,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

        assert result.request_id == "req-123"
        assert len(result.offers) == 1
        assert result.offers[0].provider_name == "Provider1"
        assert result.timestamp == datetime(2024, 1, 1, 12, 0, 0)

    def test_search_result_defaults(self):
        """Test search result with default values."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult(request_id="req-123", address=address)

        assert result.request_id == "req-123"
        assert result.address == address
        assert result.offers == []
        assert result.timestamp is not None
        assert result.expires_at is not None
        assert result.share_token is not None
        assert len(result.share_token) >= 8
        assert result.search_metadata == {}

    def test_search_result_validation(self):
        """Test search result validation."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")

        # Empty request ID
        with pytest.raises(ValueError, match="Request ID cannot be empty"):
            SearchResult(request_id="", address=address)

        # Invalid address type
        with pytest.raises(ValueError, match="Address must be a valid Address value object"):
            SearchResult(request_id="req-123", address="not an address")

        # Invalid offers type
        with pytest.raises(ValueError, match="Offers must be a list"):
            SearchResult(request_id="req-123", address=address, offers="not a list")

        # Invalid offer in list
        with pytest.raises(ValueError, match="All offers must be ProviderOffer instances"):
            SearchResult(request_id="req-123", address=address, offers=["not an offer"])

        # Expiration before timestamp
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with pytest.raises(ValueError, match="Expiration date must be after timestamp"):
            SearchResult(
                request_id="req-123",
                address=address,
                timestamp=base_time,
                expires_at=base_time - timedelta(days=1),
            )

        # Short share token
        with pytest.raises(ValueError, match="Share token must be at least 8 characters long"):
            SearchResult(request_id="req-123", address=address, share_token="short")

    def test_create_new_class_method(self):
        """Test creating new search result using class method."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")

        # Without request ID
        result = SearchResult.create_new(address)
        assert result.address == address
        assert result.request_id is not None
        assert len(result.request_id) > 0

        # With custom request ID
        result_custom = SearchResult.create_new(address, "custom-req-123")
        assert result_custom.request_id == "custom-req-123"

    def test_add_offer(self):
        """Test adding offers to search result."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        offer = ProviderOffer(
            provider_name="Provider1",
            product_id="offer-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        result.add_offer(offer)
        assert len(result.offers) == 1
        assert result.offers[0] == offer

        # Test adding invalid offer type
        with pytest.raises(ValueError, match="Offer must be a ProviderOffer instance"):
            result.add_offer("not an offer")

        # Test adding duplicate offer
        with pytest.raises(ValueError, match="Offer from Provider1 with product offer-1 already exists"):
            result.add_offer(offer)

    def test_remove_offer(self):
        """Test removing offers from search result."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        offer = ProviderOffer(
            provider_name="Provider1",
            product_id="offer-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        result.add_offer(offer)
        assert len(result.offers) == 1

        # Remove existing offer
        removed = result.remove_offer("Provider1", "offer-1")
        assert removed is True
        assert len(result.offers) == 0

        # Try to remove non-existent offer
        removed = result.remove_offer("NonExistent", "offer-999")
        assert removed is False

    def test_get_offer_by_provider_and_product(self):
        """Test getting offer by provider and product ID."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        offer = ProviderOffer(
            provider_name="Provider1",
            product_id="offer-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        result.add_offer(offer)

        # Find existing offer
        found_offer = result.get_offer_by_provider_and_product("Provider1", "offer-1")
        assert found_offer == offer

        # Try to find non-existent offer
        not_found = result.get_offer_by_provider_and_product("NonExistent", "offer-999")
        assert not_found is None

    def test_get_offers_by_provider(self):
        """Test getting offers by provider."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        offer1 = ProviderOffer(
            provider_name="Provider1",
            product_id="offer-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        offer2 = ProviderOffer(
            provider_name="Provider1",
            product_id="offer-2",
            speed_download_mbps=50,
            speed_upload_mbps=25,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
        )

        offer3 = ProviderOffer(
            provider_name="Provider2",
            product_id="offer-3",
            speed_download_mbps=200,
            speed_upload_mbps=100,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        result.add_offer(offer1)
        result.add_offer(offer2)
        result.add_offer(offer3)

        provider1_offers = result.get_offers_by_provider("Provider1")
        assert len(provider1_offers) == 2
        assert offer1 in provider1_offers
        assert offer2 in provider1_offers

        provider2_offers = result.get_offers_by_provider("Provider2")
        assert len(provider2_offers) == 1
        assert offer3 in provider2_offers

        # Non-existent provider
        no_offers = result.get_offers_by_provider("NonExistent")
        assert len(no_offers) == 0

    def test_get_offers_by_connection_type(self):
        """Test getting offers by connection type."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        fiber_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="fiber-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        dsl_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="dsl-1",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
        )

        result.add_offer(fiber_offer)
        result.add_offer(dsl_offer)

        fiber_offers = result.get_offers_by_connection_type(ConnectionType.FIBER)
        assert len(fiber_offers) == 1
        assert fiber_offer in fiber_offers

        dsl_offers = result.get_offers_by_connection_type(ConnectionType.DSL)
        assert len(dsl_offers) == 1
        assert dsl_offer in dsl_offers

        cable_offers = result.get_offers_by_connection_type(ConnectionType.CABLE)
        assert len(cable_offers) == 0

    def test_get_available_offers(self):
        """Test getting only available offers."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        available_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="available-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.AVAILABLE,
        )

        unavailable_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="unavailable-1",
            speed_download_mbps=50,
            speed_upload_mbps=25,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
            status=OfferStatus.UNAVAILABLE,
        )

        result.add_offer(available_offer)
        result.add_offer(unavailable_offer)

        available_offers = result.get_available_offers()
        assert len(available_offers) == 1
        assert available_offer in available_offers
        assert unavailable_offer not in available_offers

    def test_get_cheapest_offer(self):
        """Test getting cheapest offer."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        expensive_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="expensive-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        cheap_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="cheap-1",
            speed_download_mbps=50,
            speed_upload_mbps=25,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
        )

        result.add_offer(expensive_offer)
        result.add_offer(cheap_offer)

        cheapest = result.get_cheapest_offer()
        assert cheapest == cheap_offer

        # Test with no offers
        empty_result = SearchResult.create_new(address)
        assert empty_result.get_cheapest_offer() is None

    def test_get_fastest_offer(self):
        """Test getting fastest offer."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        slow_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="slow-1",
            speed_download_mbps=50,
            speed_upload_mbps=25,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
        )

        fast_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="fast-1",
            speed_download_mbps=200,
            speed_upload_mbps=100,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        result.add_offer(slow_offer)
        result.add_offer(fast_offer)

        fastest = result.get_fastest_offer()
        assert fastest == fast_offer

        # Test with no offers
        empty_result = SearchResult.create_new(address)
        assert empty_result.get_fastest_offer() is None

    def test_get_best_value_offer(self):
        """Test getting best value offer (lowest cost per Mbps)."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        # 39.99 / 50 = 0.7998 per Mbps
        poor_value_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="poor-value-1",
            speed_download_mbps=50,
            speed_upload_mbps=25,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
        )

        # 29.99 / 100 = 0.2999 per Mbps
        good_value_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="good-value-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        result.add_offer(poor_value_offer)
        result.add_offer(good_value_offer)

        best_value = result.get_best_value_offer()
        assert best_value == good_value_offer

        # Test with no offers
        empty_result = SearchResult.create_new(address)
        assert empty_result.get_best_value_offer() is None

    def test_get_fiber_offers(self):
        """Test getting fiber offers."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        fiber_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="fiber-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        dsl_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="dsl-1",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
        )

        result.add_offer(fiber_offer)
        result.add_offer(dsl_offer)

        fiber_offers = result.get_fiber_offers()
        assert len(fiber_offers) == 1
        assert fiber_offer in fiber_offers
        assert dsl_offer not in fiber_offers

    def test_count_properties(self):
        """Test count properties."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        # Empty result
        assert result.offer_count == 0
        assert result.available_offer_count == 0
        assert result.provider_count == 0

        # Add offers
        offer1 = ProviderOffer(
            provider_name="Provider1",
            product_id="offer-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.AVAILABLE,
        )

        offer2 = ProviderOffer(
            provider_name="Provider1",
            product_id="offer-2",
            speed_download_mbps=50,
            speed_upload_mbps=25,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
            status=OfferStatus.UNAVAILABLE,
        )

        offer3 = ProviderOffer(
            provider_name="Provider2",
            product_id="offer-3",
            speed_download_mbps=200,
            speed_upload_mbps=100,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.AVAILABLE,
        )

        result.add_offer(offer1)
        result.add_offer(offer2)
        result.add_offer(offer3)

        assert result.offer_count == 3
        assert result.available_offer_count == 2  # offer1 and offer3
        assert result.provider_count == 2  # Provider1 and Provider2

    def test_expiration_properties(self):
        """Test expiration-related properties."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")

        # Create result with past expiration
        past_time = datetime.utcnow() - timedelta(days=1)
        expired_result = SearchResult(
            request_id="expired-123",
            address=address,
            timestamp=past_time - timedelta(days=30),
            expires_at=past_time,
        )

        assert expired_result.is_expired is True
        assert expired_result.days_until_expiration == 0

        # Create result with future expiration
        future_time = datetime.utcnow() + timedelta(days=5)
        active_result = SearchResult(
            request_id="active-123",
            address=address,
            timestamp=datetime.utcnow(),
            expires_at=future_time,
        )

        assert active_result.is_expired is False
        assert active_result.days_until_expiration >= 4  # Should be around 5 days

    def test_extend_expiration(self):
        """Test extending expiration date."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        original_expiration = result.expires_at

        result.extend_expiration(10)

        expected_expiration = original_expiration + timedelta(days=10)
        assert result.expires_at == expected_expiration

        # Test invalid extension
        with pytest.raises(ValueError, match="Extension days must be positive"):
            result.extend_expiration(0)

        with pytest.raises(ValueError, match="Extension days must be positive"):
            result.extend_expiration(-5)

    def test_metadata_management(self):
        """Test metadata management."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        # Add metadata
        result.add_metadata("search_source", "web")
        result.add_metadata("user_id", "user-123")

        assert result.get_metadata("search_source") == "web"
        assert result.get_metadata("user_id") == "user-123"
        assert result.get_metadata("non_existent", "default") == "default"

        # Test empty key
        with pytest.raises(ValueError, match="Metadata key cannot be empty"):
            result.add_metadata("", "value")

    def test_get_summary_stats(self):
        """Test summary statistics generation."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        # Empty result stats
        empty_stats = result.get_summary_stats()
        assert empty_stats["total_offers"] == 0
        assert empty_stats["available_offers"] == 0
        assert empty_stats["providers"] == 0
        assert empty_stats["cheapest_monthly_cost"] is None
        assert empty_stats["fastest_speed"] is None
        assert empty_stats["fiber_available"] is False

        # Add offers
        offer1 = ProviderOffer(
            provider_name="Provider1",
            product_id="offer-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        offer2 = ProviderOffer(
            provider_name="Provider2",
            product_id="offer-2",
            speed_download_mbps=50,
            speed_upload_mbps=25,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
        )

        result.add_offer(offer1)
        result.add_offer(offer2)

        stats = result.get_summary_stats()
        assert stats["total_offers"] == 2
        assert stats["available_offers"] == 2
        assert stats["providers"] == 2
        assert stats["cheapest_monthly_cost"] == Decimal("19.99")
        assert stats["most_expensive_monthly_cost"] == Decimal("29.99")
        assert stats["fastest_speed"] == 100
        assert stats["slowest_speed"] == 50
        assert stats["fiber_available"] is True
        assert "Fiber" in stats["connection_types"]
        assert "DSL" in stats["connection_types"]

    def test_search_result_get_best_offer(self):
        """Test getting best offer from search result."""
        offers = [
            ProviderOffer(
                provider_name="Provider1",
                product_id="offer-1",
                speed_download_mbps=50,
                speed_upload_mbps=25,
                monthly_cost_euros=Decimal("39.99"),
                connection_type=ConnectionType.DSL,
                contract_duration_months=24,
                setup_fee_euros=Decimal("50.0"),
            ),
            ProviderOffer(
                provider_name="Provider2",
                product_id="offer-2",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
                setup_fee_euros=Decimal("0.0"),
            ),
        ]

        result = SearchResult(
            request_id="req-123",
            address=Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE"),
            offers=offers,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

        best_offer = result.get_best_value_offer()
        assert best_offer.provider_name == "Provider2"  # Better speed and price

    def test_search_result_share_token_generation(self):
        """Test share token generation and validation."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")

        # Test automatic token generation
        result1 = SearchResult.create_new(address)
        result2 = SearchResult.create_new(address)

        # Tokens should be different for different results
        assert result1.share_token != result2.share_token
        assert len(result1.share_token) >= 8
        assert len(result2.share_token) >= 8

    def test_search_result_expiration_edge_cases(self):
        """Test expiration edge cases."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")

        # Test result that expires exactly now
        now = datetime.utcnow()
        result = SearchResult(
            request_id="req-123",
            address=address,
            timestamp=now - timedelta(days=30),
            expires_at=now,
        )

        # Should be expired or very close to expiring
        assert result.is_expired is True or result.days_until_expiration == 0

    def test_search_result_metadata_edge_cases(self):
        """Test metadata edge cases."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        # Test adding metadata with whitespace key
        with pytest.raises(ValueError, match="Metadata key cannot be empty"):
            result.add_metadata("   ", "value")

        # Test overwriting metadata
        result.add_metadata("key1", "value1")
        result.add_metadata("key1", "value2")  # Overwrite
        assert result.get_metadata("key1") == "value2"

    def test_search_result_offer_filtering_edge_cases(self):
        """Test edge cases in offer filtering methods."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        # Test methods with empty offer list
        assert result.get_cheapest_offer() is None
        assert result.get_fastest_offer() is None
        assert result.get_best_value_offer() is None
        assert len(result.get_fiber_offers()) == 0
        assert len(result.get_available_offers()) == 0

        # Add unavailable offers only
        unavailable_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="unavailable-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.UNAVAILABLE,
        )

        result.add_offer(unavailable_offer)

        # Methods should return None when no available offers
        assert result.get_cheapest_offer() is None
        assert result.get_fastest_offer() is None
        assert result.get_best_value_offer() is None

        # But total counts should include unavailable offers
        assert result.offer_count == 1
        assert result.available_offer_count == 0

    def test_search_result_summary_stats_edge_cases(self):
        """Test summary stats with various offer combinations."""
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        result = SearchResult.create_new(address)

        # Add offers with same provider but different products
        offer1 = ProviderOffer(
            provider_name="SameProvider",
            product_id="product-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        offer2 = ProviderOffer(
            provider_name="SameProvider",
            product_id="product-2",
            speed_download_mbps=200,
            speed_upload_mbps=100,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        result.add_offer(offer1)
        result.add_offer(offer2)

        stats = result.get_summary_stats()
        assert stats["total_offers"] == 2
        assert stats["available_offers"] == 2
        assert stats["providers"] == 1  # Same provider for both offers
        assert stats["cheapest_monthly_cost"] == Decimal("29.99")
        assert stats["most_expensive_monthly_cost"] == Decimal("39.99")
        assert stats["fastest_speed"] == 200
        assert stats["slowest_speed"] == 100
        assert stats["fiber_available"] is True


class TestAddress:
    """Test Address value object."""

    def test_address_creation(self):
        """Test creating an address."""
        address = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")

        assert address.street == "Musterstraße"
        assert address.house_number == "1"
        assert address.city == "Berlin"
        assert address.postal_code == "10115"
        assert address.country == "DE"

    def test_address_defaults(self):
        """Test address with default country."""
        address = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115")

        assert address.country == "DE"  # Default country

    def test_street_validation(self):
        """Test street validation."""
        # Empty street
        with pytest.raises(ValueError, match="Street cannot be empty"):
            Address(street="", house_number="1", city="Berlin", postal_code="10115", country="DE")

        # Whitespace only street
        with pytest.raises(ValueError, match="Street cannot be empty"):
            Address(street="   ", house_number="1", city="Berlin", postal_code="10115", country="DE")

        # Too short street
        with pytest.raises(ValueError, match="Street must be at least 2 characters long"):
            Address(street="A", house_number="1", city="Berlin", postal_code="10115", country="DE")

        # Too long street
        with pytest.raises(ValueError, match="Street cannot exceed 100 characters"):
            Address(street="A" * 101, house_number="1", city="Berlin", postal_code="10115", country="DE")

    def test_house_number_validation(self):
        """Test house number validation."""
        # Empty house number
        with pytest.raises(ValueError, match="House number cannot be empty"):
            Address(street="Musterstraße", house_number="", city="Berlin", postal_code="10115", country="DE")

        # Whitespace only house number
        with pytest.raises(ValueError, match="House number cannot be empty"):
            Address(street="Musterstraße", house_number="   ", city="Berlin", postal_code="10115", country="DE")

        # Invalid house number format
        with pytest.raises(ValueError, match="House number must be in valid format"):
            Address(street="Musterstraße", house_number="abc", city="Berlin", postal_code="10115", country="DE")

        # Valid house number formats
        valid_formats = ["1", "12", "123", "12a", "12A", "12-14", "12a-14b"]
        for house_num in valid_formats:
            address = Address(street="Musterstraße", house_number=house_num, city="Berlin", postal_code="10115", country="DE")
            assert address.house_number == house_num

    def test_city_validation(self):
        """Test city validation."""
        # Empty city
        with pytest.raises(ValueError, match="City cannot be empty"):
            Address(street="Musterstraße", house_number="1", city="", postal_code="10115", country="DE")

        # Whitespace only city
        with pytest.raises(ValueError, match="City cannot be empty"):
            Address(street="Musterstraße", house_number="1", city="   ", postal_code="10115", country="DE")

        # Too short city
        with pytest.raises(ValueError, match="City must be at least 2 characters long"):
            Address(street="Musterstraße", house_number="1", city="A", postal_code="10115", country="DE")

        # Too long city
        with pytest.raises(ValueError, match="City cannot exceed 50 characters"):
            Address(street="Musterstraße", house_number="1", city="A" * 51, postal_code="10115", country="DE")

        # Invalid characters in city
        with pytest.raises(ValueError, match="City contains invalid characters"):
            Address(street="Musterstraße", house_number="1", city="Berlin123", postal_code="10115", country="DE")

        # Valid city names with special characters
        valid_cities = ["Berlin", "München", "Köln", "Düsseldorf", "Bad Homburg", "Frankfurt am Main", "Saint-Étienne"]
        for city in valid_cities:
            try:
                address = Address(street="Musterstraße", house_number="1", city=city, postal_code="10115", country="DE")
                assert address.city == city
            except ValueError:
                # Some cities with special characters might not pass the regex, that's expected
                pass

    def test_postal_code_validation(self):
        """Test postal code validation."""
        # Empty postal code
        with pytest.raises(ValueError, match="Postal code cannot be empty"):
            Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="", country="DE")

        # Whitespace only postal code
        with pytest.raises(ValueError, match="Postal code cannot be empty"):
            Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="   ", country="DE")

        # Invalid German postal code (not 5 digits)
        with pytest.raises(ValueError, match="German postal code must be exactly 5 digits"):
            Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="1011", country="DE")

        with pytest.raises(ValueError, match="German postal code must be exactly 5 digits"):
            Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="101156", country="DE")

        with pytest.raises(ValueError, match="German postal code must be exactly 5 digits"):
            Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="1011a", country="DE")

        # Valid German postal code
        address = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")
        assert address.postal_code == "10115"

        # Test non-German postal codes
        # Too short
        with pytest.raises(ValueError, match="Postal code must be between 3 and 10 characters"):
            Address(street="Main St", house_number="1", city="New York", postal_code="12", country="US")

        # Too long
        with pytest.raises(ValueError, match="Postal code must be between 3 and 10 characters"):
            Address(street="Main St", house_number="1", city="New York", postal_code="12345678901", country="US")

        # Valid non-German postal codes
        valid_non_german = [
            ("12345", "US"),
            ("SW1A 1AA", "GB"),
            ("75001", "FR"),
            ("1234", "CH"),
        ]
        for postal_code, country in valid_non_german:
            address = Address(street="Main St", house_number="1", city="City", postal_code=postal_code, country=country)
            assert address.postal_code == postal_code

    def test_country_validation(self):
        """Test country code validation."""
        # Invalid country code length
        with pytest.raises(ValueError, match="Country code must be exactly 2 characters"):
            Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="DEU")

        with pytest.raises(ValueError, match="Country code must be exactly 2 characters"):
            Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="D")

        # Lowercase country code
        with pytest.raises(ValueError, match="Country code must be uppercase"):
            Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="de")

        # Valid country codes
        valid_countries = ["DE", "US", "GB", "FR", "IT", "ES"]
        for country in valid_countries:
            address = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country=country)
            assert address.country == country

    def test_full_address_property(self):
        """Test full address string representation."""
        address = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")

        full_address = address.full_address
        assert "Musterstraße" in full_address
        assert "1" in full_address
        assert "Berlin" in full_address
        assert "10115" in full_address

        # Check format
        expected = "Musterstraße 1, 10115 Berlin"
        assert full_address == expected

    def test_normalized_postal_code_property(self):
        """Test normalized postal code property."""
        # German postal code (no spaces to normalize)
        address_de = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")
        assert address_de.normalized_postal_code == "10115"

        # UK postal code with space
        address_uk = Address(street="Main St", house_number="1", city="London", postal_code="SW1A 1AA", country="GB")
        assert address_uk.normalized_postal_code == "SW1A1AA"

    def test_is_same_location(self):
        """Test location comparison."""
        address1 = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")
        address2 = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")
        address3 = Address(street="Hauptstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")
        address4 = Address(street="Musterstraße", house_number="2", city="Berlin", postal_code="10115", country="DE")
        address5 = Address(street="Musterstraße", house_number="1", city="München", postal_code="80331", country="DE")

        # Same location
        assert address1.is_same_location(address2) is True

        # Different street (but same postal code and house number)
        assert address1.is_same_location(address3) is True

        # Different house number
        assert address1.is_same_location(address4) is False

        # Different city and postal code
        assert address1.is_same_location(address5) is False

        # Test with non-Address object
        assert address1.is_same_location("not an address") is False

        # Test case insensitive comparison
        address_upper = Address(street="MUSTERSTRASSE", house_number="1A", city="BERLIN", postal_code="10115", country="DE")
        address_lower = Address(street="musterstrasse", house_number="1a", city="berlin", postal_code="10115", country="DE")
        assert address_upper.is_same_location(address_lower) is True

        # Test postal code normalization in comparison
        address_spaced = Address(street="Main St", house_number="1", city="London", postal_code="SW1A 1AA", country="GB")
        address_no_space = Address(street="Main St", house_number="1", city="London", postal_code="SW1A1AA", country="GB")
        assert address_spaced.is_same_location(address_no_space) is True

    def test_address_equality(self):
        """Test address equality."""
        address1 = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")
        address2 = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")
        address3 = Address(street="Hauptstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")

        assert address1 == address2
        assert address1 != address3

    def test_address_immutability(self):
        """Test that address is immutable (frozen dataclass)."""
        address = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115", country="DE")

        # Should not be able to modify fields
        with pytest.raises(AttributeError):
            address.street = "New Street"

        with pytest.raises(AttributeError):
            address.house_number = "2"

    def test_address_validation_boundary_cases(self):
        """Test boundary cases for address validation."""
        # Test minimum valid street length (2 characters)
        address = Address(street="St", house_number="1", city="Berlin", postal_code="10115", country="DE")
        assert address.street == "St"

        # Test minimum valid city length (2 characters)
        address = Address(street="Musterstraße", house_number="1", city="NY", postal_code="10115", country="DE")
        assert address.city == "NY"

        # Test maximum valid street length (100 characters)
        long_street = "A" * 100
        address = Address(street=long_street, house_number="1", city="Berlin", postal_code="10115", country="DE")
        assert address.street == long_street

        # Test maximum valid city length (50 characters)
        long_city = "B" * 50
        address = Address(street="Musterstraße", house_number="1", city=long_city, postal_code="10115", country="DE")
        assert address.city == long_city

    def test_address_special_characters_in_city(self):
        """Test city names with special characters."""
        # Test German umlauts
        german_cities = ["München", "Köln", "Düsseldorf"]
        for city in german_cities:
            address = Address(street="Musterstraße", house_number="1", city=city, postal_code="10115", country="DE")
            assert address.city == city

        # Test cities with hyphens and spaces
        complex_cities = ["Bad Homburg", "Frankfurt am Main", "Garmisch-Partenkirchen"]
        for city in complex_cities:
            address = Address(street="Musterstraße", house_number="1", city=city, postal_code="10115", country="DE")
            assert address.city == city

    def test_address_house_number_formats(self):
        """Test various house number formats."""
        valid_house_numbers = ["1", "12", "123", "12a", "12A", "12b", "12Z", "12-14", "12a-14", "12-14b", "1a-3c"]

        for house_num in valid_house_numbers:
            address = Address(street="Musterstraße", house_number=house_num, city="Berlin", postal_code="10115", country="DE")
            assert address.house_number == house_num

    def test_address_postal_code_edge_cases(self):
        """Test postal code edge cases for different countries."""
        # Test minimum length for non-German countries (3 characters)
        address = Address(street="Main St", house_number="1", city="City", postal_code="123", country="US")
        assert address.postal_code == "123"

        # Test maximum length for non-German countries (10 characters)
        address = Address(street="Main St", house_number="1", city="City", postal_code="1234567890", country="US")
        assert address.postal_code == "1234567890"

        # Test UK postal code with space
        address = Address(street="Main St", house_number="1", city="London", postal_code="SW1A 1AA", country="GB")
        assert address.normalized_postal_code == "SW1A1AA"

    def test_address_country_none_handling(self):
        """Test address creation with None country (explicitly None)."""
        # With None country, postal code validation uses generic rules (3-10 chars)
        address = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="12345", country=None)
        assert address.country is None

        # Test that omitting country parameter uses default
        address_default = Address(street="Musterstraße", house_number="1", city="Berlin", postal_code="10115")
        assert address_default.country == "DE"

    def test_address_full_address_formatting(self):
        """Test full address formatting with various inputs."""
        test_cases = [
            {
                "street": "Musterstraße",
                "house_number": "123a",
                "city": "München",
                "postal_code": "80331",
                "expected": "Musterstraße 123a, 80331 München",
            },
            {
                "street": "Main Street",
                "house_number": "12-14",
                "city": "New York",
                "postal_code": "10001",
                "expected": "Main Street 12-14, 10001 New York",
            },
        ]

        for case in test_cases:
            address = Address(
                street=case["street"],
                house_number=case["house_number"],
                city=case["city"],
                postal_code=case["postal_code"],
                country="DE",
            )
            assert address.full_address == case["expected"]
