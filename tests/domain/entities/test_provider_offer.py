"""Tests for ProviderOffer entity."""

import pytest
from decimal import Decimal
from src.domain.entities.provider_offer import ProviderOffer, ConnectionType, OfferStatus


class TestProviderOffer:
    """Test cases for ProviderOffer entity."""
    
    def test_valid_offer_creation(self):
        """Test creating a valid provider offer."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            setup_fee_euros=Decimal("49.99")
        )
        
        assert offer.provider_name == "TestProvider"
        assert offer.product_id == "TEST-001"
        assert offer.speed_download_mbps == 100
        assert offer.speed_upload_mbps == 50
        assert offer.monthly_cost_euros == Decimal("29.99")
        assert offer.connection_type == ConnectionType.FIBER
        assert offer.contract_duration_months == 24
        assert offer.setup_fee_euros == Decimal("49.99")
        assert offer.status == OfferStatus.AVAILABLE  # Default
        assert offer.additional_features == {}  # Default empty dict
    
    def test_offer_with_defaults(self):
        """Test offer creation with default values."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12
        )
        
        assert offer.setup_fee_euros is None
        assert offer.status == OfferStatus.AVAILABLE
        assert offer.additional_features == {}
    
    def test_total_first_year_cost(self):
        """Test total first year cost calculation."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("30.00"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            setup_fee_euros=Decimal("50.00")
        )
        
        expected_cost = Decimal("30.00") * 12 + Decimal("50.00")  # 360 + 50 = 410
        assert offer.total_first_year_cost == expected_cost
    
    def test_total_first_year_cost_without_setup_fee(self):
        """Test total first year cost without setup fee."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("30.00"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        expected_cost = Decimal("30.00") * 12  # 360
        assert offer.total_first_year_cost == expected_cost
    
    def test_speed_ratio(self):
        """Test speed ratio calculation."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        assert offer.speed_ratio == 0.5  # 50/100
    
    def test_speed_ratio_zero_download(self):
        """Test speed ratio with zero download speed."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=1,  # Will be validated as positive
            speed_upload_mbps=0,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        assert offer.speed_ratio == 0.0
    
    def test_is_fiber_property(self):
        """Test is_fiber property."""
        fiber_offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        dsl_offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-002",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=24
        )
        
        assert fiber_offer.is_fiber is True
        assert dsl_offer.is_fiber is False
    
    def test_is_available_property(self):
        """Test is_available property."""
        available_offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.AVAILABLE
        )
        
        unavailable_offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-002",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.UNAVAILABLE
        )
        
        assert available_offer.is_available is True
        assert unavailable_offer.is_available is False
    
    def test_calculate_monthly_cost_per_mbps(self):
        """Test monthly cost per Mbps calculation."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("30.00"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        expected_cost_per_mbps = Decimal("30.00") / 100  # 0.30
        assert offer.calculate_monthly_cost_per_mbps() == expected_cost_per_mbps
    
    def test_calculate_monthly_cost_per_mbps_zero_speed(self):
        """Test monthly cost per Mbps with zero speed (should not happen due to validation)."""
        # This test verifies the method behavior, though validation prevents zero speed
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=1,  # Minimum valid speed
            speed_upload_mbps=0,
            monthly_cost_euros=Decimal("30.00"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        # Manually set speed to 0 to test the method (bypassing validation)
        offer.speed_download_mbps = 0
        assert offer.calculate_monthly_cost_per_mbps() == Decimal('0')
    
    def test_is_better_value_than(self):
        """Test value comparison between offers."""
        offer1 = ProviderOffer(
            provider_name="Provider1",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("30.00"),  # 0.30 per Mbps
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        offer2 = ProviderOffer(
            provider_name="Provider2",
            product_id="TEST-002",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("40.00"),  # 0.40 per Mbps
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        assert offer1.is_better_value_than(offer2) is True
        assert offer2.is_better_value_than(offer1) is False
    
    def test_add_feature(self):
        """Test adding additional features."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        offer.add_feature("wifi_included", True)
        offer.add_feature("tv_channels", 50)
        
        assert offer.additional_features["wifi_included"] is True
        assert offer.additional_features["tv_channels"] == 50
    
    def test_has_feature(self):
        """Test checking for feature existence."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        offer.add_feature("wifi_included", True)
        
        assert offer.has_feature("wifi_included") is True
        assert offer.has_feature("tv_channels") is False
    
    def test_get_feature(self):
        """Test getting feature values."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        offer.add_feature("wifi_included", True)
        
        assert offer.get_feature("wifi_included") is True
        assert offer.get_feature("tv_channels") is None
        assert offer.get_feature("tv_channels", 0) == 0  # With default
    
    # Validation tests
    def test_empty_provider_name_validation(self):
        """Test validation of empty provider name."""
        with pytest.raises(ValueError, match="Provider name cannot be empty"):
            ProviderOffer(
                provider_name="",
                product_id="TEST-001",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
    
    def test_long_provider_name_validation(self):
        """Test validation of too long provider name."""
        long_name = "A" * 51
        with pytest.raises(ValueError, match="Provider name cannot exceed 50 characters"):
            ProviderOffer(
                provider_name=long_name,
                product_id="TEST-001",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
    
    def test_empty_product_id_validation(self):
        """Test validation of empty product ID."""
        with pytest.raises(ValueError, match="Product ID cannot be empty"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
    
    def test_negative_download_speed_validation(self):
        """Test validation of negative download speed."""
        with pytest.raises(ValueError, match="Download speed must be positive"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=-1,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
    
    def test_zero_download_speed_validation(self):
        """Test validation of zero download speed."""
        with pytest.raises(ValueError, match="Download speed must be positive"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=0,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
    
    def test_negative_upload_speed_validation(self):
        """Test validation of negative upload speed."""
        with pytest.raises(ValueError, match="Upload speed cannot be negative"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=100,
                speed_upload_mbps=-1,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
    
    def test_unrealistic_download_speed_validation(self):
        """Test validation of unrealistic download speed."""
        with pytest.raises(ValueError, match="Download speed seems unrealistic"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=15000,  # > 10Gbps
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
    
    def test_upload_exceeds_download_validation(self):
        """Test validation when upload speed exceeds download speed."""
        with pytest.raises(ValueError, match="Upload speed cannot exceed download speed"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=50,
                speed_upload_mbps=100,  # Higher than download
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
    
    def test_negative_monthly_cost_validation(self):
        """Test validation of negative monthly cost."""
        with pytest.raises(ValueError, match="Monthly cost cannot be negative"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("-10.00"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
    
    def test_unrealistic_monthly_cost_validation(self):
        """Test validation of unrealistic monthly cost."""
        with pytest.raises(ValueError, match="Monthly cost seems unrealistic"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("1500.00"),  # > 1000 EUR
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24
            )
    
    def test_negative_setup_fee_validation(self):
        """Test validation of negative setup fee."""
        with pytest.raises(ValueError, match="Setup fee cannot be negative"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
                setup_fee_euros=Decimal("-50.00")
            )
    
    def test_unrealistic_setup_fee_validation(self):
        """Test validation of unrealistic setup fee."""
        with pytest.raises(ValueError, match="Setup fee seems unrealistic"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=24,
                setup_fee_euros=Decimal("600.00")  # > 500 EUR
            )
    
    def test_negative_contract_duration_validation(self):
        """Test validation of negative contract duration."""
        with pytest.raises(ValueError, match="Contract duration cannot be negative"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=-1
            )
    
    def test_unrealistic_contract_duration_validation(self):
        """Test validation of unrealistic contract duration."""
        with pytest.raises(ValueError, match="Contract duration seems unrealistic"):
            ProviderOffer(
                provider_name="TestProvider",
                product_id="TEST-001",
                speed_download_mbps=100,
                speed_upload_mbps=50,
                monthly_cost_euros=Decimal("29.99"),
                connection_type=ConnectionType.FIBER,
                contract_duration_months=72  # > 60 months (5 years)
            )
    
    def test_empty_feature_name_validation(self):
        """Test validation of empty feature name."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        with pytest.raises(ValueError, match="Feature name cannot be empty"):
            offer.add_feature("", "value")