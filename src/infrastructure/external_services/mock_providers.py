"""Mock provider service implementations for testing purposes."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import random
from decimal import Decimal
from copy import deepcopy

from ...application.interfaces.providers import (
    IProviderService, 
    IByteMe, 
    IVerbynDich, 
    IWebWunder, 
    IPingPerfect,
    IProviderRegistry,
    IProviderAggregator,
    ProviderStatus, 
    ProviderType
)
from ...domain.entities.provider_offer import ProviderOffer, ConnectionType, OfferStatus
from ...domain.value_objects.address import Address


class MockProviderService(IProviderService):
    """Base mock provider service implementation."""
    
    def __init__(self, provider_name: str, provider_type: ProviderType = ProviderType.API_BASED,
                 supported_regions: Optional[List[str]] = None, 
                 status: ProviderStatus = ProviderStatus.AVAILABLE):
        """Initialize mock provider."""
        self._provider_name = provider_name
        self._provider_type = provider_type
        self._supported_regions = supported_regions or ["DE", "AT", "CH"]
        self._status = status
        self._rate_limit_remaining = 1000
        self._rate_limit_reset_time = datetime.utcnow()
        self._call_count = 0
    
    async def get_offers(self, address: Address) -> List[ProviderOffer]:
        """Get mock internet offers for a specific address."""
        self._call_count += 1
        
        if self._status != ProviderStatus.AVAILABLE:
            if self._status == ProviderStatus.RATE_LIMITED:
                raise Exception(f"Rate limited for provider {self._provider_name}")
            else:
                raise Exception(f"Provider {self._provider_name} is {self._status.value}")
        
        if not await self.validate_address(address):
            return []
        
        # Generate mock offers
        offers = []
        num_offers = random.randint(1, 4)
        
        for i in range(num_offers):
            download_speed = random.choice([25, 50, 100, 250, 500, 1000])
            # Ensure upload speed doesn't exceed download speed
            max_upload = min(download_speed, 100)
            upload_speed = random.choice([speed for speed in [5, 10, 25, 50, 100] if speed <= max_upload])
            
            offer = ProviderOffer(
                provider_name=self._provider_name,
                product_id=f"{self._provider_name.lower()}_product_{i+1}",
                speed_download_mbps=download_speed,
                speed_upload_mbps=upload_speed,
                monthly_cost_euros=Decimal(str(random.uniform(19.99, 89.99))).quantize(Decimal('0.01')),
                connection_type=random.choice(list(ConnectionType)),
                contract_duration_months=random.choice([0, 12, 24]),
                setup_fee_euros=Decimal(str(random.uniform(0, 99.99))).quantize(Decimal('0.01')) if random.random() > 0.5 else None,
                status=OfferStatus.AVAILABLE
            )
            
            # Add some mock features
            offer.add_feature("installation_included", random.choice([True, False]))
            offer.add_feature("router_included", random.choice([True, False]))
            offer.add_feature("tv_package_available", random.choice([True, False]))
            
            offers.append(offer)
        
        # Simulate rate limiting
        self._rate_limit_remaining -= 1
        if self._rate_limit_remaining <= 0:
            self._status = ProviderStatus.RATE_LIMITED
        
        return offers
    
    async def validate_address(self, address: Address) -> bool:
        """Validate if an address is supported by this provider."""
        if address.country not in self._supported_regions:
            return False
        
        # Mock validation - reject some postal codes
        if address.postal_code.startswith("00"):
            return False
        
        return True
    
    async def get_provider_status(self) -> ProviderStatus:
        """Get current status of the provider service."""
        return self._status
    
    @property
    def provider_name(self) -> str:
        """Get the name of the provider."""
        return self._provider_name
    
    @property
    def provider_type(self) -> ProviderType:
        """Get the type of the provider."""
        return self._provider_type
    
    @property
    def supported_regions(self) -> List[str]:
        """Get list of supported regions/countries."""
        return self._supported_regions.copy()
    
    async def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get rate limiting information for this provider."""
        return {
            "remaining_requests": self._rate_limit_remaining,
            "reset_time": self._rate_limit_reset_time.isoformat(),
            "total_calls": self._call_count
        }
    
    # Mock-specific methods
    
    def set_status(self, status: ProviderStatus) -> None:
        """Set provider status (for testing)."""
        self._status = status
    
    def reset_rate_limit(self) -> None:
        """Reset rate limit (for testing)."""
        self._rate_limit_remaining = 1000
        self._status = ProviderStatus.AVAILABLE


class MockByteMe(MockProviderService, IByteMe):
    """Mock implementation of ByteMe provider service."""
    
    def __init__(self):
        """Initialize ByteMe mock provider."""
        super().__init__("ByteMe", ProviderType.CSV_BASED)
    
    async def parse_csv_data(self, csv_content: str) -> List[ProviderOffer]:
        """Parse mock CSV data from ByteMe provider."""
        offers = []
        lines = csv_content.strip().split('\n')
        
        # Skip header if present
        if lines and 'speed' in lines[0].lower():
            lines = lines[1:]
        
        for line in lines:
            if not line.strip():
                continue
            
            parts = line.split(',')
            if len(parts) >= 4:
                try:
                    offer = ProviderOffer(
                        provider_name=self.provider_name,
                        product_id=f"byteme_{parts[0].strip()}",
                        speed_download_mbps=int(parts[1].strip()),
                        speed_upload_mbps=int(parts[2].strip()),
                        monthly_cost_euros=Decimal(parts[3].strip()),
                        connection_type=ConnectionType.DSL,
                        contract_duration_months=12
                    )
                    offers.append(offer)
                except (ValueError, IndexError):
                    continue
        
        return offers
    
    async def get_csv_data_for_address(self, address: Address) -> str:
        """Get mock CSV data for a specific address."""
        # Generate mock CSV data
        csv_data = "product_id,download_speed,upload_speed,monthly_cost\n"
        csv_data += "dsl_basic,25,5,29.99\n"
        csv_data += "dsl_premium,50,10,39.99\n"
        csv_data += "dsl_ultra,100,25,49.99\n"
        
        return csv_data


class MockVerbynDich(MockProviderService, IVerbynDich):
    """Mock implementation of VerbynDich provider service."""
    
    def __init__(self):
        """Initialize VerbynDich mock provider."""
        super().__init__("VerbynDich", ProviderType.API_BASED)
    
    async def parse_nested_array_data(self, json_data: Dict[str, Any]) -> List[ProviderOffer]:
        """Parse mock nested array data from VerbynDich provider."""
        offers = []
        
        # Navigate nested structure
        products = json_data.get("data", {}).get("products", [])
        
        for product in products:
            if not isinstance(product, dict):
                continue
            
            try:
                offer = ProviderOffer(
                    provider_name=self.provider_name,
                    product_id=f"verbyndich_{product.get('id', 'unknown')}",
                    speed_download_mbps=product.get("speeds", {}).get("download", 0),
                    speed_upload_mbps=product.get("speeds", {}).get("upload", 0),
                    monthly_cost_euros=Decimal(str(product.get("pricing", {}).get("monthly", 0))),
                    connection_type=ConnectionType.CABLE,
                    contract_duration_months=product.get("contract", {}).get("duration", 24)
                )
                offers.append(offer)
            except (ValueError, KeyError):
                continue
        
        return offers
    
    async def get_api_data_for_address(self, address: Address) -> Dict[str, Any]:
        """Get mock API data for a specific address."""
        return {
            "data": {
                "products": [
                    {
                        "id": "cable_basic",
                        "speeds": {"download": 100, "upload": 10},
                        "pricing": {"monthly": 34.99},
                        "contract": {"duration": 12}
                    },
                    {
                        "id": "cable_premium",
                        "speeds": {"download": 250, "upload": 25},
                        "pricing": {"monthly": 44.99},
                        "contract": {"duration": 24}
                    }
                ]
            }
        }


class MockWebWunder(MockProviderService, IWebWunder):
    """Mock implementation of WebWunder provider service."""
    
    def __init__(self):
        """Initialize WebWunder mock provider."""
        super().__init__("WebWunder", ProviderType.HYBRID)
    
    async def get_offers_with_metadata(self, address: Address) -> Dict[str, Any]:
        """Get mock offers with additional metadata from WebWunder."""
        offers = await self.get_offers(address)
        
        return {
            "offers": [
                {
                    "provider_name": offer.provider_name,
                    "product_id": offer.product_id,
                    "speed_download_mbps": offer.speed_download_mbps,
                    "speed_upload_mbps": offer.speed_upload_mbps,
                    "monthly_cost_euros": float(offer.monthly_cost_euros),
                    "connection_type": offer.connection_type.value,
                    "contract_duration_months": offer.contract_duration_months,
                    "metadata": {
                        "availability_score": random.uniform(0.7, 1.0),
                        "installation_time_days": random.randint(7, 21),
                        "customer_rating": random.uniform(3.5, 5.0)
                    }
                }
                for offer in offers
            ],
            "address_metadata": {
                "coverage_quality": random.choice(["excellent", "good", "fair"]),
                "infrastructure_age": random.randint(1, 15),
                "competition_level": random.choice(["high", "medium", "low"])
            }
        }


class MockPingPerfect(MockProviderService, IPingPerfect):
    """Mock implementation of PingPerfect provider service."""
    
    def __init__(self):
        """Initialize PingPerfect mock provider."""
        super().__init__("PingPerfect", ProviderType.API_BASED)
    
    async def sign_request(self, request_data: Dict[str, Any]) -> str:
        """Generate mock signature for PingPerfect API."""
        # Simple mock signature based on request data
        data_str = str(sorted(request_data.items()))
        mock_signature = f"mock_signature_{hash(data_str) % 10000:04d}"
        return mock_signature
    
    async def get_signed_offers(self, address: Address) -> List[ProviderOffer]:
        """Get mock offers using signed requests."""
        # Sign the request
        request_data = {
            "address": address.full_address,
            "timestamp": datetime.utcnow().isoformat()
        }
        signature = await self.sign_request(request_data)
        
        # Get offers (signature validation would happen in real implementation)
        offers = await self.get_offers(address)
        
        # Add signature metadata to offers
        for offer in offers:
            offer.add_feature("request_signature", signature)
            offer.add_feature("verified", True)
        
        return offers


class MockProviderRegistry(IProviderRegistry):
    """Mock implementation of provider registry for testing."""
    
    def __init__(self):
        """Initialize with empty registry."""
        self._providers: Dict[str, IProviderService] = {}
    
    async def register_provider(self, provider: IProviderService) -> bool:
        """Register a provider service."""
        self._providers[provider.provider_name] = provider
        return True
    
    async def unregister_provider(self, provider_name: str) -> bool:
        """Unregister a provider service."""
        if provider_name in self._providers:
            del self._providers[provider_name]
            return True
        return False
    
    async def get_provider(self, provider_name: str) -> Optional[IProviderService]:
        """Get a registered provider by name."""
        return self._providers.get(provider_name)
    
    async def get_all_providers(self) -> List[IProviderService]:
        """Get all registered providers."""
        return list(self._providers.values())
    
    async def get_available_providers(self, address: Address) -> List[IProviderService]:
        """Get providers that support a specific address."""
        available_providers = []
        
        for provider in self._providers.values():
            try:
                if await provider.validate_address(address):
                    status = await provider.get_provider_status()
                    if status == ProviderStatus.AVAILABLE:
                        available_providers.append(provider)
            except Exception:
                # Skip providers that fail validation
                continue
        
        return available_providers
    
    async def get_provider_health_status(self) -> Dict[str, ProviderStatus]:
        """Get health status of all registered providers."""
        health_status = {}
        
        for provider_name, provider in self._providers.items():
            try:
                status = await provider.get_provider_status()
                health_status[provider_name] = status
            except Exception:
                health_status[provider_name] = ProviderStatus.ERROR
        
        return health_status


class MockProviderAggregator(IProviderAggregator):
    """Mock implementation of provider aggregator for testing."""
    
    def __init__(self, registry: MockProviderRegistry):
        """Initialize with provider registry."""
        self._registry = registry
    
    async def get_aggregated_offers(self, address: Address, 
                                   provider_names: Optional[List[str]] = None) -> List[ProviderOffer]:
        """Get aggregated offers from multiple providers."""
        all_offers = []
        
        if provider_names:
            providers = []
            for name in provider_names:
                provider = await self._registry.get_provider(name)
                if provider:
                    providers.append(provider)
        else:
            providers = await self._registry.get_available_providers(address)
        
        for provider in providers:
            try:
                offers = await provider.get_offers(address)
                all_offers.extend(offers)
            except Exception:
                # Skip providers that fail
                continue
        
        return all_offers
    
    async def get_offers_with_fallback(self, address: Address, 
                                      primary_providers: List[str],
                                      fallback_providers: List[str]) -> List[ProviderOffer]:
        """Get offers with fallback strategy."""
        # Try primary providers first
        offers = await self.get_aggregated_offers(address, primary_providers)
        
        # If no offers from primary, try fallback
        if not offers:
            offers = await self.get_aggregated_offers(address, fallback_providers)
        
        return offers
    
    async def get_parallel_offers(self, address: Address, 
                                 timeout_seconds: int = 30) -> Dict[str, List[ProviderOffer]]:
        """Get offers from all providers in parallel."""
        providers = await self._registry.get_available_providers(address)
        results = {}
        
        # In a real implementation, this would use asyncio.gather with timeout
        # For mock, we'll simulate parallel execution
        for provider in providers:
            try:
                offers = await provider.get_offers(address)
                results[provider.provider_name] = offers
            except Exception:
                results[provider.provider_name] = []
        
        return results