"""App A: Request Chain Tracer

Simple FastAPI app that receives requests, calls App B, and returns both:
1. What App A received (external request info)
2. What App B saw (internal VPC request info)

Used to compare external vs internal request headers and IPs.
"""

import os
import socket
import asyncio
import random
import httpx
from fastapi import FastAPI, Request
from typing import Dict, Any

app = FastAPI(title="VPC Test App A - Request Chain Tracer")

# Get App B URL from environment (internal VPC URL)
APP_B_URL = os.getenv("APP_B_URL", "http://test-header-b:8080")


@app.get("/")
async def root():
    """Simple hello endpoint."""
    return {
        "app": "test-header-a",
        "message": "VPC request chain tracer",
        "app_b_url": APP_B_URL,
    }


@app.get("/call-b")
async def call_b(request: Request, fib: int = None) -> Dict[str, Any]:
    """Receive external request, call App B internally, return both results.

    This endpoint:
    1. Captures what App A received from external caller
    2. Makes internal VPC call to App B
    3. Returns both sets of information for comparison

    Query params:
    - fib: Optional Fibonacci number to pass to App B for CPU load testing

    This allows us to see the difference between:
    - External request (browser/curl → App A through load balancer)
    - Internal request (App A → App B within VPC)
    """
    # Get this pod's hostname
    app_a_pod_name = socket.gethostname()

    # NO delay in app-a - it processes immediately
    app_a_delay = 0

    # Capture what App A received from external caller
    app_a_client_ip = request.client.host if request.client else "unknown"
    app_a_headers = dict(request.headers)
    app_a_specific = {
        "x-forwarded-for": request.headers.get("x-forwarded-for"),
        "x-real-ip": request.headers.get("x-real-ip"),
        "do-connecting-ip": request.headers.get("do-connecting-ip"),
        "user-agent": request.headers.get("user-agent"),
        "host": request.headers.get("host"),
    }

    # Make internal call to App B
    try:
        async with httpx.AsyncClient() as client:
            # Add fib parameter if provided
            url = f"{APP_B_URL}/diagnostic"
            params = {"fib": fib} if fib is not None else {}
            response = await client.get(url, params=params, timeout=60.0)
            app_b_response = response.json()
            call_success = True
            error_message = None
    except Exception as e:
        app_b_response = None
        call_success = False
        error_message = str(e)

    return {
        "test_description": "External request to App A, which then calls App B internally",
        "app_a_pod_name": app_a_pod_name,
        "app_a_delay_seconds": app_a_delay,
        "fib_param": fib,
        "app_a_received": {
            "description": "What App A saw from external caller (through load balancer)",
            "client_ip": app_a_client_ip,
            "specific_headers": app_a_specific,
            "all_headers": app_a_headers,
        },
        "internal_call_to_app_b": {
            "description": "App A called App B using internal VPC URL",
            "url_used": APP_B_URL,
            "fib_passed_to_b": fib,
            "call_success": call_success,
            "error": error_message,
        },
        "app_b_response": {
            "description": "What App B saw when App A called it (internal VPC request)",
            "data": app_b_response,
        },
    }


@app.get("/test-load-balancing")
async def test_load_balancing() -> Dict[str, Any]:
    """Make multiple calls to App B to test internal load balancing.

    If load balancing works, we should see different pod IPs.
    If not, all calls will go to the same pod.
    """
    results = []
    ip_counts = {}

    # Make 20 calls to App B with NEW connections each time
    for i in range(20):
        try:
            # Create new client for each request (forces new TCP connection)
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{APP_B_URL}/diagnostic", timeout=10.0)
                data = response.json()
                pod_ip = data.get("client_ip", "unknown")

                results.append({
                    "call_number": i + 1,
                    "pod_ip": pod_ip,
                    "success": True
                })

                # Count IPs
                ip_counts[pod_ip] = ip_counts.get(pod_ip, 0) + 1

        except Exception as e:
            results.append({
                "call_number": i + 1,
                "pod_ip": None,
                "success": False,
                "error": str(e)
            })

    # Analyze results
    unique_ips = len(ip_counts)
    load_balanced = unique_ips > 1

    return {
        "test_description": "Made 20 internal calls to test-header-b to check load balancing",
        "app_b_instances_expected": 2,
        "unique_pod_ips_seen": unique_ips,
        "load_balancing_working": load_balanced,
        "ip_distribution": ip_counts,
        "detailed_results": results,
        "conclusion": (
            f"✅ Load balancing IS working - saw {unique_ips} different pod IPs"
            if load_balanced
            else f"❌ Load balancing NOT working - all calls went to same pod"
        )
    }


@app.get("/health")
async def health():
    """Health check endpoint for Digital Ocean."""
    return {"status": "healthy"}
