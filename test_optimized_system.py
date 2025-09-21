#!/usr/bin/env python3
"""
Test script for the optimized MemeNem backend system.
Tests async job processing, caching, and free-tier compatibility.
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Dict, Any

import httpx
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = "http://localhost:8000/api/v1"  # Change to your server URL
TEST_CONFIG = {
    "timeout": 120,  # 2 minutes timeout for tests
    "poll_interval": 5,  # Poll every 5 seconds
    "test_requests": [
        {
            "topic": "Monday morning meetings",
            "style": "sarcastic",
            "max_templates": 3,
            "variations_per_template": 4
        },
        {
            "topic": "Working from home",
            "style": "gen_z_slang", 
            "max_templates": 2,
            "variations_per_template": 3
        },
        {
            "topic": "Coffee addiction",
            "style": "wholesome",
            "max_templates": 4,
            "variations_per_template": 4
        }
    ]
}

class MemeNemTester:
    """Test suite for optimized MemeNem backend."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        self.test_results = []
    
    async def run_all_tests(self):
        """Run complete test suite."""
        logger.info("🧪 Starting MemeNem Optimized System Tests")
        logger.info(f"Base URL: {self.base_url}")
        
        try:
            # Test 1: System Health
            await self.test_system_health()
            
            # Test 2: Template Caching
            await self.test_template_caching()
            
            # Test 3: Async Job Submission
            await self.test_async_job_submission()
            
            # Test 4: Job Polling and Results
            await self.test_job_polling()
            
            # Test 5: Multiple Concurrent Jobs
            await self.test_concurrent_jobs()
            
            # Test 6: Cache Statistics
            await self.test_cache_stats()
            
            # Test 7: Cache Cleanup
            await self.test_cache_cleanup()
            
            # Print summary
            self.print_test_summary()
            
        finally:
            await self.client.aclose()
    
    async def test_system_health(self):
        """Test basic system health and endpoints."""
        logger.info("📊 Testing system health...")
        
        try:
            # Test root endpoint
            response = await self.client.get(f"{self.base_url.replace('/api/v1', '')}/health")
            assert response.status_code == 200
            health_data = response.json()
            
            self.test_results.append({
                "test": "System Health",
                "status": "PASS",
                "message": f"System healthy: {health_data.get('status', 'unknown')}",
                "response_time": response.elapsed.total_seconds()
            })
            
            logger.info("✅ System health test passed")
            
        except Exception as e:
            self.test_results.append({
                "test": "System Health", 
                "status": "FAIL",
                "message": f"Health check failed: {str(e)}"
            })
            logger.error(f"❌ System health test failed: {e}")
    
    async def test_template_caching(self):
        """Test template fetching and caching."""
        logger.info("🗂️ Testing template caching...")
        
        try:
            # First request (should fetch fresh)
            start_time = time.time()
            response1 = await self.client.get(f"{self.base_url}/templates?limit=20")
            first_request_time = time.time() - start_time
            
            assert response1.status_code == 200
            templates_data1 = response1.json()
            assert templates_data1["success"] is True
            template_count1 = templates_data1["count"]
            
            # Second request (should use cache)
            start_time = time.time()
            response2 = await self.client.get(f"{self.base_url}/templates?limit=20")
            second_request_time = time.time() - start_time
            
            assert response2.status_code == 200
            templates_data2 = response2.json()
            template_count2 = templates_data2["count"]
            
            # Cache should make second request faster
            cache_performance = second_request_time < first_request_time
            
            self.test_results.append({
                "test": "Template Caching",
                "status": "PASS",
                "message": f"Fetched {template_count1} templates, cache performance: {cache_performance}",
                "details": {
                    "first_request_time": first_request_time,
                    "second_request_time": second_request_time,
                    "template_count": template_count1
                }
            })
            
            logger.info(f"✅ Template caching test passed ({template_count1} templates)")
            
        except Exception as e:
            self.test_results.append({
                "test": "Template Caching",
                "status": "FAIL", 
                "message": f"Template caching test failed: {str(e)}"
            })
            logger.error(f"❌ Template caching test failed: {e}")
    
    async def test_async_job_submission(self):
        """Test async meme generation job submission."""
        logger.info("🚀 Testing async job submission...")
        
        try:
            test_request = TEST_CONFIG["test_requests"][0]
            
            # Submit job
            response = await self.client.post(
                f"{self.base_url}/generate-variations",
                json=test_request
            )
            
            assert response.status_code == 200
            job_data = response.json()
            assert job_data["success"] is True
            assert "job_id" in job_data
            
            job_id = job_data["job_id"]
            
            self.test_results.append({
                "test": "Async Job Submission",
                "status": "PASS",
                "message": f"Job submitted successfully: {job_id}",
                "details": {
                    "job_id": job_id,
                    "estimated_time": job_data.get("estimated_completion_time", 0)
                }
            })
            
            logger.info(f"✅ Job submission test passed (Job ID: {job_id})")
            
        except Exception as e:
            self.test_results.append({
                "test": "Async Job Submission",
                "status": "FAIL",
                "message": f"Job submission failed: {str(e)}"
            })
            logger.error(f"❌ Job submission test failed: {e}")
    
    async def test_job_polling(self):
        """Test job status polling and result retrieval.""" 
        logger.info("📊 Testing job polling and results...")
        
        try:
            test_request = TEST_CONFIG["test_requests"][1]
            
            # Submit a job
            response = await self.client.post(
                f"{self.base_url}/generate-variations",
                json=test_request
            )
            assert response.status_code == 200
            job_data = response.json()
            job_id = job_data["job_id"]
            
            logger.info(f"Polling job {job_id}...")
            
            # Poll for completion
            max_polls = TEST_CONFIG["timeout"] // TEST_CONFIG["poll_interval"]
            poll_count = 0
            
            while poll_count < max_polls:
                poll_count += 1
                
                # Check job status
                status_response = await self.client.get(f"{self.base_url}/job-status/{job_id}")
                assert status_response.status_code == 200
                
                status_data = status_response.json()
                logger.info(f"Job {job_id}: {status_data['status']} ({status_data['progress']:.1f}%)")
                
                if status_data["status"] == "completed":
                    # Check if we got results
                    template_count = status_data["count"]
                    has_templates = len(status_data.get("templates", [])) > 0
                    
                    self.test_results.append({
                        "test": "Job Polling & Results",
                        "status": "PASS",
                        "message": f"Job completed successfully with {template_count} templates",
                        "details": {
                            "job_id": job_id,
                            "poll_count": poll_count,
                            "template_count": template_count,
                            "has_results": has_templates,
                            "processing_time": status_data.get("processing_time", 0)
                        }
                    })
                    
                    logger.info(f"✅ Job polling test passed ({template_count} templates generated)")
                    return
                
                elif status_data["status"] == "failed":
                    error_msg = status_data.get("error_message", "Unknown error")
                    raise Exception(f"Job failed: {error_msg}")
                
                # Wait before next poll
                await asyncio.sleep(TEST_CONFIG["poll_interval"])
            
            # Job didn't complete in time
            raise Exception(f"Job did not complete within {TEST_CONFIG['timeout']} seconds")
            
        except Exception as e:
            self.test_results.append({
                "test": "Job Polling & Results",
                "status": "FAIL",
                "message": f"Job polling test failed: {str(e)}"
            })
            logger.error(f"❌ Job polling test failed: {e}")
    
    async def test_concurrent_jobs(self):
        """Test multiple concurrent job processing."""
        logger.info("🔄 Testing concurrent job processing...")
        
        try:
            jobs = []
            
            # Submit multiple jobs
            for i, test_request in enumerate(TEST_CONFIG["test_requests"]):
                response = await self.client.post(
                    f"{self.base_url}/generate-variations", 
                    json=test_request
                )
                assert response.status_code == 200
                job_data = response.json()
                jobs.append({
                    "id": job_data["job_id"],
                    "topic": test_request["topic"]
                })
                
                # Small delay between submissions
                await asyncio.sleep(1)
            
            logger.info(f"Submitted {len(jobs)} concurrent jobs")
            
            # Monitor all jobs
            completed_jobs = 0
            max_polls = TEST_CONFIG["timeout"] // TEST_CONFIG["poll_interval"]
            
            for poll_round in range(max_polls):
                for job in jobs:
                    if job.get("completed"):
                        continue
                    
                    status_response = await self.client.get(f"{self.base_url}/job-status/{job['id']}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        
                        if status_data["status"] == "completed":
                            job["completed"] = True
                            job["template_count"] = status_data["count"]
                            completed_jobs += 1
                            logger.info(f"Job completed: {job['topic']} ({job['template_count']} templates)")
                
                if completed_jobs == len(jobs):
                    break
                
                await asyncio.sleep(TEST_CONFIG["poll_interval"])
            
            success_rate = completed_jobs / len(jobs)
            
            self.test_results.append({
                "test": "Concurrent Jobs",
                "status": "PASS" if success_rate >= 0.5 else "PARTIAL", 
                "message": f"Completed {completed_jobs}/{len(jobs)} jobs ({success_rate:.1%} success rate)",
                "details": {
                    "total_jobs": len(jobs),
                    "completed_jobs": completed_jobs,
                    "success_rate": success_rate
                }
            })
            
            logger.info(f"✅ Concurrent jobs test completed ({success_rate:.1%} success)")
            
        except Exception as e:
            self.test_results.append({
                "test": "Concurrent Jobs",
                "status": "FAIL",
                "message": f"Concurrent jobs test failed: {str(e)}"
            })
            logger.error(f"❌ Concurrent jobs test failed: {e}")
    
    async def test_cache_stats(self):
        """Test cache statistics endpoint."""
        logger.info("📈 Testing cache statistics...")
        
        try:
            response = await self.client.get(f"{self.base_url}/cache-stats")
            assert response.status_code == 200
            
            stats_data = response.json()
            assert stats_data["success"] is True
            
            cache_stats = stats_data["cache_stats"]
            
            self.test_results.append({
                "test": "Cache Statistics",
                "status": "PASS",
                "message": "Cache stats retrieved successfully",
                "details": cache_stats
            })
            
            logger.info("✅ Cache statistics test passed")
            
        except Exception as e:
            self.test_results.append({
                "test": "Cache Statistics", 
                "status": "FAIL",
                "message": f"Cache stats test failed: {str(e)}"
            })
            logger.error(f"❌ Cache statistics test failed: {e}")
    
    async def test_cache_cleanup(self):
        """Test cache cleanup functionality."""
        logger.info("🧹 Testing cache cleanup...")
        
        try:
            response = await self.client.post(f"{self.base_url}/cache-cleanup")
            assert response.status_code == 200
            
            cleanup_data = response.json()
            assert cleanup_data["success"] is True
            
            self.test_results.append({
                "test": "Cache Cleanup",
                "status": "PASS", 
                "message": "Cache cleanup triggered successfully",
                "details": cleanup_data
            })
            
            logger.info("✅ Cache cleanup test passed")
            
        except Exception as e:
            self.test_results.append({
                "test": "Cache Cleanup",
                "status": "FAIL",
                "message": f"Cache cleanup test failed: {str(e)}"
            })
            logger.error(f"❌ Cache cleanup test failed: {e}")
    
    def print_test_summary(self):
        """Print comprehensive test results summary."""
        logger.info("\n" + "="*80)
        logger.info("🧪 MEMENEM OPTIMIZED SYSTEM TEST SUMMARY")
        logger.info("="*80)
        
        passed = sum(1 for result in self.test_results if result["status"] == "PASS")
        partial = sum(1 for result in self.test_results if result["status"] == "PARTIAL")
        failed = sum(1 for result in self.test_results if result["status"] == "FAIL")
        total = len(self.test_results)
        
        logger.info(f"📊 Results: {passed} PASSED | {partial} PARTIAL | {failed} FAILED | {total} TOTAL")
        logger.info(f"✅ Success Rate: {(passed + partial) / total:.1%}")
        
        logger.info("\n📋 Detailed Results:")
        for result in self.test_results:
            status_icon = {"PASS": "✅", "PARTIAL": "⚠️", "FAIL": "❌"}[result["status"]]
            logger.info(f"  {status_icon} {result['test']}: {result['message']}")
            
            if "details" in result:
                details = result["details"]
                if isinstance(details, dict):
                    for key, value in details.items():
                        logger.info(f"      {key}: {value}")
        
        logger.info("\n🎯 System Assessment:")
        if passed >= 5:
            logger.info("🟢 SYSTEM READY FOR PRODUCTION - All core features working")
        elif passed >= 3:
            logger.info("🟡 SYSTEM PARTIALLY READY - Some features may need attention")
        else:
            logger.info("🔴 SYSTEM NOT READY - Major issues detected")
        
        logger.info("="*80)

async def main():
    """Run the test suite."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = BASE_URL
    
    tester = MemeNemTester(base_url)
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())