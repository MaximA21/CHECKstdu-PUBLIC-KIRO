#!/usr/bin/env python3
"""
Script to demonstrate REST API traffic distribution between old and new implementations.
This script shows how to implement client-side traffic distribution for canary deployments.
"""

import argparse
import requests
import random
import json
import time
import statistics
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


class RestApiTrafficDistributor:
    """Distributes traffic between old and new REST API implementations."""
    
    def __init__(self, prod_endpoint: str, canary_endpoint: str, traffic_split: int = 10):
        """
        Initialize the traffic distributor.
        
        Args:
            prod_endpoint: Production endpoint URL
            canary_endpoint: Canary endpoint URL  
            traffic_split: Percentage of traffic to send to canary (0-100)
        """
        self.prod_endpoint = prod_endpoint.rstrip('/')
        self.canary_endpoint = canary_endpoint.rstrip('/')
        self.traffic_split = traffic_split
        
    def get_endpoint_for_request(self) -> str:
        """Determine which endpoint to use based on traffic split."""
        if random.randint(1, 100) <= self.traffic_split:
            return self.canary_endpoint
        else:
            return self.prod_endpoint
    
    def make_request(self, path: str, method: str = 'GET', **kwargs) -> Dict[str, Any]:
        """Make a request with traffic distribution."""
        endpoint = self.get_endpoint_for_request()
        url = f"{endpoint}{path}"
        
        start_time = time.time()
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, **kwargs)
            elif method.upper() == 'POST':
                response = requests.post(url, **kwargs)
            elif method.upper() == 'PUT':
                response = requests.put(url, **kwargs)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            end_time = time.time()
            
            return {
                'endpoint': endpoint,
                'url': url,
                'method': method,
                'status_code': response.status_code,
                'response_time': (end_time - start_time) * 1000,
                'success': response.status_code < 400,
                'response_data': response.text,
                'headers': dict(response.headers),
                'error': None
            }
            
        except requests.RequestException as e:
            end_time = time.time()
            return {
                'endpoint': endpoint,
                'url': url,
                'method': method,
                'status_code': None,
                'response_time': (end_time - start_time) * 1000,
                'success': False,
                'response_data': None,
                'headers': {},
                'error': str(e)
            }
    
    def load_test(self, path: str, num_requests: int = 100, concurrency: int = 10) -> Dict[str, Any]:
        """Perform load testing with traffic distribution."""
        print(f"🔄 Load testing with {num_requests} requests (concurrency: {concurrency})")
        print(f"Traffic split: {100 - self.traffic_split}% prod, {self.traffic_split}% canary")
        
        results = []
        
        def make_test_request():
            return self.make_request(path, timeout=10)
        
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(make_test_request) for _ in range(num_requests)]
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        'success': False,
                        'error': str(e),
                        'response_time': None,
                        'endpoint': 'unknown'
                    })
        
        # Analyze results by endpoint
        prod_results = [r for r in results if self.prod_endpoint in r.get('endpoint', '')]
        canary_results = [r for r in results if self.canary_endpoint in r.get('endpoint', '')]
        
        def analyze_endpoint_results(endpoint_results: List[Dict], endpoint_name: str) -> Dict:
            if not endpoint_results:
                return {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'success_rate': 0,
                    'avg_response_time': 0,
                    'min_response_time': 0,
                    'max_response_time': 0,
                    'p95_response_time': 0
                }
                
            successful = [r for r in endpoint_results if r['success']]
            failed = [r for r in endpoint_results if not r['success']]
            response_times = [r['response_time'] for r in successful if r['response_time']]
            
            return {
                'total_requests': len(endpoint_results),
                'successful_requests': len(successful),
                'failed_requests': len(failed),
                'success_rate': len(successful) / len(endpoint_results) * 100,
                'avg_response_time': statistics.mean(response_times) if response_times else 0,
                'min_response_time': min(response_times) if response_times else 0,
                'max_response_time': max(response_times) if response_times else 0,
                'p95_response_time': statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0
            }
        
        prod_analysis = analyze_endpoint_results(prod_results, 'production')
        canary_analysis = analyze_endpoint_results(canary_results, 'canary')
        
        # Overall analysis
        all_successful = [r for r in results if r['success']]
        all_response_times = [r['response_time'] for r in all_successful if r['response_time']]
        
        overall_analysis = {
            'total_requests': num_requests,
            'successful_requests': len(all_successful),
            'failed_requests': num_requests - len(all_successful),
            'success_rate': len(all_successful) / num_requests * 100,
            'avg_response_time': statistics.mean(all_response_times) if all_response_times else 0,
            'traffic_distribution': {
                'production_requests': len(prod_results),
                'canary_requests': len(canary_results),
                'production_percentage': len(prod_results) / num_requests * 100,
                'canary_percentage': len(canary_results) / num_requests * 100
            },
            'production_metrics': prod_analysis,
            'canary_metrics': canary_analysis
        }
        
        return overall_analysis
    
    def compare_implementations(self, path: str, num_requests: int = 50) -> Dict[str, Any]:
        """Compare performance between production and canary implementations."""
        print(f"🔄 Comparing implementations with {num_requests} requests each")
        
        # Test production endpoint
        print("Testing production endpoint...")
        prod_results = []
        for _ in range(num_requests):
            result = self.make_request(path, timeout=10)
            # Force production endpoint
            result['endpoint'] = self.prod_endpoint
            result['url'] = f"{self.prod_endpoint}{path}"
            try:
                response = requests.get(result['url'], timeout=10)
                result['status_code'] = response.status_code
                result['success'] = response.status_code < 400
                result['response_data'] = response.text
            except:
                result['success'] = False
            prod_results.append(result)
        
        # Test canary endpoint
        print("Testing canary endpoint...")
        canary_results = []
        for _ in range(num_requests):
            result = self.make_request(path, timeout=10)
            # Force canary endpoint
            result['endpoint'] = self.canary_endpoint
            result['url'] = f"{self.canary_endpoint}{path}"
            try:
                response = requests.get(result['url'], timeout=10)
                result['status_code'] = response.status_code
                result['success'] = response.status_code < 400
                result['response_data'] = response.text
            except:
                result['success'] = False
            canary_results.append(result)
        
        def analyze_results(results: List[Dict], name: str) -> Dict:
            successful = [r for r in results if r['success']]
            response_times = [r['response_time'] for r in successful if r['response_time']]
            
            return {
                'name': name,
                'total_requests': len(results),
                'successful_requests': len(successful),
                'success_rate': len(successful) / len(results) * 100,
                'avg_response_time': statistics.mean(response_times) if response_times else 0,
                'min_response_time': min(response_times) if response_times else 0,
                'max_response_time': max(response_times) if response_times else 0,
                'p95_response_time': statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0
            }
        
        prod_analysis = analyze_results(prod_results, 'Production')
        canary_analysis = analyze_results(canary_results, 'Canary')
        
        # Performance comparison
        comparison = {
            'production': prod_analysis,
            'canary': canary_analysis,
            'comparison': {
                'success_rate_diff': canary_analysis['success_rate'] - prod_analysis['success_rate'],
                'avg_response_time_diff': canary_analysis['avg_response_time'] - prod_analysis['avg_response_time'],
                'canary_faster': canary_analysis['avg_response_time'] < prod_analysis['avg_response_time'],
                'canary_more_reliable': canary_analysis['success_rate'] > prod_analysis['success_rate']
            }
        }
        
        return comparison
    
    def update_traffic_split(self, new_split: int) -> None:
        """Update the traffic split percentage."""
        if 0 <= new_split <= 100:
            self.traffic_split = new_split
            print(f"Updated traffic split to {new_split}% canary")
        else:
            raise ValueError("Traffic split must be between 0 and 100")


def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description='REST API traffic distribution for canary deployment')
    parser.add_argument('--prod-endpoint', required=True, help='Production endpoint URL')
    parser.add_argument('--canary-endpoint', required=True, help='Canary endpoint URL')
    parser.add_argument('--traffic-split', type=int, default=10, help='Percentage of traffic to canary (default: 10)')
    parser.add_argument('--path', default='/share/test-token', help='API path to test (default: /share/test-token)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Load test command
    load_parser = subparsers.add_parser('load-test', help='Run load test with traffic distribution')
    load_parser.add_argument('--requests', type=int, default=100, help='Number of requests (default: 100)')
    load_parser.add_argument('--concurrency', type=int, default=10, help='Concurrent requests (default: 10)')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare production vs canary performance')
    compare_parser.add_argument('--requests', type=int, default=50, help='Number of requests per endpoint (default: 50)')
    
    # Single request command
    subparsers.add_parser('request', help='Make a single request with traffic distribution')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    distributor = RestApiTrafficDistributor(
        args.prod_endpoint,
        args.canary_endpoint,
        args.traffic_split
    )
    
    if args.command == 'load-test':
        results = distributor.load_test(args.path, args.requests, args.concurrency)
        
        print(f"\n📊 Load Test Results:")
        print(f"Total Requests: {results['total_requests']}")
        print(f"Success Rate: {results['success_rate']:.1f}%")
        print(f"Average Response Time: {results['avg_response_time']:.2f}ms")
        
        print(f"\n🚦 Traffic Distribution:")
        dist = results['traffic_distribution']
        print(f"Production: {dist['production_requests']} requests ({dist['production_percentage']:.1f}%)")
        print(f"Canary: {dist['canary_requests']} requests ({dist['canary_percentage']:.1f}%)")
        
        print(f"\n📈 Production Metrics:")
        prod = results['production_metrics']
        print(f"Success Rate: {prod['success_rate']:.1f}%")
        print(f"Avg Response Time: {prod['avg_response_time']:.2f}ms")
        
        print(f"\n🧪 Canary Metrics:")
        canary = results['canary_metrics']
        print(f"Success Rate: {canary['success_rate']:.1f}%")
        print(f"Avg Response Time: {canary['avg_response_time']:.2f}ms")
        
    elif args.command == 'compare':
        results = distributor.compare_implementations(args.path, args.requests)
        
        print(f"\n📊 Implementation Comparison:")
        
        prod = results['production']
        canary = results['canary']
        comp = results['comparison']
        
        print(f"\n🏭 Production:")
        print(f"Success Rate: {prod['success_rate']:.1f}%")
        print(f"Avg Response Time: {prod['avg_response_time']:.2f}ms")
        print(f"P95 Response Time: {prod['p95_response_time']:.2f}ms")
        
        print(f"\n🧪 Canary:")
        print(f"Success Rate: {canary['success_rate']:.1f}%")
        print(f"Avg Response Time: {canary['avg_response_time']:.2f}ms")
        print(f"P95 Response Time: {canary['p95_response_time']:.2f}ms")
        
        print(f"\n📈 Comparison:")
        print(f"Success Rate Difference: {comp['success_rate_diff']:+.1f}%")
        print(f"Response Time Difference: {comp['avg_response_time_diff']:+.2f}ms")
        print(f"Canary is {'faster' if comp['canary_faster'] else 'slower'}")
        print(f"Canary is {'more' if comp['canary_more_reliable'] else 'less'} reliable")
        
    elif args.command == 'request':
        result = distributor.make_request(args.path)
        
        print(f"\n📤 Single Request Result:")
        print(f"Endpoint: {result['endpoint']}")
        print(f"URL: {result['url']}")
        print(f"Status Code: {result['status_code']}")
        print(f"Response Time: {result['response_time']:.2f}ms")
        print(f"Success: {result['success']}")
        
        if result['error']:
            print(f"Error: {result['error']}")


if __name__ == '__main__':
    main()