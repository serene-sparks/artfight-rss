#!/usr/bin/env python3
"""Test script to verify ArtFight authentication using requests."""

import os

import requests
from bs4 import BeautifulSoup

# Get cookies from environment variables
laravel_session = os.environ.get("LARAVEL_SESSION")
cf_clearance = os.environ.get("CF_CLEARANCE")

if not laravel_session or not cf_clearance:
    print("❌ Please set LARAVEL_SESSION and CF_CLEARANCE environment variables.")
    exit(1)

# Prepare cookies and headers
cookies = {
    "laravel_session": laravel_session,
    "cf_clearance": cf_clearance,
}

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-GPC": "1",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}

url = "https://artfight.net/~fourleafisland/defenses"

print(f"\n🎯 GET {url}")
with requests.Session() as session:
    response = session.get(url, headers=headers, cookies=cookies)
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
    print(f"Content-Encoding: {response.headers.get('content-encoding', 'none')}")
    print(f"Content-Length: {response.headers.get('content-length', 'unknown')}")

    if response.status_code == 200:
        print("✅ Successfully accessed attack page!")
        # requests auto-decompresses Brotli if brotli/brotlicffi is installed
        html = response.text
        if "wishing-star" in html.lower():
            print("✅ Attack content found!")
        else:
            print("⚠️  Attack content not found in response")
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string if soup.title else "(no <title>)"
        print(f"Page <title>: {title}")
        # Save for inspection
        with open("test_response.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("💾 Response saved to test_response.html")
        print(f"\n📄 Response Preview (first 500 chars):\n{'-'*50}\n{html[:500]}\n{'-'*50}")
    elif response.status_code == 404:
        print("❌ Attack not found (404)")
    elif response.status_code == 403:
        print("❌ Access forbidden (403) - authentication may be invalid")
    elif response.status_code == 302:
        print("❌ Redirected (302) - may be redirected to login")
        print(f"  Redirect location: {response.headers.get('location', 'unknown')}")
    else:
        print(f"❌ Unexpected status code: {response.status_code}")
