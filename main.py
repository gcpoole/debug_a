"""App A: Request Chain Tracer

Simple FastAPI app that receives requests, calls App B, and returns both:
1. What App A received (external request info)
2. What App B saw (internal VPC request info)

Used to compare external vs internal request headers and IPs.
"""

import os
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
async def call_b(request: Request) -> Dict[str, Any]:
    """Receive external request, call App B internally, return both results.

    This endpoint:
    1. Captures what App A received from external caller
    2. Makes internal VPC call to App B
    3. Returns both sets of information for comparison

    This allows us to see the difference between:
    - External request (browser/curl → App A through load balancer)
    - Internal request (App A → App B within VPC)
    """
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
            response = await client.get(f"{APP_B_URL}/diagnostic", timeout=10.0)
            app_b_response = response.json()
            call_success = True
            error_message = None
    except Exception as e:
        app_b_response = None
        call_success = False
        error_message = str(e)

    return {
        "test_description": "External request to App A, which then calls App B internally",
        "app_a_received": {
            "description": "What App A saw from external caller (through load balancer)",
            "client_ip": app_a_client_ip,
            "specific_headers": app_a_specific,
            "all_headers": app_a_headers,
        },
        "internal_call_to_app_b": {
            "description": "App A called App B using internal VPC URL",
            "url_used": APP_B_URL,
            "call_success": call_success,
            "error": error_message,
        },
        "app_b_response": {
            "description": "What App B saw when App A called it (internal VPC request)",
            "data": app_b_response,
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint for Digital Ocean."""
    return {"status": "healthy"}
