"""
Async job management routes for optimized meme generation.
Handles job submission, status checking, and result polling for Render free tier.
"""

import time
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime

# Import schemas and utilities
from app.models.schemas import (
    JobRequest, JobSubmissionResponse, JobResultResponse, JobStatus,
    HUMOR_STYLES, JOB_STATUS, ErrorResponse
)
from app.utils.cache_manager import cache_manager
from app.utils.batch_processor import batch_processor

logger = logging.getLogger(__name__)

# Create router for async meme generation
async_router = APIRouter()

@async_router.post("/generate-variations-async", response_model=JobSubmissionResponse)
async def submit_meme_generation_job(
    request: JobRequest, 
    background_tasks: BackgroundTasks
):
    """
    Submit async meme generation job with batching and caching.
    Returns job ID for polling results.
    
    This endpoint immediately returns a job ID and processes memes in the background,
    optimized for Render free tier with proper memory management and rate limiting.
    """
    try:
        start_time = time.time()
        logger.info(f"Submitting async job: topic='{request.topic}', style='{request.style}', max_templates={request.max_templates}")
        
        # Validate humor style
        if request.style not in HUMOR_STYLES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid humor style. Must be one of: {HUMOR_STYLES}"
            )
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create initial job status in database
        success = await cache_manager.create_job_status(
            job_id=job_id,
            topic=request.topic,
            style=request.style,
            max_templates=request.max_templates,
            variations_per_template=request.variations_per_template
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to create job status. Please try again."
            )
        
        # Schedule background processing
        background_tasks.add_task(
            batch_processor.process_meme_generation_job,
            job_id=job_id,
            topic=request.topic,
            style=request.style,
            max_templates=request.max_templates,
            variations_per_template=request.variations_per_template,
            template_id=request.template_id
        )
        
        # Schedule cache cleanup
        background_tasks.add_task(cache_manager.cleanup_expired_cache)
        
        # Estimate completion time
        estimated_time = batch_processor.get_estimated_completion_time(
            request.max_templates, 
            request.variations_per_template
        )
        
        submission_time = time.time() - start_time
        logger.info(f"Job {job_id} submitted in {submission_time:.2f}s, estimated completion: {estimated_time}s")
        
        return JobSubmissionResponse(
            success=True,
            job_id=job_id,
            status=JOB_STATUS["QUEUED"],
            estimated_completion_time=estimated_time,
            message=f"Job submitted successfully. Use job ID '{job_id}' to check status and retrieve results."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting meme generation job: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit job: {str(e)}"
        )

@async_router.get("/job-status/{job_id}", response_model=JobResultResponse)
async def get_job_status(job_id: str):
    """
    Get job status and results if completed.
    Frontend can poll this endpoint to check progress and retrieve results.
    """
    try:
        logger.info(f"Checking status for job: {job_id}")
        
        # Get job status from cache
        job_data = await cache_manager.get_job_status(job_id)
        
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail=f"Job not found: {job_id}"
            )
        
        # Prepare base response
        response_data = {
            "success": True,
            "job_id": job_id,
            "status": job_data.get("status", "unknown"),
            "progress": job_data.get("progress", 0.0),
            "templates": [],
            "count": 0
        }
        
        # Add error message if failed
        if job_data.get("error_message"):
            response_data["error_message"] = job_data["error_message"]
        
        # If completed, try to get results
        if job_data.get("status") == JOB_STATUS["COMPLETED"]:
            # Check for cached results
            cached_results = await cache_manager.get_cached_job_results(job_id)
            
            if cached_results:
                templates, count = cached_results
                response_data["templates"] = templates
                response_data["count"] = count
                response_data["completed_at"] = job_data.get("completed_at")
                
                # Calculate processing time if available
                if job_data.get("completed_at") and job_data.get("created_at"):
                    created_at = job_data["created_at"]
                    completed_at = job_data["completed_at"]
                    if isinstance(created_at, datetime) and isinstance(completed_at, datetime):
                        processing_time = (completed_at - created_at).total_seconds()
                        response_data["processing_time"] = processing_time
            else:
                # Results expired or not found
                response_data["error_message"] = "Results have expired. Please submit a new job."
                response_data["status"] = JOB_STATUS["FAILED"]
        
        logger.info(f"Job {job_id} status: {response_data['status']} ({response_data['progress']:.1f}%)")
        
        return JobResultResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job status: {str(e)}"
        )

@async_router.get("/jobs", response_model=list[JobStatus])
async def list_recent_jobs(limit: int = 10):
    """
    List recent jobs for debugging/monitoring purposes.
    Limited to prevent database overload on free tier.
    """
    try:
        if limit > 20:  # Prevent large queries
            limit = 20
            
        # Get recent jobs from database
        db = cache_manager._get_database()
        jobs_collection = db.job_status
        
        cursor = jobs_collection.find({}).sort("created_at", -1).limit(limit)
        job_docs = await cursor.to_list(length=limit)
        
        jobs = []
        for doc in job_docs:
            doc.pop("_id", None)
            job_status = JobStatus(
                job_id=doc["job_id"],
                status=doc["status"],
                progress=doc.get("progress", 0.0),
                created_at=doc["created_at"],
                updated_at=doc["updated_at"],
                total_templates=doc.get("total_templates"),
                completed_templates=doc.get("completed_templates"),
                error_message=doc.get("error_message")
            )
            jobs.append(job_status)
        
        return jobs
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list jobs: {str(e)}"
        )

@async_router.delete("/job/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel a job (marks as cancelled, doesn't stop processing).
    Used for cleanup purposes.
    """
    try:
        success = await cache_manager.update_job_status(
            job_id, 
            status=JOB_STATUS["CANCELLED"]
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Job not found: {job_id}"
            )
        
        return {"success": True, "message": f"Job {job_id} marked as cancelled"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel job: {str(e)}"
        )

@async_router.get("/cache-stats")
async def get_cache_statistics():
    """
    Get cache statistics for monitoring and optimization.
    """
    try:
        db = cache_manager._get_database()
        
        stats = {}
        
        # Templates cache stats
        templates_count = await db.templates.count_documents({})
        stats["templates"] = {
            "total": templates_count,
            "sources": await db.templates.distinct("source")
        }
        
        # Cached captions stats
        captions_count = await db.cached_captions.count_documents({})
        stats["cached_captions"] = {
            "total": captions_count
        }
        
        # Job status stats
        jobs_by_status = await db.job_status.aggregate([
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]).to_list(10)
        
        stats["jobs"] = {
            status_doc["_id"]: status_doc["count"] 
            for status_doc in jobs_by_status
        }
        
        # Results cache stats
        results_count = await db.job_results.count_documents({})
        stats["cached_results"] = {
            "total": results_count
        }
        
        return {
            "success": True,
            "cache_stats": stats,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cache statistics: {str(e)}"
        )

@async_router.post("/cache-cleanup")
async def trigger_cache_cleanup(background_tasks: BackgroundTasks):
    """
    Trigger manual cache cleanup for maintenance.
    """
    try:
        # Schedule cleanup in background
        background_tasks.add_task(cache_manager.cleanup_expired_cache)
        
        return {
            "success": True,
            "message": "Cache cleanup scheduled"
        }
        
    except Exception as e:
        logger.error(f"Error triggering cache cleanup: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger cache cleanup: {str(e)}"
        )

# Backwards compatibility endpoints for existing frontend
@async_router.post("/generate-variations", response_model=JobSubmissionResponse)
async def generate_variations_compat(
    request: JobRequest, 
    background_tasks: BackgroundTasks
):
    """
    Backwards compatible endpoint that now uses async processing.
    
    NOTE: This endpoint now returns a job ID instead of immediate results.
    Frontend should be updated to use the async pattern with job polling.
    """
    try:
        logger.info("Legacy generate-variations endpoint called, using async processing")
        
        # Use the async submission endpoint
        return await submit_meme_generation_job(request, background_tasks)
        
    except Exception as e:
        logger.error(f"Error in legacy endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {str(e)}"
        )