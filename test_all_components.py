#!/usr/bin/env python3
"""
MemeNem Backend Component Test Suite
Tests all APIs, database connection, and environment variables
"""

import os
import sys
import asyncio
import json
from typing import Dict, Any
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Import required modules
try:
    from dotenv import load_dotenv
    import motor.motor_asyncio
    import praw
    import requests
    import google.generativeai as genai
    from loguru import logger
except ImportError as e:
    print(f"❌ IMPORT ERROR: {e}")
    print("Please install missing dependencies with: pip install -r requirements.txt")
    sys.exit(1)

# Load environment variables
load_dotenv()

class ComponentTester:
    def __init__(self):
        self.results = {}
        self.mongodb_client = None
        
    def log_test(self, component: str, status: str, message: str, details: Any = None):
        """Log test results"""
        self.results[component] = {
            "status": status,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        status_icon = "✅" if status == "PASS" else "❌"
        print(f"{status_icon} {component}: {message}")
        if details and status == "FAIL":
            print(f"   Details: {details}")

    def test_environment_variables(self) -> bool:
        """Test that all required environment variables are loaded"""
        print("\n🔧 Testing Environment Variables...")
        
        required_vars = [
            'GEMINI_API_KEY', 'REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 
            'REDDIT_USER_AGENT', 'IMGFLIP_API_USERNAME', 'IMGFLIP_API_PASSWORD', 
            'MONGODB_URI'
        ]
        
        missing_vars = []
        loaded_vars = []
        
        for var in required_vars:
            value = os.getenv(var)
            if not value or value.startswith('your_') or value == '':
                missing_vars.append(var)
            else:
                loaded_vars.append(var)
        
        if missing_vars:
            self.log_test("Environment Variables", "FAIL", 
                         f"Missing or placeholder values: {', '.join(missing_vars)}", 
                         missing_vars)
            return False
        else:
            self.log_test("Environment Variables", "PASS", 
                         f"All {len(required_vars)} variables loaded successfully",
                         loaded_vars)
            return True

    async def test_mongodb_connection(self) -> bool:
        """Test MongoDB connection and database access"""
        print("\n🗄️ Testing MongoDB Connection...")
        
        try:
            mongodb_uri = os.getenv('MONGODB_URI')
            if not mongodb_uri:
                self.log_test("MongoDB Connection", "FAIL", "MONGODB_URI not set")
                return False

            # Create MongoDB client
            self.mongodb_client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_uri)
            
            # Test connection
            await self.mongodb_client.admin.command('ping')
            
            # Check database and collections
            db = self.mongodb_client['memenem']
            collections = await db.list_collection_names()
            
            # Try to access templates and memes collections
            templates_count = await db.templates.count_documents({})
            memes_count = await db.memes.count_documents({})
            
            self.log_test("MongoDB Connection", "PASS", 
                         f"Connected successfully. Collections: {collections}, Templates: {templates_count}, Memes: {memes_count}",
                         {"collections": collections, "templates": templates_count, "memes": memes_count})
            return True
            
        except Exception as e:
            self.log_test("MongoDB Connection", "FAIL", f"Connection failed: {str(e)}", str(e))
            return False

    def test_gemini_api(self) -> bool:
        """Test Gemini API for caption generation"""
        print("\n🤖 Testing Gemini API...")
        
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                self.log_test("Gemini API", "FAIL", "GEMINI_API_KEY not set")
                return False

            # Configure Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Test caption generation
            prompt = """Generate a funny meme caption for the topic "Drake memes". 
                       Make it sarcastic and relatable. Keep it under 50 characters.
                       Return only the caption text, nothing else."""
            
            response = model.generate_content(prompt)
            caption = response.text.strip()
            
            if caption and len(caption) > 0:
                self.log_test("Gemini API", "PASS", 
                             f"Caption generated successfully: '{caption}'",
                             {"caption": caption, "length": len(caption)})
                return True
            else:
                self.log_test("Gemini API", "FAIL", "Empty response from Gemini")
                return False
                
        except Exception as e:
            self.log_test("Gemini API", "FAIL", f"API call failed: {str(e)}", str(e))
            return False

    def test_reddit_api(self) -> bool:
        """Test Reddit API for fetching trending meme templates"""
        print("\n🔥 Testing Reddit API...")
        
        try:
            client_id = os.getenv('REDDIT_CLIENT_ID')
            client_secret = os.getenv('REDDIT_CLIENT_SECRET')
            user_agent = os.getenv('REDDIT_USER_AGENT')
            
            if not all([client_id, client_secret, user_agent]):
                self.log_test("Reddit API", "FAIL", "Missing Reddit API credentials")
                return False

            # Initialize Reddit client
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
            
            # Test API access
            subreddit = reddit.subreddit('memes')
            hot_posts = list(subreddit.hot(limit=1))
            
            if hot_posts:
                post = hot_posts[0]
                self.log_test("Reddit API", "PASS", 
                             f"Fetched trending post: '{post.title[:50]}...'",
                             {"title": post.title, "score": post.score, "url": post.url})
                return True
            else:
                self.log_test("Reddit API", "FAIL", "No posts retrieved from Reddit")
                return False
                
        except Exception as e:
            self.log_test("Reddit API", "FAIL", f"API call failed: {str(e)}", str(e))
            return False

    def test_imgflip_api(self) -> bool:
        """Test Imgflip API for fetching meme templates"""
        print("\n🖼️ Testing Imgflip API...")
        
        try:
            username = os.getenv('IMGFLIP_API_USERNAME')
            password = os.getenv('IMGFLIP_API_PASSWORD')
            
            if not all([username, password]):
                self.log_test("Imgflip API", "FAIL", "Missing Imgflip API credentials")
                return False

            # Test Imgflip API
            url = "https://api.imgflip.com/get_memes"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data', {}).get('memes'):
                    templates = data['data']['memes'][:1]  # Get first template
                    template = templates[0]
                    
                    self.log_test("Imgflip API", "PASS", 
                                 f"Fetched template: '{template['name']}'",
                                 {"name": template['name'], "id": template['id'], "url": template['url']})
                    return True
                else:
                    self.log_test("Imgflip API", "FAIL", "API returned unsuccessful response", data)
                    return False
            else:
                self.log_test("Imgflip API", "FAIL", f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Imgflip API", "FAIL", f"API call failed: {str(e)}", str(e))
            return False

    async def cleanup(self):
        """Clean up resources"""
        if self.mongodb_client:
            self.mongodb_client.close()

    def print_final_report(self):
        """Print final test report"""
        print("\n" + "="*60)
        print("🧪 MEMENEM BACKEND TEST REPORT")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r['status'] == 'PASS')
        failed_tests = total_tests - passed_tests
        
        for component, result in self.results.items():
            status_icon = "✅" if result['status'] == 'PASS' else "❌"
            print(f"{status_icon} {component}: {result['status']}")
            if result['status'] == 'FAIL':
                print(f"   Error: {result['message']}")
        
        print(f"\nSUMMARY: {passed_tests}/{total_tests} tests passed")
        
        if failed_tests == 0:
            print("🎉 ALL TESTS PASSED! Your MemeNem backend is ready to run.")
        else:
            print(f"⚠️ {failed_tests} test(s) failed. Please fix the issues before proceeding.")
            
        return failed_tests == 0

async def main():
    """Run all tests"""
    print("🚀 Starting MemeNem Backend Component Tests...")
    print("="*60)
    
    tester = ComponentTester()
    
    try:
        # Run all tests
        env_ok = tester.test_environment_variables()
        mongo_ok = await tester.test_mongodb_connection()
        gemini_ok = tester.test_gemini_api()
        reddit_ok = tester.test_reddit_api()
        imgflip_ok = tester.test_imgflip_api()
        
        # Print final report
        all_passed = tester.print_final_report()
        
        return all_passed
        
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)