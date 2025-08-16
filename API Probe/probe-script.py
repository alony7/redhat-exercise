#!/usr/bin/env python3
"""
API Probe Script - Sends non-streaming requests at 1 RPS and measures latency
"""

import argparse
import csv
import json
import time
import sys
import warnings
from datetime import datetime

# Suppress SSL warnings when verify=False is used
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description='API Probe - Send requests at 1 RPS and measure latency'
    )
    
    parser.add_argument(
        '--api-url',
        required=True,
        help='Full endpoint URL (e.g., http://localhost:8000/v1/chat/completions)'
    )
    
    parser.add_argument(
        '--api-token',
        default=None,
        help='Authentication token/key (optional)'
    )
    
    parser.add_argument(
        '--prompt',
        required=True,
        help='A single text prompt to send in the request body'
    )
    
    parser.add_argument(
        '--requests',
        type=int,
        required=True,
        help='Number of requests to send'
    )
    
    parser.add_argument(
        '--rps',
        type=int,
        default=1,
        help='Requests per second (default: 1)'
    )
    
    args = parser.parse_args()
    
    # Enforce RPS = 1 for core version
    if args.rps != 1:
        print("Warning: Core version only supports RPS=1. Setting RPS to 1.")
        args.rps = 1
    
    return args


def create_request_body(prompt):
    """
    Create the request body for the API.
    Assumes OpenAI-compatible chat completions format.
    Modify this function if your API expects a different format.
    """
    return {
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False  # Explicitly set non-streaming
    }


def send_request(api_url, api_token, prompt):
    """
    Send a single non-streaming request and measure its latency.
    
    Returns:
        tuple: (start_time_str, total_time_ms, status_code)
    """
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Add authorization header if token provided
    if api_token:
        headers['Authorization'] = f'Bearer {api_token}'
    
    request_body = create_request_body(prompt)
    
    # Record start time
    start_time = time.time()
    start_time_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Format with milliseconds
    
    try:
        # Send the request (disable SSL verification for local development)
        response = requests.post(
            api_url,
            headers=headers,
            json=request_body,
            timeout=30,  # 30 second timeout
            verify=False  # Disable SSL verification for local/dev servers
        )
        
        # Record end time
        end_time = time.time()
        
        # Calculate total time in milliseconds
        total_time_ms = int((end_time - start_time) * 1000)
        
        return start_time_str, total_time_ms, response.status_code
        
    except requests.exceptions.SSLError as e:
        # Handle SSL errors specifically
        end_time = time.time()
        total_time_ms = int((end_time - start_time) * 1000)
        
        print(f"SSL Error: {str(e)[:100]}...")
        print(f"  Hint: For localhost, use http:// instead of https://")
        return start_time_str, total_time_ms, -1
        
    except requests.exceptions.ConnectionError as e:
        # Handle connection errors
        end_time = time.time()
        total_time_ms = int((end_time - start_time) * 1000)
        
        print(f"Connection Error: Cannot reach {api_url}")
        print(f"  Hint: Check if the server is running and the URL is correct")
        return start_time_str, total_time_ms, -1
        
    except requests.exceptions.Timeout:
        # Handle timeout errors
        end_time = time.time()
        total_time_ms = int((end_time - start_time) * 1000)
        
        print(f"Timeout Error: Request took longer than 30 seconds")
        return start_time_str, total_time_ms, -1
        
    except requests.exceptions.RequestException as e:
        # Handle other request errors
        end_time = time.time()
        total_time_ms = int((end_time - start_time) * 1000)
        
        print(f"Request error: {str(e)[:100]}...")
        return start_time_str, total_time_ms, -1  # -1 indicates error


def save_metrics_to_csv(metrics, filename='metrics.csv'):
    """Save collected metrics to a CSV file"""
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['request_number', 'start_time', 'total_time_ms', 'status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for metric in metrics:
            writer.writerow(metric)
    
    print(f"\nMetrics saved to {filename}")


def main():
    """Main execution function"""
    args = parse_arguments()
    
    print(f"API Probe Starting")
    print(f"================")
    print(f"API URL: {args.api_url}")
    print(f"Requests to send: {args.requests}")
    print(f"RPS: {args.rps}")
    print(f"Prompt: {args.prompt[:50]}..." if len(args.prompt) > 50 else f"Prompt: {args.prompt}")
    print()
    
    metrics = []
    interval = 1.0 / args.rps  # Time between request starts (1.0 seconds for RPS=1)
    
    # Record the absolute start time of the test
    test_start_time = time.time()
    
    for i in range(1, args.requests + 1):
        # Calculate when this request SHOULD start for consistent RPS
        scheduled_start = test_start_time + (i - 1) * interval
        
        # Wait until the scheduled start time if needed
        current_time = time.time()
        if current_time < scheduled_start:
            time.sleep(scheduled_start - current_time)
        
        # Send the request and measure latency
        start_time_str, total_time_ms, status_code = send_request(
            args.api_url,
            args.api_token,
            args.prompt
        )
        
        # Print result to console
        if status_code == -1:
            print(f"Request {i}: {total_time_ms} ms, status ERROR")
        else:
            print(f"Request {i}: {total_time_ms} ms, status {status_code}")
        
        # Store metrics
        metrics.append({
            'request_number': i,
            'start_time': start_time_str,
            'total_time_ms': total_time_ms,
            'status': status_code
        })
        
        # Note: If a request takes longer than the interval, the next request
        # will start immediately after this one finishes (maintaining best-effort RPS)
    
    # Save metrics to CSV
    save_metrics_to_csv(metrics)
    
    # Print summary statistics
    print("\nSummary Statistics")
    print("==================")
    
    valid_latencies = [m['total_time_ms'] for m in metrics if m['status'] != -1]
    
    if valid_latencies:
        avg_latency = sum(valid_latencies) / len(valid_latencies)
        min_latency = min(valid_latencies)
        max_latency = max(valid_latencies)
        
        print(f"Successful requests: {len(valid_latencies)}/{args.requests}")
        print(f"Average latency: {avg_latency:.0f} ms")
        print(f"Min latency: {min_latency} ms")
        print(f"Max latency: {max_latency} ms")
        
        # Calculate actual RPS achieved
        total_test_time = time.time() - test_start_time
        actual_rps = args.requests / total_test_time
        print(f"Target RPS: {args.rps:.1f}")
        print(f"Actual RPS: {actual_rps:.2f}")
        
        # Warn if requests are taking too long for target RPS
        if any(lat > interval * 1000 for lat in valid_latencies):
            print(f"\nWarning: Some requests took longer than {interval:.1f}s, which affects RPS")
            print(f"  Requests exceeding interval: {sum(1 for lat in valid_latencies if lat > interval * 1000)}")
    else:
        print("No successful requests completed")
    
    error_count = len([m for m in metrics if m['status'] == -1])
    if error_count > 0:
        print(f"Failed requests: {error_count}")


if __name__ == "__main__":
    main()