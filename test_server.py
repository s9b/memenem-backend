#!/usr/bin/env python3
"""
Test the FastAPI server endpoints
"""

import subprocess
import time
import requests
import json
import sys
import signal
import os

def test_server_endpoints():
    server_process = None
    try:
        print("🚀 Starting FastAPI server...")
        
        # Start the server
        server_process = subprocess.Popen(
            ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )
        
        # Wait for server to start
        print("⏳ Waiting for server to start...")
        time.sleep(8)
        
        # Check if server is still running
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate()
            print(f"❌ Server failed to start!")
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            return False
            
        print("✅ Server started successfully!")
        
        # Test health endpoint
        try:
            print("\n🔍 Testing /health endpoint...")
            response = requests.get("http://localhost:8000/health", timeout=10)
            if response.status_code == 200:
                print(f"✅ Health endpoint: PASS - {response.json()}")
                health_pass = True
            else:
                print(f"❌ Health endpoint: FAIL - Status {response.status_code}")
                health_pass = False
        except Exception as e:
            print(f"❌ Health endpoint: FAIL - {str(e)}")
            health_pass = False
        
        # Test generate endpoint (look for the correct endpoint)
        try:
            print("\n🎭 Testing meme generation endpoint...")
            
            # First, let's see what endpoints are available
            try:
                docs_response = requests.get("http://localhost:8000/docs", timeout=5)
                print(f"📖 Docs endpoint available: {docs_response.status_code == 200}")
            except:
                pass
                
            # Try the generate endpoint
            generate_payload = {
                "topic": "Drake memes",
                "style": "sarcastic"
            }
            
            response = requests.post(
                "http://localhost:8000/api/v1/generate", 
                json=generate_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Generate endpoint: PASS - Generated meme: {result.get('meme_id', 'unknown')}")
                generate_pass = True
            else:
                print(f"❌ Generate endpoint: FAIL - Status {response.status_code}: {response.text}")
                generate_pass = False
                
        except Exception as e:
            print(f"❌ Generate endpoint: FAIL - {str(e)}")
            generate_pass = False
        
        # Print final report
        print("\n" + "="*60)
        print("🧪 SERVER ENDPOINT TEST REPORT")
        print("="*60)
        print(f"✅ Server Startup: PASS" if server_process.poll() is None else "❌ Server Startup: FAIL")
        print(f"✅ Health Endpoint: PASS" if health_pass else "❌ Health Endpoint: FAIL")
        print(f"✅ Generate Endpoint: PASS" if generate_pass else "❌ Generate Endpoint: FAIL")
        
        total_tests = 3
        passed_tests = sum([
            server_process.poll() is None,
            health_pass,
            generate_pass
        ])
        
        print(f"\nSUMMARY: {passed_tests}/{total_tests} endpoint tests passed")
        
        return passed_tests == total_tests
        
    finally:
        if server_process and server_process.poll() is None:
            print("\n🛑 Shutting down server...")
            server_process.terminate()
            server_process.wait(timeout=5)

if __name__ == "__main__":
    success = test_server_endpoints()
    sys.exit(0 if success else 1)