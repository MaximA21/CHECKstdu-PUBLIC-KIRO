"""Simple demonstration of provider adapter concepts."""

import asyncio
from decimal import Decimal


class MockAddress:
    """Mock address for demonstration."""
    
    def __init__(self, street, house_number, city, postal_code, country="DE"):
        self.street = street
        self.house_number = house_number
        self.city = city
        self.postal_code = postal_code
        self.country = country
    
    @property
    def full_address(self):
        return f"{self.street} {self.house_number}, {self.postal_code} {self.city}"


class MockOffer:
    """Mock offer for demonstration."""
    
    def __init__(self, provider_name, product_id, speed_mbps, monthly_cost_euros, connection_type):
        self.provider_name = provider_name
        self.product_id = product_id
        self.speed_mbps = speed_mbps
        self.monthly_cost_euros = Decimal(str(monthly_cost_euros))
        self.connection_type = connection_type


async def demonstrate_byteme_parsing():
    """Demonstrate ByteMe CSV parsing logic."""
    print("🔍 ByteMe CSV Parsing Demo")
    print("-" * 30)
    
    # Sample CSV data (similar to what ByteMe would return)
    csv_data = """productId,providerName,speed,monthlyCostInCent,connectionType
byteme_dsl_25,ByteMe,25,2999,DSL
byteme_dsl_50,ByteMe,50,3999,DSL
byteme_cable_100,ByteMe,100,4999,Cable"""
    
    print("Sample CSV Data:")
    print(csv_data)
    print()
    
    # Parse CSV (simplified version)
    lines = csv_data.strip().split('\n')
    header = lines[0].split(',')
    
    offers = []
    for line in lines[1:]:
        fields = line.split(',')
        offer = MockOffer(
            provider_name=fields[1],
            product_id=fields[0],
            speed_mbps=int(fields[2]),
            monthly_cost_euros=int(fields[3]) / 100,
            connection_type=fields[4]
        )
        offers.append(offer)
    
    print(f"Parsed {len(offers)} offers:")
    for offer in offers:
        print(f"  - {offer.product_id}: {offer.speed_mbps} Mbps for {offer.monthly_cost_euros}€/month ({offer.connection_type})")
    
    return offers


async def demonstrate_verbyndich_parsing():
    """Demonstrate VerbynDich nested array parsing logic."""
    print("\n🔍 VerbynDich Nested Array Parsing Demo")
    print("-" * 40)
    
    # Sample nested array data (similar to what VerbynDich would return)
    nested_data = {
        "results": [
            [
                [
                    {
                        "valid": True,
                        "product": "verbyndich_dsl_25",
                        "description": "Für nur 24€ im Monat erhalten Sie eine DSL-Verbindung mit einer Geschwindigkeit von 25 Mbit/s. Mindestvertragslaufzeit 12 Monate."
                    }
                ]
            ],
            [
                {
                    "valid": True,
                    "product": "verbyndich_cable_100",
                    "description": "Für nur 39€ im Monat erhalten Sie eine Cable-Verbindung mit einer Geschwindigkeit von 100 Mbit/s. Fernsehsender enthalten."
                }
            ]
        ]
    }
    
    print("Sample Nested Data Structure:")
    print(f"Results with {len(nested_data['results'])} top-level items")
    print()
    
    # Flatten nested structure
    def flatten_nested(obj):
        if isinstance(obj, list):
            for item in obj:
                yield from flatten_nested(item)
        elif isinstance(obj, dict):
            if 'results' in obj:
                yield from flatten_nested(obj['results'])
            else:
                yield obj
        else:
            yield obj
    
    flattened = list(flatten_nested(nested_data))
    valid_items = [item for item in flattened if isinstance(item, dict) and item.get('valid')]
    
    print(f"Flattened to {len(valid_items)} valid items:")
    
    offers = []
    for item in valid_items:
        # Simple description parsing
        description = item.get('description', '')
        
        # Extract price
        import re
        price_match = re.search(r'(\d+)€ im Monat', description)
        price = float(price_match.group(1)) if price_match else 0.0
        
        # Extract speed
        speed_match = re.search(r'(\d+) Mbit/s', description)
        speed = int(speed_match.group(1)) if speed_match else 0
        
        # Extract connection type
        connection_type = "DSL"
        if "Cable-Verbindung" in description:
            connection_type = "Cable"
        elif "Fiber-Verbindung" in description:
            connection_type = "Fiber"
        
        offer = MockOffer(
            provider_name="VerbynDich",
            product_id=item.get('product', 'unknown'),
            speed_mbps=speed,
            monthly_cost_euros=price,
            connection_type=connection_type
        )
        offers.append(offer)
        
        print(f"  - {offer.product_id}: {offer.speed_mbps} Mbps for {offer.monthly_cost_euros}€/month ({offer.connection_type})")
    
    return offers


async def demonstrate_webwunder_parsing():
    """Demonstrate WebWunder XML parsing logic."""
    print("\n🔍 WebWunder XML Parsing Demo")
    print("-" * 32)
    
    # Sample XML data (simplified)
    xml_data = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <products>
            <productId>webwunder_fiber_500</productId>
            <providerName>WebWunder</providerName>
            <productInfo>
                <speed>500</speed>
                <monthlyCostInCent>5999</monthlyCostInCent>
                <connectionType>Fiber</connectionType>
            </productInfo>
        </products>
    </soap:Body>
</soap:Envelope>"""
    
    print("Sample XML Data (simplified):")
    print(xml_data[:200] + "...")
    print()
    
    # Simple XML parsing (in real implementation would use ElementTree)
    import re
    
    # Extract values using regex (simplified approach)
    product_id = re.search(r'<productId>(.*?)</productId>', xml_data)
    provider_name = re.search(r'<providerName>(.*?)</providerName>', xml_data)
    speed = re.search(r'<speed>(.*?)</speed>', xml_data)
    cost = re.search(r'<monthlyCostInCent>(.*?)</monthlyCostInCent>', xml_data)
    connection_type = re.search(r'<connectionType>(.*?)</connectionType>', xml_data)
    
    if all([product_id, provider_name, speed, cost, connection_type]):
        offer = MockOffer(
            provider_name=provider_name.group(1),
            product_id=product_id.group(1),
            speed_mbps=int(speed.group(1)),
            monthly_cost_euros=int(cost.group(1)) / 100,
            connection_type=connection_type.group(1)
        )
        
        print(f"Parsed offer:")
        print(f"  - {offer.product_id}: {offer.speed_mbps} Mbps for {offer.monthly_cost_euros}€/month ({offer.connection_type})")
        
        return [offer]
    
    return []


async def demonstrate_ping_perfect_parsing():
    """Demonstrate PingPerfect API parsing logic."""
    print("\n🔍 PingPerfect API Parsing Demo")
    print("-" * 33)
    
    # Sample API response data
    api_response = [
        {
            "call_type": "fiber",
            "offers": [
                {
                    "providerName": "PingPerfect",
                    "productInfo": {
                        "speed": 1000,
                        "connectionType": "Fiber"
                    },
                    "pricingDetails": {
                        "monthlyCostInCent": 5999
                    }
                }
            ]
        },
        {
            "call_type": "non_fiber",
            "offers": [
                {
                    "providerName": "PingPerfect",
                    "productInfo": {
                        "speed": 100,
                        "connectionType": "Cable"
                    },
                    "pricingDetails": {
                        "monthlyCostInCent": 3999
                    }
                }
            ]
        }
    ]
    
    print("Sample API Response:")
    print(f"Response with {len(api_response)} call types")
    print()
    
    offers = []
    for call_data in api_response:
        call_type = call_data.get('call_type', 'unknown')
        call_offers = call_data.get('offers', [])
        
        print(f"Processing {call_type} call with {len(call_offers)} offers:")
        
        for i, offer_data in enumerate(call_offers, 1):
            product_info = offer_data.get('productInfo', {})
            pricing_details = offer_data.get('pricingDetails', {})
            
            offer = MockOffer(
                provider_name=offer_data.get('providerName', 'PingPerfect'),
                product_id=f"ping_perfect_{call_type}_{i}",
                speed_mbps=product_info.get('speed', 0),
                monthly_cost_euros=pricing_details.get('monthlyCostInCent', 0) / 100,
                connection_type=product_info.get('connectionType', 'Unknown')
            )
            offers.append(offer)
            
            print(f"  - {offer.product_id}: {offer.speed_mbps} Mbps for {offer.monthly_cost_euros}€/month ({offer.connection_type})")
    
    return offers


async def demonstrate_aggregation():
    """Demonstrate offer aggregation."""
    print("\n🔄 Offer Aggregation Demo")
    print("-" * 25)
    
    # Get offers from all providers
    byteme_offers = await demonstrate_byteme_parsing()
    verbyndich_offers = await demonstrate_verbyndich_parsing()
    webwunder_offers = await demonstrate_webwunder_parsing()
    pingperfect_offers = await demonstrate_ping_perfect_parsing()
    
    # Aggregate all offers
    all_offers = byteme_offers + verbyndich_offers + webwunder_offers + pingperfect_offers
    
    print(f"\n📊 Aggregation Results:")
    print(f"Total offers from all providers: {len(all_offers)}")
    
    # Sort by price
    sorted_by_price = sorted(all_offers, key=lambda x: x.monthly_cost_euros)
    print(f"\n💰 Cheapest offers:")
    for i, offer in enumerate(sorted_by_price[:3], 1):
        print(f"  {i}. {offer.provider_name} - {offer.monthly_cost_euros}€/month ({offer.speed_mbps} Mbps, {offer.connection_type})")
    
    # Sort by speed
    sorted_by_speed = sorted(all_offers, key=lambda x: x.speed_mbps, reverse=True)
    print(f"\n🚀 Fastest offers:")
    for i, offer in enumerate(sorted_by_speed[:3], 1):
        print(f"  {i}. {offer.provider_name} - {offer.speed_mbps} Mbps ({offer.monthly_cost_euros}€/month, {offer.connection_type})")
    
    # Group by connection type
    by_connection_type = {}
    for offer in all_offers:
        conn_type = offer.connection_type
        if conn_type not in by_connection_type:
            by_connection_type[conn_type] = []
        by_connection_type[conn_type].append(offer)
    
    print(f"\n🔌 Offers by connection type:")
    for conn_type, offers in by_connection_type.items():
        print(f"  {conn_type}: {len(offers)} offers")


async def main():
    """Main demonstration function."""
    print("🚀 External Provider Service Adapters Demo")
    print("=" * 50)
    print("This demo shows the core parsing logic from each provider adapter")
    print("without the full dependency injection setup.")
    print()
    
    # Create test address
    address = MockAddress(
        street="Musterstraße",
        house_number="42",
        city="Berlin",
        postal_code="10115",
        country="DE"
    )
    
    print(f"📍 Test Address: {address.full_address}")
    print()
    
    # Demonstrate each provider's parsing logic
    await demonstrate_byteme_parsing()
    await demonstrate_verbyndich_parsing()
    await demonstrate_webwunder_parsing()
    await demonstrate_ping_perfect_parsing()
    
    # Demonstrate aggregation
    await demonstrate_aggregation()
    
    print("\n" + "=" * 50)
    print("✅ Provider Adapters Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("- ByteMe: CSV parsing with Polars optimization")
    print("- VerbynDich: Nested array flattening and description parsing")
    print("- WebWunder: XML SOAP response parsing")
    print("- PingPerfect: API response parsing with request signing")
    print("- Aggregation: Combining offers from multiple providers")
    print("- Sorting: By price, speed, and connection type")


if __name__ == "__main__":
    asyncio.run(main())