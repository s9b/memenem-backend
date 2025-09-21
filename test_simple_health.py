#!/usr/bin/env python3
"""
Simple health check test
"""

import subprocess
import time
import requests
import sys

def test_simple_health():
    server_process = None
    try:
        print("🚀 Starting minimal server test...")
        
        # Start the server
        server_process = subprocess.Popen(
            ["python", "-c", """
import sys
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok", "message": "Server is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server to start
        time.sleep(3)
        
        # Test health endpoint
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ Simple health check: PASS - {response.json()}")
                return True
            else:
                print(f"❌ Simple health check: FAIL - Status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Simple health check: FAIL - {str(e)}")
            return False
        
    finally:
        if server_process:
            server_process.terminate()
            server_process.wait(timeout=5)

if __name__ == "__main__":
    success = test_simple_health()
    sys.exit(0 if success else 1)