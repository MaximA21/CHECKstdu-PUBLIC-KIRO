"""Tests for domain services."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from src.domain.entities.search_result import SearchResult
from src.domain.entities.provider_offer import ProviderOffer, ConnectionType, OfferStatus
from src.domain.entities.connection_session import ConnectionSession, SessionConnectionType
from src.domain.value_objects.address import Address


class TestSearchResultDomainLogic:
    """Test domain logic within SearchResult entity."""
    
    @pytest.fixture
    def sample_address(self):
        """Create a sample address for testing."""
        return Address(
            street="Domainstraße",
            house_number="42",
            city="München",
            postal_code="80331",
            country="DE"
        )
    
    @pytest.fixture
    def fiber_offers(self):
        """Create sample fiber offers."""
        return [
            ProviderOffer(
                provider_name="FiberProvider1",
                product_id="FIBER-100",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("39.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            ),
            ProviderOffer(
                provider_name="FiberProvider2",
                product_id="FIBER-200",
                speed_download_mbps=200,
                speed_upload_mbps=100,
                monthly_cost_euros=Decimal("59.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
        ]
    
    @pytest.fixture
    def dsl_offers(self):
        """Create sample DSL offers."""
        return [
            ProviderOffer(
                provider_name="DSLProvider1",
                product_id="DSL-50",
                speed_download_mbps=50,
                speed_upload_mbps=10,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.DSL,
                contract_duration_months=12
            ),
            ProviderOffer(
                provider_name="DSLProvider2",
                product_id="DSL-25",
                speed_download_mbps=25,
                speed_upload_mbps=5,
                monthly_cost_euros=Decimal("19.99"),
                connection_type=ConnectionType.DSL,
                contract_duration_months=12
            )
        ]
    
    def test_offer_comparison_logic(self, sample_address, fiber_offers, dsl_offers):
        """Test offer comparison and ranking logic."""
        search_result = SearchResult.create_new(sample_address)
        
        # Add all offers
        for offer in fiber_offers + dsl_offers:
            search_result.add_offer(offer)
        
        # Test cheapest offer logic
        cheapest = search_result.get_cheapest_offer()
        assert cheapest.monthly_cost_euros == Decimal("19.99")
        assert cheapest.provider_name == "DSLProvider2"
        
        # Test fastest offer logic
        fastest = search_result.get_fastest_offer()
        assert fastest.speed_download_mbps == 200
        assert fastest.provider_name == "FiberProvider2"
        
        # Test best value logic (cost per Mbps)
        best_value = search_result.get_best_value_offer()
        # DSL-25: 19.99/25 = 0.7996 EUR/Mbps
        # DSL-50: 29.99/50 = 0.5998 EUR/Mbps
        # FIBER-100: 39.99/100 = 0.3999 EUR/Mbps (best value)
        # FIBER-200: 59.99/200 = 0.29995 EUR/Mbps (even better value)
        assert best_value.provider_name == "FiberProvider2"
        assert best_value.product_id == "FIBER-200"
    
    def test_offer_filtering_logic(self, sample_address, fiber_offers, dsl_offers):
        """Test offer filtering by various criteria."""
        search_result = SearchResult.create_new(sample_address)
        
        # Add offers with different statuses
        available_offer = fiber_offers[0]
        unavailable_offer = dsl_offers[0]
        unavailable_offer.status = OfferStatus.UNAVAILABLE
        
        search_result.add_offer(available_offer)
        search_result.add_offer(unavailable_offer)
        search_result.add_offer(fiber_offers[1])
        
        # Test available offers filtering
        available_offers = search_result.get_available_offers()
        assert len(available_offers) == 2
        assert all(offer.status == OfferStatus.AVAILABLE for offer in available_offers)
        
        # Test fiber offers filtering
        fiber_offers_result = search_result.get_fiber_offers()
        assert len(fiber_offers_result) == 2
        assert all(offer.connection_type == ConnectionType.FIBER for offer in fiber_offers_result)
        
        # Test provider filtering
        provider1_offers = search_result.get_offers_by_provider("FiberProvider1")
        assert len(provider1_offers) == 1
        assert provider1_offers[0].provider_name == "FiberProvider1"
    
    def test_search_result_statistics(self, sample_address, fiber_offers, dsl_offers):
        """Test search result statistics calculation."""
        search_result = SearchResult.create_new(sample_address)
        
        # Add offers
        for offer in fiber_offers + dsl_offers:
            search_result.add_offer(offer)
        
        # Test summary statistics
        stats = search_result.get_summary_stats()
        
        assert stats["total_offers"] == 4
        assert stats["available_offers"] == 4
        assert stats["providers"] == 4
        assert stats["cheapest_monthly_cost"] == Decimal("19.99")
        assert stats["most_expensive_monthly_cost"] == Decimal("59.99")
        assert stats["fastest_speed"] == 200
        assert stats["slowest_speed"] == 25
        assert stats["fiber_available"] is True
        assert "Fiber" in stats["connection_types"]
        assert "DSL" in stats["connection_types"]
    
    def test_search_result_expiration_logic(self, sample_address):
        """Test search result expiration logic."""
        search_result = SearchResult.create_new(sample_address)
        
        # Test initial expiration (should be in future)
        assert not search_result.is_expired
        assert search_result.days_until_expiration > 0
        
        # Test extending expiration
        original_expiration = search_result.expires_at
        search_result.extend_expiration(7)
        
        expected_expiration = original_expiration + timedelta(days=7)
        assert search_result.expires_at == expected_expiration
        
        # Test expiration calculation
        days_until = search_result.days_until_expiration
        assert days_until > 7  # Should be more than 7 days now
    
    def test_search_result_metadata_management(self, sample_address):
        """Test search result metadata management."""
        search_result = SearchResult.create_new(sample_address)
        
        # Test adding metadata
        search_result.add_metadata("search_source", "web_app")
        search_result.add_metadata("user_agent", "Mozilla/5.0")
        search_result.add_metadata("session_id", "sess_123")
        
        # Test retrieving metadata
        assert search_result.get_metadata("search_source") == "web_app"
        assert search_result.get_metadata("user_agent") == "Mozilla/5.0"
        assert search_result.get_metadata("session_id") == "sess_123"
        assert search_result.get_metadata("nonexistent") is None
        assert search_result.get_metadata("nonexistent", "default") == "default"
        
        # Test metadata in search metadata dict
        assert "search_source" in search_result.search_metadata
        assert "user_agent" in search_result.search_metadata
        assert "session_id" in search_result.search_metadata


class TestConnectionSessionDomainLogic:
    """Test domain logic within ConnectionSession entity."""
    
    def test_connection_lifecycle_management(self):
        """Test connection lifecycle state management."""
        session = ConnectionSession.create_new("test-conn-lifecycle")
        
        # Test initial state
        assert not session.is_connected
        assert not session.is_disconnected
        assert session.status.value == "Connecting"
        
        # Test connection
        session.connect()
        assert session.is_connected
        assert not session.is_disconnected
        assert session.status.value == "Connected"
        assert session.connected_at is not None
        
        # Test activity updates
        original_activity = session.last_activity_at
        session.update_activity()
        assert session.last_activity_at > original_activity
        
        # Test disconnection
        session.disconnect("Normal closure")
        assert not session.is_connected
        assert session.is_disconnected
        assert session.get_session_data("disconnect_reason") == "Normal closure"
        assert session.disconnected_at is not None
    
    def test_connection_timeout_logic(self):
        """Test connection timeout logic."""
        session = ConnectionSession.create_new("test-conn-timeout")
        session.connect()
        
        # Test idle duration calculation
        idle_duration = session.idle_duration
        assert idle_duration is not None
        assert idle_duration.total_seconds() >= 0
        
        # Test idle check
        assert not session.is_idle_for(60)  # Not idle for 1 hour (60 minutes)
        assert session.is_idle_for(0)  # Idle for 0 minutes
        
        # Test timeout check
        assert not session.should_timeout(60)  # Should not timeout with 1 hour limit
        assert session.should_timeout(0)  # Should timeout with 0 minute limit
    
    def test_connection_client_info_management(self):
        """Test client information management."""
        session = ConnectionSession.create_new("test-conn-client")
        
        # Test adding client info
        session.add_client_info("user_agent", "Mozilla/5.0")
        session.add_client_info("ip_address", "192.168.1.1")
        session.add_client_info("platform", "web")
        
        # Test retrieving client info
        assert session.get_client_info("user_agent") == "Mozilla/5.0"
        assert session.get_client_info("ip_address") == "192.168.1.1"
        assert session.get_client_info("platform") == "web"
        assert session.get_client_info("nonexistent") is None
        assert session.get_client_info("nonexistent", "default") == "default"
    
    def test_connection_session_data_management(self):
        """Test session data management."""
        session = ConnectionSession.create_new("test-conn-data")
        
        # Test adding session data
        session.add_session_data("current_search", "search_123")
        session.add_session_data("preferences", {"language": "de", "currency": "EUR"})
        session.add_session_data("last_action", "search_initiated")
        
        # Test retrieving session data
        assert session.get_session_data("current_search") == "search_123"
        assert session.get_session_data("preferences") == {"language": "de", "currency": "EUR"}
        assert session.get_session_data("last_action") == "search_initiated"
        assert session.get_session_data("nonexistent") is None
    
    def test_connection_topic_subscription(self):
        """Test topic subscription management."""
        session = ConnectionSession.create_new("test-conn-topics")
        
        # Test subscribing to topics
        session.subscribe_to_topic("search_updates")
        session.subscribe_to_topic("provider_notifications")
        session.subscribe_to_topic("system_alerts")
        
        # Test topic membership
        assert session.is_subscribed_to("search_updates")
        assert session.is_subscribed_to("provider_notifications")
        assert session.is_subscribed_to("system_alerts")
        assert not session.is_subscribed_to("nonexistent_topic")
        
        # Test getting subscribed topics
        topics = session.subscribed_topics
        assert "search_updates" in topics
        assert "provider_notifications" in topics
        assert "system_alerts" in topics
        assert len(topics) == 3
        
        # Test unsubscribing
        session.unsubscribe_from_topic("provider_notifications")
        assert not session.is_subscribed_to("provider_notifications")
        assert len(session.subscribed_topics) == 2
    
    def test_connection_summary_generation(self):
        """Test connection summary generation."""
        session = ConnectionSession.create_new("test-conn-summary", SessionConnectionType.WEBSOCKET)
        session.connect()
        
        # Add some data
        session.add_client_info("user_agent", "TestAgent/1.0")
        session.subscribe_to_topic("test_topic")
        session.add_session_data("test_key", "test_value")
        
        # Generate summary
        summary = session.get_connection_summary()
        
        assert summary["connection_id"] == "test-conn-summary"
        assert summary["connection_type"] == SessionConnectionType.WEBSOCKET.value
        assert summary["status"] == "Connected"
        assert "connected_at" in summary
        assert "connection_duration_seconds" in summary
        assert "idle_duration_seconds" in summary
        assert summary["subscribed_topics_count"] == 1
        assert summary["has_client_info"] is True
        assert summary["has_session_data"] is True


class TestProviderOfferDomainLogic:
    """Test domain logic within ProviderOffer entity."""
    
    def test_offer_value_calculations(self):
        """Test offer value calculation methods."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("39.99"),
            setup_fee_euros=Decimal("49.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        # Test total first year cost
        expected_first_year = (Decimal("39.99") * 12) + Decimal("49.99")
        assert offer.total_first_year_cost == expected_first_year
        
        # Test cost per Mbps
        expected_cost_per_mbps = Decimal("39.99") / 100
        assert offer.calculate_monthly_cost_per_mbps() == expected_cost_per_mbps
        
        # Test speed ratio
        expected_ratio = 50 / 100
        assert offer.speed_ratio == expected_ratio
    
    def test_offer_comparison_logic(self):
        """Test offer comparison methods."""
        offer1 = ProviderOffer(
            provider_name="Provider1",
            product_id="OFFER-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        offer2 = ProviderOffer(
            provider_name="Provider2",
            product_id="OFFER-002",
            speed_download_mbps=200,
            speed_upload_mbps=100,
            monthly_cost_euros=Decimal("59.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        # Test value comparison
        # offer1: 39.99/100 = 0.3999 EUR/Mbps
        # offer2: 59.99/200 = 0.29995 EUR/Mbps (better value)
        assert offer2.is_better_value_than(offer1)
        assert not offer1.is_better_value_than(offer2)
    
    def test_offer_feature_management(self):
        """Test offer feature management."""
        offer = ProviderOffer(
            provider_name="FeatureProvider",
            product_id="FEATURE-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        # Test adding features
        offer.add_feature("static_ip", True)
        offer.add_feature("ipv6_support", True)
        offer.add_feature("data_limit_gb", 1000)
        offer.add_feature("router_included", False)
        
        # Test feature queries
        assert offer.has_feature("static_ip")
        assert offer.has_feature("ipv6_support")
        assert offer.has_feature("data_limit_gb")
        assert offer.has_feature("router_included")
        assert not offer.has_feature("nonexistent_feature")
        
        # Test feature values
        assert offer.get_feature("static_ip") is True
        assert offer.get_feature("ipv6_support") is True
        assert offer.get_feature("data_limit_gb") == 1000
        assert offer.get_feature("router_included") is False
        assert offer.get_feature("nonexistent_feature") is None
        assert offer.get_feature("nonexistent_feature", "default") == "default"
    
    def test_offer_properties(self):
        """Test offer property methods."""
        fiber_offer = ProviderOffer(
            provider_name="FiberProvider",
            product_id="FIBER-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.AVAILABLE
        )
        
        dsl_offer = ProviderOffer(
            provider_name="DSLProvider",
            product_id="DSL-001",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
            status=OfferStatus.UNAVAILABLE
        )
        
        # Test fiber property
        assert fiber_offer.is_fiber
        assert not dsl_offer.is_fiber
        
        # Test availability property
        assert fiber_offer.is_available
        assert not dsl_offer.is_available


if __name__ == "__main__":
    pytest.main([__file__])