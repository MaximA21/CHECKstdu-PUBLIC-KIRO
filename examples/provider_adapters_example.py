"""Example demonstrating the use of external provider service adapters."""

import asyncio
import logging
import sys
import os
from decimal import Decimal

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from infrastructure.external_services import (
    ByteMeAdapter,
    VerbynDichAdapter,
    WebWunderAdapter,
    PingPerfectAdapter,
    ProviderRegistry,
    ProviderAggregator
)
from domain.value_objects.address import Address


async def main():
    """Demonstrate provider adapters functionality."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    print("🚀 External Provider Service Adapters Example")
    print("=" * 50)
    
    # Create test address
    address = Address(
        street="Musterstraße",
        house_number="42",
        city="Berlin",
        postal_code="10115",
        country="DE"
    )
    
    print(f"📍 Test Address: {address.full_address}")
    print()
    
    # Initialize provider adapters
    print("🔧 Initializing Provider Adapters...")
    byteme = ByteMeAdapter(logger=logger)
    verbyndich = VerbynDichAdapter(logger=logger)
    webwunder = WebWunderAdapter(logger=logger)
    pingperfect = PingPerfectAdapter(api_key="demo_key", secret_key="demo_secret", logger=logger)
    
    # Create registry and register providers
    print("📋 Setting up Provider Registry...")
    registry = ProviderRegistry(logger=logger)
    
    await registry.register_provider(byteme)
    await registry.register_provider(verbyndich)
    await registry.register_provider(webwunder)
    await registry.register_provider(pingperfect)
    
    print(f"✅ Registered {len(await registry.get_all_providers())} providers")
    print()
    
    # Test individual providers
    print("🧪 Testing Individual Providers...")
    print("-" * 30)
    
    for provider_name in ["ByteMe", "VerbynDich", "WebWunder", "PingPerfect"]:
        provider = await registry.get_provider(provider_name)
        if provider:
            try:
                print(f"\n{provider_name}:")
                print(f"  Type: {provider.provider_type.value}")
                print(f"  Regions: {', '.join(provider.supported_regions)}")
                
                # Validate address
                is_valid = await provider.validate_address(address)
                print(f"  Address Valid: {is_valid}")
                
                # Get status
                status = await provider.get_provider_status()
                print(f"  Status: {status.value}")
                
                # Get rate limit info
                rate_info = await provider.get_rate_limit_info()
                print(f"  Rate Limit: {rate_info.get('remaining_requests', 'N/A')} remaining")
                
                # Get offers (this will use mock data)
                if is_valid:
                    offers = await provider.get_offers(address)
                    print(f"  Offers: {len(offers)} found")
                    
                    if offers:
                        best_offer = min(offers, key=lambda x: x.monthly_cost_euros)
                        print(f"  Best Offer: {best_offer.speed_download_mbps} Mbps for {best_offer.monthly_cost_euros}€/month")
                
            except Exception as e:
                print(f"  Error: {e}")
    
    print("\n" + "=" * 50)
    
    # Test aggregator
    print("🔄 Testing Provider Aggregator...")
    aggregator = ProviderAggregator(registry, logger=logger)
    
    # Get aggregated offers from all providers
    print("\n📊 Getting Aggregated Offers...")
    all_offers = await aggregator.get_aggregated_offers(address)
    
    print(f"✅ Found {len(all_offers)} total offers from all providers")
    
    if all_offers:
        # Sort by price
        sorted_offers = sorted(all_offers, key=lambda x: x.monthly_cost_euros)
        
        print("\n🏆 Top 5 Offers by Price:")
        for i, offer in enumerate(sorted_offers[:5], 1):
            print(f"  {i}. {offer.provider_name} - {offer.speed_download_mbps} Mbps")
            print(f"     {offer.monthly_cost_euros}€/month ({offer.connection_type.value})")
            
            # Show additional features if available
            features = []
            if offer.has_feature("tv_included") and offer.get_feature("tv_included"):
                features.append("TV included")
            if offer.has_feature("installation_service") and offer.get_feature("installation_service"):
                features.append("Installation service")
            if features:
                print(f"     Features: {', '.join(features)}")
            print()
    
    # Test parallel offers
    print("⚡ Testing Parallel Offers...")
    parallel_results = await aggregator.get_parallel_offers(address, timeout_seconds=10)
    
    print(f"📈 Parallel Results Summary:")
    for provider_name, offers in parallel_results.items():
        print(f"  {provider_name}: {len(offers)} offers")
    
    # Test fallback strategy
    print("\n🔄 Testing Fallback Strategy...")
    primary_providers = ["ByteMe", "VerbynDich"]
    fallback_providers = ["WebWunder", "PingPerfect"]
    
    fallback_offers = await aggregator.get_offers_with_fallback(
        address, primary_providers, fallback_providers
    )
    
    print(f"🎯 Fallback Strategy Result: {len(fallback_offers)} offers")
    
    # Test best offers
    print("\n🌟 Getting Best Offers...")
    best_by_price = await aggregator.get_best_offers(address, max_offers=3, sort_by="price")
    best_by_speed = await aggregator.get_best_offers(address, max_offers=3, sort_by="speed")
    
    print(f"💰 Best by Price: {len(best_by_price)} offers")
    if best_by_price:
        cheapest = best_by_price[0]
        print(f"   Cheapest: {cheapest.provider_name} - {cheapest.monthly_cost_euros}€/month")
    
    print(f"🚀 Best by Speed: {len(best_by_speed)} offers")
    if best_by_speed:
        fastest = best_by_speed[0]
        print(f"   Fastest: {fastest.provider_name} - {fastest.speed_download_mbps} Mbps")
    
    # Get aggregation statistics
    print("\n📊 Aggregation Statistics...")
    stats = await aggregator.get_aggregation_statistics(address)
    
    print(f"  Total Offers: {stats.get('total_offers', 0)}")
    print(f"  Successful Providers: {stats.get('successful_providers', 0)}")
    print(f"  Failed Providers: {stats.get('failed_providers', 0)}")
    print(f"  Processing Time: {stats.get('processing_time_seconds', 0):.2f}s")
    
    # Registry statistics
    print("\n📋 Registry Statistics...")
    registry_stats = await registry.get_provider_statistics()
    
    print(f"  Total Providers: {registry_stats.get('total_providers', 0)}")
    print(f"  Provider Types: {registry_stats.get('provider_types', {})}")
    print(f"  Status Distribution: {registry_stats.get('status_distribution', {})}")
    
    print("\n" + "=" * 50)
    print("✅ Provider Adapters Example Complete!")


if __name__ == "__main__":
    asyncio.run(main())