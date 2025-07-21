"""Provider offer entity representing internet service offers."""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from decimal import Decimal
from enum import Enum


class ConnectionType(Enum):
    """Enumeration of internet connection types."""
    DSL = "DSL"
    CABLE = "Cable"
    FIBER = "Fiber"
    SATELLITE = "Satellite"
    MOBILE = "Mobile"
    UNKNOWN = "Unknown"


class OfferStatus(Enum):
    """Enumeration of offer availability status."""
    AVAILABLE = "Available"
    LIMITED = "Limited"
    UNAVAILABLE = "Unavailable"
    PENDING = "Pending"


@dataclass
class ProviderOffer:
    """Entity representing an internet service provider offer."""
    
    provider_name: str
    product_id: str
    speed_download_mbps: int
    speed_upload_mbps: int
    monthly_cost_euros: Decimal
    connection_type: ConnectionType
    contract_duration_months: int
    setup_fee_euros: Optional[Decimal] = None
    status: OfferStatus = OfferStatus.AVAILABLE
    additional_features: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate offer data after initialization."""
        self._validate_provider_name()
        self._validate_product_id()
        self._validate_speeds()
        self._validate_costs()
        self._validate_contract_duration()
        
        # Ensure additional_features is not None
        if self.additional_features is None:
            object.__setattr__(self, 'additional_features', {})
    
    def _validate_provider_name(self) -> None:
        """Validate provider name."""
        if not self.provider_name or not self.provider_name.strip():
            raise ValueError("Provider name cannot be empty")
        if len(self.provider_name) > 50:
            raise ValueError("Provider name cannot exceed 50 characters")
    
    def _validate_product_id(self) -> None:
        """Validate product ID."""
        if not self.product_id or not self.product_id.strip():
            raise ValueError("Product ID cannot be empty")
        if len(self.product_id) > 100:
            raise ValueError("Product ID cannot exceed 100 characters")
    
    def _validate_speeds(self) -> None:
        """Validate internet speeds."""
        if self.speed_download_mbps <= 0:
            raise ValueError("Download speed must be positive")
        if self.speed_upload_mbps < 0:
            raise ValueError("Upload speed cannot be negative")
        if self.speed_download_mbps > 10000:
            raise ValueError("Download speed seems unrealistic (>10Gbps)")
        if self.speed_upload_mbps > self.speed_download_mbps:
            raise ValueError("Upload speed cannot exceed download speed")
    
    def _validate_costs(self) -> None:
        """Validate cost values."""
        if self.monthly_cost_euros < 0:
            raise ValueError("Monthly cost cannot be negative")
        if self.monthly_cost_euros > Decimal('1000'):
            raise ValueError("Monthly cost seems unrealistic (>1000 EUR)")
        
        if self.setup_fee_euros is not None:
            if self.setup_fee_euros < 0:
                raise ValueError("Setup fee cannot be negative")
            if self.setup_fee_euros > Decimal('500'):
                raise ValueError("Setup fee seems unrealistic (>500 EUR)")
    
    def _validate_contract_duration(self) -> None:
        """Validate contract duration."""
        if self.contract_duration_months < 0:
            raise ValueError("Contract duration cannot be negative")
        if self.contract_duration_months > 60:
            raise ValueError("Contract duration seems unrealistic (>5 years)")
    
    @property
    def total_first_year_cost(self) -> Decimal:
        """Calculate total cost for the first year including setup fee."""
        monthly_cost = self.monthly_cost_euros * 12
        setup_cost = self.setup_fee_euros or Decimal('0')
        return monthly_cost + setup_cost
    
    @property
    def speed_ratio(self) -> float:
        """Calculate upload to download speed ratio."""
        if self.speed_download_mbps == 0:
            return 0.0
        return self.speed_upload_mbps / self.speed_download_mbps
    
    @property
    def is_fiber(self) -> bool:
        """Check if this is a fiber connection."""
        return self.connection_type == ConnectionType.FIBER
    
    @property
    def is_available(self) -> bool:
        """Check if the offer is currently available."""
        return self.status == OfferStatus.AVAILABLE
    
    def calculate_monthly_cost_per_mbps(self) -> Decimal:
        """Calculate cost per Mbps of download speed."""
        if self.speed_download_mbps == 0:
            return Decimal('0')
        return self.monthly_cost_euros / self.speed_download_mbps
    
    def is_better_value_than(self, other: 'ProviderOffer') -> bool:
        """Compare value proposition with another offer."""
        if not isinstance(other, ProviderOffer):
            return False
        
        # Compare cost per Mbps
        self_cost_per_mbps = self.calculate_monthly_cost_per_mbps()
        other_cost_per_mbps = other.calculate_monthly_cost_per_mbps()
        
        return self_cost_per_mbps < other_cost_per_mbps
    
    def add_feature(self, feature_name: str, feature_value: Any) -> None:
        """Add an additional feature to the offer."""
        if not feature_name or not feature_name.strip():
            raise ValueError("Feature name cannot be empty")
        
        self.additional_features[feature_name] = feature_value
    
    def has_feature(self, feature_name: str) -> bool:
        """Check if the offer has a specific feature."""
        return feature_name in self.additional_features
    
    def get_feature(self, feature_name: str, default: Any = None) -> Any:
        """Get the value of a specific feature."""
        return self.additional_features.get(feature_name, default)