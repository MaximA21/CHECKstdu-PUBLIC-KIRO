#!/usr/bin/env python3
"""
WebWunder SOAP API Test Script
Tests different parameters to understand API behavior
"""

import json
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

import requests

# Configuration
API_URL = "https://webwunder.gendev7.check24.fun/endpunkte/soap/ws/getInternetOffers.wsdl"  # Keep .wsdl as in Postman
API_KEY = "D0156B21AE587299B0B1E9D17444BAAF8C308887C4E2A157269C58CCFCA092F2898F6C30F81EDF791C41E729F9088CA8172FD3F20E9E72881231CC06E9021266"  # Replace with actual key

# Extended test data - more addresses across Germany
TEST_ADDRESSES = [
    {"name": "Munich", "street": "Kiefernstrasse", "houseNumber": "25", "city": "Munich", "plz": "81549"},
    {"name": "Berlin", "street": "Alexanderplatz", "houseNumber": "1", "city": "Berlin", "plz": "10178"},
    {"name": "Hamburg", "street": "Reeperbahn", "houseNumber": "10", "city": "Hamburg", "plz": "20359"},
    {"name": "Cologne", "street": "Hohe Strasse", "houseNumber": "50", "city": "Köln", "plz": "50667"},
    {"name": "Frankfurt", "street": "Zeil", "houseNumber": "106", "city": "Frankfurt am Main", "plz": "60313"},
    {"name": "Stuttgart", "street": "Königstrasse", "houseNumber": "78", "city": "Stuttgart", "plz": "70173"},
    {"name": "Düsseldorf", "street": "Königsallee", "houseNumber": "2", "city": "Düsseldorf", "plz": "40212"},
    {"name": "Leipzig", "street": "Augustusplatz", "houseNumber": "9", "city": "Leipzig", "plz": "04109"},
    {"name": "Nuremberg", "street": "Hauptmarkt", "houseNumber": "14", "city": "Nürnberg", "plz": "90403"},
    {"name": "Dresden", "street": "Prager Strasse", "houseNumber": "2", "city": "Dresden", "plz": "01069"},
]

# Try different connection type variations based on your working example
CONNECTION_TYPES = ["FIBER", "DSL", "CABLE"]
INSTALLATION_OPTIONS = [True, False]

# Test configuration
SAMPLING_ROUNDS = 5  # How many times to test each combination
ROUND_DELAY_MINUTES = 2  # Wait time between rounds (in minutes)
QUICK_MODE = False  # Set to True for faster testing with fewer addresses


def create_soap_envelope(address: Dict, installation: bool, connection_type: str) -> str:
    """Create SOAP envelope with given parameters - exactly like Postman"""
    return f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:gs="http://webwunder.gendev7.check24.fun/offerservice">
<soapenv:Header/>
<soapenv:Body>
<gs:legacyGetInternetOffers>
<gs:input>
<gs:installation>{str(installation).lower()}</gs:installation>
<gs:connectionEnum>{connection_type}</gs:connectionEnum>
<gs:address>
<gs:street>{address['street']}</gs:street>
<gs:houseNumber>{address['houseNumber']}</gs:houseNumber>
<gs:city>{address['city']}</gs:city>
<gs:plz>{address['plz']}</gs:plz>
<gs:countryCode>DE</gs:countryCode>
</gs:address>
</gs:input>
</gs:legacyGetInternetOffers>
</soapenv:Body>
</soapenv:Envelope>"""


def extract_offer_details(xml_response: str) -> List[Dict]:
    """Extract detailed offer information from XML response"""
    offers = []

    try:
        root = ET.fromstring(xml_response)

        # Register namespace to avoid issues
        namespaces = {
            "ns2": "http://webwunder.gendev7.check24.fun/offerservice",
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
        }

        # Find all product elements using the correct namespace
        product_elements = root.findall(".//ns2:products", namespaces)

        if not product_elements:
            # Fallback: try without namespace
            product_elements = root.findall(".//products")

        print(f"🔍 Found {len(product_elements)} product elements")

        for i, product_elem in enumerate(product_elements, 1):
            try:
                # Extract basic product info
                product_id = product_elem.find("ns2:productId", namespaces)
                if product_id is None:
                    product_id = product_elem.find("productId")

                provider_name = product_elem.find("ns2:providerName", namespaces)
                if provider_name is None:
                    provider_name = product_elem.find("providerName")

                # Find productInfo element
                product_info = product_elem.find("ns2:productInfo", namespaces)
                if product_info is None:
                    product_info = product_elem.find("productInfo")

                offer_details = {
                    "offer_id": i,
                    "product_id": product_id.text if product_id is not None else "N/A",
                    "provider_name": provider_name.text if provider_name is not None else "N/A",
                }

                if product_info is not None:
                    # Extract details from productInfo
                    speed = product_info.find("ns2:speed", namespaces)
                    if speed is None:
                        speed = product_info.find("speed")
                    offer_details["speed"] = speed.text if speed is not None else "N/A"

                    monthly_cost = product_info.find("ns2:monthlyCostInCent", namespaces)
                    if monthly_cost is None:
                        monthly_cost = product_info.find("monthlyCostInCent")
                    offer_details["monthly_cost"] = monthly_cost.text if monthly_cost is not None else "N/A"

                    monthly_cost_25 = product_info.find("ns2:monthlyCostInCentFrom25thMonth", namespaces)
                    if monthly_cost_25 is None:
                        monthly_cost_25 = product_info.find("monthlyCostInCentFrom25thMonth")
                    offer_details["monthly_cost_from_25th"] = monthly_cost_25.text if monthly_cost_25 is not None else "N/A"

                    contract_duration = product_info.find("ns2:contractDurationInMonths", namespaces)
                    if contract_duration is None:
                        contract_duration = product_info.find("contractDurationInMonths")
                    offer_details["contract_duration"] = contract_duration.text if contract_duration is not None else "N/A"

                    connection_type = product_info.find("ns2:connectionType", namespaces)
                    if connection_type is None:
                        connection_type = product_info.find("connectionType")
                    offer_details["connection_type"] = connection_type.text if connection_type is not None else "N/A"

                    # Extract voucher info if present
                    voucher = product_info.find("ns2:voucher", namespaces)
                    if voucher is None:
                        voucher = product_info.find("voucher")

                    if voucher is not None:
                        percentage = voucher.find("ns2:percentage", namespaces)
                        if percentage is None:
                            percentage = voucher.find("percentage")
                        offer_details["voucher_percentage"] = percentage.text if percentage is not None else "N/A"

                        max_discount = voucher.find("ns2:maxDiscountInCent", namespaces)
                        if max_discount is None:
                            max_discount = voucher.find("maxDiscountInCent")
                        offer_details["voucher_max_discount"] = max_discount.text if max_discount is not None else "N/A"

                # Print the extracted offer info
                speed_text = f" - {offer_details['speed']} Mbps" if offer_details["speed"] != "N/A" else ""
                print(f"📦 Extracted offer {i}: {offer_details['provider_name']}{speed_text}")

                offers.append(offer_details)

            except Exception as e:
                print(f"⚠️  Error processing product {i}: {e}")
                continue

    except ET.ParseError as e:
        print(f"⚠️  XML parsing error: {e}")
        return []
    except Exception as e:
        print(f"⚠️  Error extracting offers: {e}")
        return []

    return offers


def call_webwunder_api(address: Dict, installation: bool, connection_type: str) -> Dict[str, Any]:
    """Call WebWunder API with given parameters"""

    soap_body = create_soap_envelope(address, installation, connection_type)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "X-Api-Key": API_KEY,
        # No SOAPAction needed based on your Postman example
    }

    try:
        print(f"🔄 Testing {address['name']} | {connection_type} | Installation: {installation}")

        response = requests.post(API_URL, data=soap_body, headers=headers, timeout=30)

        result = {
            "address": address["name"],
            "connection_type": connection_type,
            "installation": installation,
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response_size": len(response.text),
            "offers_count": 0,
            "error": None,
            "raw_response": response.text[:500] + "..." if len(response.text) > 500 else response.text,
        }

        if response.status_code == 200:
            # Extract detailed offer information
            offers = extract_offer_details(response.text)
            result["offers_count"] = len(offers)
            result["offers_details"] = offers

            if offers:
                # Summary statistics
                result["has_pricing"] = any(offer.get("monthly_cost") != "N/A" for offer in offers)
                result["has_discounts"] = any(offer.get("voucher_percentage") != "N/A" for offer in offers)
                result["unique_names"] = list(
                    set(offer.get("provider_name") for offer in offers if offer.get("provider_name") != "N/A")
                )
                result["speed_range"] = [offer.get("speed") for offer in offers if offer.get("speed") != "N/A"]

        else:
            result["error"] = f"HTTP {response.status_code}: {response.text[:500]}"
            # Try to extract SOAP fault details for better debugging
            if "SOAP-ENV:Fault" in response.text or "soap:Fault" in response.text:
                try:
                    root = ET.fromstring(response.text)
                    fault_code = root.find(".//*[local-name()='faultcode']")
                    fault_string = root.find(".//*[local-name()='faultstring']")
                    if fault_code is not None and fault_string is not None:
                        result["soap_fault"] = f"{fault_code.text}: {fault_string.text}"
                except:
                    pass

        return result

    except requests.exceptions.Timeout:
        return {
            "address": address["name"],
            "connection_type": connection_type,
            "installation": installation,
            "error": "Request timeout",
            "success": False,
        }
    except Exception as e:
        return {
            "address": address["name"],
            "connection_type": connection_type,
            "installation": installation,
            "error": str(e),
            "success": False,
        }


def analyze_results(results: List[Dict]) -> None:
    """Analyze test results to find patterns"""

    print("\n" + "=" * 80)
    print("📊 BASIC ANALYSIS RESULTS")
    print("=" * 80)

    # Group by different criteria
    by_installation = {}
    by_connection = {}
    by_address = {}

    for result in results:
        if not result["success"]:
            continue

        # Group by installation parameter
        inst_key = result["installation"]
        if inst_key not in by_installation:
            by_installation[inst_key] = []
        by_installation[inst_key].append(result)

        # Group by connection type
        conn_key = result["connection_type"]
        if conn_key not in by_connection:
            by_connection[conn_key] = []
        by_connection[conn_key].append(result)

        # Group by address
        addr_key = result["address"]
        if addr_key not in by_address:
            by_address[addr_key] = []
        by_address[addr_key].append(result)

    print("\n🔧 INSTALLATION PARAMETER IMPACT:")
    for installation, results_list in by_installation.items():
        avg_offers = sum(r["offers_count"] for r in results_list) / len(results_list)
        total_tests = len(results_list)
        print(f"  Installation={installation}: {total_tests} tests, avg {avg_offers:.1f} offers")

    print("\n🌐 CONNECTION TYPE IMPACT:")
    for conn_type, results_list in by_connection.items():
        avg_offers = sum(r["offers_count"] for r in results_list) / len(results_list)
        total_tests = len(results_list)
        print(f"  {conn_type}: {total_tests} tests, avg {avg_offers:.1f} offers")

    print("\n📍 ADDRESS IMPACT:")
    for address, results_list in by_address.items():
        avg_offers = sum(r["offers_count"] for r in results_list) / len(results_list)
        total_tests = len(results_list)
        print(f"  {address}: {total_tests} tests, avg {avg_offers:.1f} offers")

    # Basic installation parameter comparison
    print("\n🔍 BASIC INSTALLATION PARAMETER COMPARISON:")

    # Get unique address/connection combinations from the results
    test_combinations = set()
    for result in results:
        if result["success"]:
            test_combinations.add((result["address"], result["connection_type"]))

    for address, conn_type in test_combinations:
        true_results = [
            r
            for r in results
            if r["address"] == address and r["connection_type"] == conn_type and r["installation"] == True and r["success"]
        ]
        false_results = [
            r
            for r in results
            if r["address"] == address and r["connection_type"] == conn_type and r["installation"] == False and r["success"]
        ]

        if true_results and false_results:
            # Calculate averages across all rounds for this combination
            true_avg = sum(r["offers_count"] for r in true_results) / len(true_results)
            false_avg = sum(r["offers_count"] for r in false_results) / len(false_results)

            if abs(true_avg - false_avg) > 0.1:  # Any noticeable difference
                print(f"  🎯 DIFFERENCE FOUND! {address} {conn_type}:")
                print(f"    Installation=true:  {true_avg:.1f} offers (avg)")
                print(f"    Installation=false: {false_avg:.1f} offers (avg)")
            else:
                print(f"  ✅ No difference: {address} {conn_type} ({true_avg:.1f} offers)")


def compare_installation_impact(results: List[Dict]) -> Dict[str, Any]:
    """Deep analysis of installation parameter impact"""

    impact_analysis = {
        "significant_differences": [],
        "no_differences": [],
        "price_differences": [],
        "offer_count_differences": [],
        "summary_stats": {},
    }

    # Group results by address and connection type
    grouped = {}
    for result in results:
        if not result["success"]:
            continue

        key = f"{result['address']}_{result['connection_type']}"
        if key not in grouped:
            grouped[key] = {"true": [], "false": []}

        grouped[key][str(result["installation"]).lower()].append(result)

    print("\n🔬 DETAILED INSTALLATION PARAMETER IMPACT ANALYSIS:")
    print("=" * 70)

    for group_key, group_data in grouped.items():
        address, conn_type = group_key.split("_", 1)

        true_results = group_data["true"]
        false_results = group_data["false"]

        if not true_results or not false_results:
            continue

        print(f"\n📍 {address} | {conn_type}:")

        # Compare offer counts across all rounds
        true_counts = [r["offers_count"] for r in true_results]
        false_counts = [r["offers_count"] for r in false_results]

        true_avg = sum(true_counts) / len(true_counts)
        false_avg = sum(false_counts) / len(false_counts)

        print(f"   Installation=True:  {true_counts} (avg: {true_avg:.1f})")
        print(f"   Installation=False: {false_counts} (avg: {false_avg:.1f})")

        # Check for significant differences
        if abs(true_avg - false_avg) > 0.5:  # More than 0.5 offers difference on average
            impact_analysis["significant_differences"].append(
                {
                    "location": f"{address}_{conn_type}",
                    "true_avg": true_avg,
                    "false_avg": false_avg,
                    "difference": true_avg - false_avg,
                }
            )
            print(f"   🎯 SIGNIFICANT DIFFERENCE: {true_avg - false_avg:.1f} offers")
        else:
            impact_analysis["no_differences"].append(f"{address}_{conn_type}")
            print(f"   ✅ No significant difference")

        # Compare prices if available
        true_prices = []
        false_prices = []

        for result in true_results:
            if result.get("offers_details"):
                for offer in result["offers_details"]:
                    if offer.get("monthly_cost") != "N/A":
                        try:
                            price = int(offer["monthly_cost"])
                            true_prices.append(price)
                        except:
                            pass

        for result in false_results:
            if result.get("offers_details"):
                for offer in result["offers_details"]:
                    if offer.get("monthly_cost") != "N/A":
                        try:
                            price = int(offer["monthly_cost"])
                            false_prices.append(price)
                        except:
                            pass

        if true_prices and false_prices:
            true_price_avg = sum(true_prices) / len(true_prices)
            false_price_avg = sum(false_prices) / len(false_prices)
            price_diff = abs(true_price_avg - false_price_avg)

            if price_diff > 100:  # More than 1 EUR difference (prices in cents)
                impact_analysis["price_differences"].append(
                    {
                        "location": f"{address}_{conn_type}",
                        "true_avg_price": true_price_avg,
                        "false_avg_price": false_price_avg,
                        "difference_cents": price_diff,
                    }
                )
                print(f"   💰 Price difference: {price_diff / 100:.2f} EUR")

    return impact_analysis


def save_comprehensive_results(results: List[Dict], analysis: Dict) -> str:
    """Save detailed results with analysis"""

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"webwunder_comprehensive_test_{timestamp}.json"

    comprehensive_data = {
        "test_metadata": {
            "timestamp": timestamp,
            "total_addresses": len(TEST_ADDRESSES),
            "connection_types": CONNECTION_TYPES,
            "sampling_rounds": SAMPLING_ROUNDS,
            "total_tests": len(results),
        },
        "impact_analysis": analysis,
        "raw_results": results,
        "summary": {
            "successful_tests": len([r for r in results if r["success"]]),
            "failed_tests": len([r for r in results if not r["success"]]),
            "total_offers_found": sum(r.get("offers_count", 0) for r in results),
            "locations_with_differences": len(analysis["significant_differences"]),
            "locations_with_price_differences": len(analysis["price_differences"]),
        },
    }

    with open(filename, "w") as f:
        json.dump(comprehensive_data, f, indent=2)

    print(f"\n💾 Comprehensive results saved to {filename}")
    return filename


def main():
    """Run the comprehensive test suite"""
    print("🚀 WebWunder API Comprehensive Test Suite")
    print(
        f"📊 Testing {len(TEST_ADDRESSES)} addresses × {len(CONNECTION_TYPES)} connection types × {len(INSTALLATION_OPTIONS)} installation options"
    )
    print(f"🔄 Running {SAMPLING_ROUNDS} sampling rounds with {ROUND_DELAY_MINUTES}min delays")

    # Filter addresses for quick mode
    addresses_to_test = TEST_ADDRESSES[:3] if QUICK_MODE else TEST_ADDRESSES
    if QUICK_MODE:
        print("⚡ Quick mode: Testing first 3 addresses only")

    all_results = []
    total_combinations = len(addresses_to_test) * len(CONNECTION_TYPES) * len(INSTALLATION_OPTIONS)

    for round_num in range(1, SAMPLING_ROUNDS + 1):
        print(f"\n{'=' * 60}")
        print(f"🔄 SAMPLING ROUND {round_num}/{SAMPLING_ROUNDS}")
        print(f"{'=' * 60}")

        round_results = []
        current_test = 0

        for address in addresses_to_test:
            for connection_type in CONNECTION_TYPES:
                for installation in INSTALLATION_OPTIONS:
                    current_test += 1
                    print(f"\n[Round {round_num}, Test {current_test}/{total_combinations}] ", end="")

                    result = call_webwunder_api(address, installation, connection_type)
                    result["round"] = round_num
                    result["timestamp"] = time.time()

                    round_results.append(result)
                    all_results.append(result)

                    # Show immediate result
                    if result["success"]:
                        print(f"✅ Success: {result['offers_count']} offers")
                    else:
                        print(f"❌ Failed: {result.get('error', 'Unknown error')}")

                    # Rate limiting - be nice to their API
                    time.sleep(2)

        print(f"\n✅ Round {round_num} completed: {len([r for r in round_results if r['success']])} successful tests")

        # Wait between rounds (except for the last round)
        if round_num < SAMPLING_ROUNDS:
            print(f"⏰ Waiting {ROUND_DELAY_MINUTES} minutes before next round...")
            time.sleep(ROUND_DELAY_MINUTES * 60)

    # Comprehensive analysis
    print(f"\n{'=' * 80}")
    print("🧪 COMPREHENSIVE ANALYSIS")
    print(f"{'=' * 80}")

    # Basic analysis
    analyze_results(all_results)

    # Deep installation parameter analysis
    impact_analysis = compare_installation_impact(all_results)

    # Save comprehensive results
    filename = save_comprehensive_results(all_results, impact_analysis)

    # Final summary
    successful_tests = [r for r in all_results if r["success"]]
    failed_tests = [r for r in all_results if not r["success"]]

    print(f"\n📈 FINAL SUMMARY:")
    print(f"  Total test combinations: {len(all_results)}")
    print(f"  Successful tests: {len(successful_tests)}")
    print(f"  Failed tests: {len(failed_tests)}")
    print(f"  Success rate: {len(successful_tests) / len(all_results) * 100:.1f}%")

    if successful_tests:
        total_offers = sum(r["offers_count"] for r in successful_tests)
        avg_offers = total_offers / len(successful_tests)
        print(f"  Average offers per successful test: {avg_offers:.1f}")

    # Installation parameter conclusions
    if impact_analysis["significant_differences"]:
        print(f"\n🎯 INSTALLATION PARAMETER CONCLUSIONS:")
        print(
            f"  Found significant differences in {len(impact_analysis['significant_differences'])} location/connection combinations"
        )
        for diff in impact_analysis["significant_differences"]:
            print(f"    {diff['location']}: {diff['difference']:+.1f} offers difference")
    else:
        print(f"\n🤷 INSTALLATION PARAMETER CONCLUSIONS:")
        print(f"  No significant differences found across {len(impact_analysis['no_differences'])} tested combinations")
        print(f"  The installation parameter appears to have minimal impact on offer availability")

    if impact_analysis["price_differences"]:
        print(f"\n💰 PRICE IMPACT:")
        for price_diff in impact_analysis["price_differences"]:
            print(f"    {price_diff['location']}: {price_diff['difference_cents'] / 100:.2f} EUR difference")

    print(f"\n📁 Detailed data saved in: {filename}")


if __name__ == "__main__":
    # You can modify these settings for different testing scenarios
    print("🔧 Test Configuration:")
    print(f"   SAMPLING_ROUNDS = {SAMPLING_ROUNDS}")
    print(f"   ROUND_DELAY_MINUTES = {ROUND_DELAY_MINUTES}")
    print(f"   QUICK_MODE = {QUICK_MODE}")
    print("\n" + "=" * 50)

    main()
