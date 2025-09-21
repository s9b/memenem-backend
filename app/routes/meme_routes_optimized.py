"""
Optimized FastAPI routes for meme generation with lazy loading.
Components are loaded only when endpoints are first accessed.
"""

import time
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime
import uuid

# Lightweight imports only
from app.models.schemas import (
    GenerateMemeRequest, GenerateMemeResponse, GenerateMemesResponse, TemplatesResponse, TrendingMemesResponse,
    UpvoteRequest, UpvoteResponse, ViralityScoreResponse, ErrorResponse,
    Template, Meme, MemeTemplate, MemeVariation, HUMOR_STYLES,
    JobRequest, JobSubmissionResponse, JobResultResponse
)
from app.models.database import database
from app.utils.cache_manager import cache_manager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Lazy component cache (will be populated by main app)
_component_cache = {}

def get_components():
    """Get lazy-loaded components from the main app cache."""
    # Import the lazy loading function from main
    from main import get_lazy_component
    
    if "scrapers" not in _component_cache:
        _component_cache["scrapers"] = get_lazy_component("scrapers")
    
    if "ai_components" not in _component_cache:
        _component_cache["ai_components"] = get_lazy_component("ai_components")
    
    return _component_cache

@router.get("/templates", response_model=TemplatesResponse)
async def get_trending_templates(limit: int = 50, source: Optional[str] = None):
    """
    Get trending meme templates with intelligent caching.
    Optimized for memory efficiency on free tier.
    """
    try:
        logger.info(f"📄 Fetching templates (limit={limit}, source={source})")
        start_time = time.time()
        
        # Check cache first for better performance
        cached_templates = await cache_manager.get_cached_templates(source=source, limit=limit)
        
        if cached_templates:
            logger.info(f"💾 Using {len(cached_templates)} cached templates")
            templates = [Template(**template) for template in cached_templates[:limit]]
            
            return TemplatesResponse(
                success=True,
                templates=templates,
                count=len(templates)
            )
        
        # If no cache, fetch fresh templates with memory optimization
        logger.info("🔄 Fetching fresh templates with lazy loading")
        
        # Lazy load scrapers
        components = get_components()
        scrapers = components["scrapers"]
        
        all_templates = []
        
        # Fetch with optimized limits for free tier
        if source is None or source == "imgflip":
            try:
                imgflip_limit = min(30, limit)  # Reduced for memory efficiency
                imgflip_templates = await scrapers["imgflip"].get_trending_templates(imgflip_limit)
                all_templates.extend(imgflip_templates)
                logger.info(f"📥 Fetched {len(imgflip_templates)} Imgflip templates")
            except Exception as e:
                logger.warning(f"Imgflip scraping failed: {e}")
        
        if source is None or source == "reddit":
            try:
                reddit_limit = min(20, limit // 3)  # Conservative limit for Reddit API
                reddit_templates = await scrapers["reddit"].get_trending_templates(reddit_limit)
                all_templates.extend(reddit_templates)
                logger.info(f"📥 Fetched {len(reddit_templates)} Reddit templates")
            except Exception as e:
                logger.warning(f"Reddit scraping failed: {e}")
        
        # Remove duplicates and sort by popularity
        seen_ids = set()
        unique_templates = []
        for template in all_templates:
            template_id = template.get("template_id")
            if template_id and template_id not in seen_ids:
                seen_ids.add(template_id)
                unique_templates.append(template)
        
        # Sort by popularity and limit results
        unique_templates.sort(key=lambda x: x.get("popularity", 0), reverse=True)
        limited_templates = unique_templates[:limit]
        
        # Cache templates for future use
        if limited_templates:
            await cache_manager.cache_templates(limited_templates)
            logger.info(f"💾 Cached {len(limited_templates)} templates")
        
        # Convert to response format
        templates = [Template(**template) for template in limited_templates]
        
        fetch_time = time.time() - start_time
        logger.info(f"✅ Templates fetched in {fetch_time:.2f}s")
        
        return TemplatesResponse(
            success=True,
            templates=templates,
            count=len(templates)
        )
        
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch templates: {str(e)}")

@router.post("/generate", response_model=GenerateMemeResponse)
async def generate_meme(request: GenerateMemeRequest, background_tasks: BackgroundTasks):
    """
    Generate a single meme. Lazy loads AI components on first request.
    """
    try:
        logger.info(f"🎨 Generating meme: topic='{request.topic}', style='{request.style}'")
        start_time = time.time()
        
        # Validate humor style
        if request.style not in HUMOR_STYLES:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid humor style. Must be one of: {HUMOR_STYLES}"
            )
        
        # Lazy load AI components
        components = get_components()
        ai_components = components["ai_components"]
        
        caption_generator = ai_components["caption_generator"]
        meme_generator = ai_components["meme_generator"]
        virality_predictor = ai_components["virality_predictor"]
        
        # Get available templates with caching
        if request.template_id:
            # Try to get specific template from cache first
            cached_templates = await cache_manager.get_cached_templates(limit=50)
            templates = [t for t in cached_templates if t["template_id"] == request.template_id]
            
            if not templates:
                # Fallback: fetch fresh templates
                components = get_components()
                scrapers = components["scrapers"]
                all_templates = await scrapers["imgflip"].get_trending_templates(10)
                templates = [t for t in all_templates if t["template_id"] == request.template_id]
        else:
            # Get suitable templates for topic
            cached_templates = await cache_manager.get_cached_templates(limit=20)
            if cached_templates:
                # Simple topic matching
                topic_lower = request.topic.lower()
                scored_templates = []
                
                for template in cached_templates:
                    score = 0
                    template_name = template.get("name", "").lower()
                    
                    # Score based on topic matches
                    for word in topic_lower.split():
                        if word in template_name:
                            score += 1
                    
                    # Add popularity bonus
                    score += template.get("popularity", 0) / 100
                    scored_templates.append((template, score))
                
                # Sort and take top templates
                scored_templates.sort(key=lambda x: x[1], reverse=True)
                templates = [t for t, s in scored_templates[:10]]
            else:
                templates = []
        
        if not templates:
            raise HTTPException(
                status_code=404,
                detail="No suitable templates found for the given topic"
            )
        
        # Select best template
        selected_template = templates[0]
        
        # Generate caption
        caption_result = await caption_generator.generate_caption(
            topic=request.topic,
            style=request.style,
            template_context=selected_template
        )
        
        if not caption_result["success"]:
            raise HTTPException(status_code=500, detail="Failed to generate caption")
        
        caption = caption_result["caption"]
        
        # Create meme image
        meme_result = await meme_generator.create_meme(
            template_data=selected_template,
            caption=caption,
            style=request.style
        )
        
        if not meme_result["success"]:
            raise HTTPException(status_code=500, detail="Failed to create meme image")
        
        # Predict virality score
        virality_features = {
            "template_popularity": selected_template.get("popularity", 75),
            "caption": caption,
            "style": request.style,
            "topic": request.topic,
            "template_tags": selected_template.get("tags", [])
        }
        
        virality_result = virality_predictor.predict_virality(virality_features)
        virality_score = virality_result.get("virality_score", 50.0)
        
        # Generate meme ID and URL
        meme_id = str(uuid.uuid4())[:8]
        image_url = meme_generator.get_meme_url(meme_result["filename"])
        
        # Create meme document for database
        meme_doc = {
            "meme_id": meme_id,
            "template_id": selected_template["template_id"],
            "template_name": selected_template["name"],
            "caption": caption,
            "style": request.style,
            "image_url": image_url,
            "virality_score": virality_score,
            "upvotes": 0,
            "timestamp": datetime.utcnow(),
            "generation_metadata": {
                "topic": request.topic,
                "template_source": selected_template.get("source"),
                "caption_method": caption_result["metadata"].get("method"),
                "virality_factors": virality_result.get("factors", {})
            }
        }
        
        # Store in database
        await _store_meme_in_db(meme_doc)
        
        # Create response meme object
        response_meme = Meme(
            template_id=selected_template["template_id"],
            caption=caption,
            style=request.style,
            meme_id=meme_id,
            template_name=selected_template["name"],
            image_url=image_url,
            virality_score=virality_score,
            upvotes=0,
            timestamp=datetime.utcnow()
        )
        
        # Schedule cleanup
        background_tasks.add_task(meme_generator.cleanup_old_memes)
        
        generation_time = time.time() - start_time
        logger.info(f"✅ Meme generated in {generation_time:.2f}s")
        
        return GenerateMemeResponse(
            success=True,
            meme=response_meme,
            message=f"Meme generated successfully with {virality_score:.1f}% virality score"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating meme: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meme: {str(e)}")

@router.post("/generate-variations", response_model=JobSubmissionResponse)
async def generate_meme_variations_async(request: JobRequest, background_tasks: BackgroundTasks):
    """
    **OPTIMIZED FOR RENDER FREE TIER** - Async meme generation with batching and caching.
    
    Now returns a job ID for polling results instead of immediate generation.
    This prevents timeouts and memory issues on free tier hosting.
    
    Use the new async flow:
    1. Submit job (this endpoint) -> get job_id
    2. Poll /api/v1/job-status/{job_id} for progress
    3. Retrieve results when status = "completed"
    
    Features:
    - Batched processing (2 templates at a time)
    - Comprehensive caching (templates, captions, results)
    - Rate limiting for AI API calls
    - Memory optimization for 512MB limit
    - Graceful error handling
    """
    try:
        logger.info(f"🎭 Submitting async job: topic='{request.topic}', style='{request.style}', max_templates={request.max_templates}")
        
        # Import async components
        from app.routes.async_meme_routes import submit_meme_generation_job
        
        # Use the optimized async system
        return await submit_meme_generation_job(request, background_tasks)
        
    except Exception as e:
        logger.error(f"Error in optimized generate-variations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit generation job: {str(e)}")

@router.get("/trending", response_model=TrendingMemesResponse)
async def get_trending_memes(limit: int = 20, sort_by: str = "virality_score"):
    """Get trending memes from database."""
    try:
        logger.info(f"📈 Fetching trending memes (limit={limit}, sort_by={sort_by})")
        
        # Validate sort_by parameter
        valid_sort_fields = ["virality_score", "upvotes", "timestamp"]
        if sort_by not in valid_sort_fields:
            sort_by = "virality_score"
        
        # Query database for trending memes
        db = database.get_database()
        memes_collection = db.memes
        
        # Create sort criteria (descending order)
        sort_criteria = [(sort_by, -1)]
        if sort_by != "upvotes":
            sort_criteria.append(("upvotes", -1))  # Secondary sort by upvotes
        
        # Find trending memes
        cursor = memes_collection.find({}).sort(sort_criteria).limit(limit)
        meme_docs = await cursor.to_list(length=limit)
        
        # Convert to response format
        memes = []
        for doc in meme_docs:
            meme = Meme(
                template_id=doc["template_id"],
                caption=doc["caption"],
                style=doc["style"],
                meme_id=doc["meme_id"],
                template_name=doc["template_name"],
                image_url=doc["image_url"],
                virality_score=doc["virality_score"],
                upvotes=doc["upvotes"],
                timestamp=doc["timestamp"]
            )
            memes.append(meme)
        
        return TrendingMemesResponse(
            success=True,
            memes=memes,
            count=len(memes)
        )
        
    except Exception as e:
        logger.error(f"Error fetching trending memes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch trending memes: {str(e)}")

@router.post("/upvote", response_model=UpvoteResponse)
async def upvote_meme(request: UpvoteRequest):
    """Upvote a meme by its ID."""
    try:
        logger.info(f"👍 Upvoting meme: {request.meme_id}")
        
        # Update meme upvotes in database
        db = database.get_database()
        memes_collection = db.memes
        
        # Increment upvotes
        result = await memes_collection.update_one(
            {"meme_id": request.meme_id},
            {"$inc": {"upvotes": 1}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Meme not found")
        
        # Get updated meme to return new upvote count
        updated_meme = await memes_collection.find_one({"meme_id": request.meme_id})
        new_upvote_count = updated_meme["upvotes"] if updated_meme else 1
        
        logger.info(f"✅ Meme {request.meme_id} now has {new_upvote_count} upvotes")
        
        return UpvoteResponse(
            success=True,
            new_upvote_count=new_upvote_count,
            message=f"Meme upvoted successfully. Total upvotes: {new_upvote_count}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upvoting meme: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upvote meme: {str(e)}")

# Async Job Management Endpoints (New Optimized System)
@router.get("/job-status/{job_id}", response_model=JobResultResponse)
async def get_job_status(job_id: str):
    """
    Get job status and results for async meme generation.
    Frontend should poll this endpoint to check progress and retrieve results.
    """
    try:
        from app.routes.async_meme_routes import get_job_status as async_get_job_status
        return await async_get_job_status(job_id)
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")

@router.post("/cache-cleanup")
async def trigger_cache_cleanup(background_tasks: BackgroundTasks):
    """
    Trigger cache cleanup for maintenance.
    """
    try:
        background_tasks.add_task(cache_manager.cleanup_expired_cache)
        return {"success": True, "message": "Cache cleanup scheduled"}
    except Exception as e:
        logger.error(f"Error triggering cache cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger cache cleanup: {str(e)}")

@router.post("/score", response_model=ViralityScoreResponse)
async def calculate_virality_score(meme_id: str):
    """Calculate virality score for an existing meme."""
    try:
        logger.info(f"📊 Calculating virality score for meme: {meme_id}")
        
        # Lazy load AI components
        components = get_components()
        virality_predictor = components["ai_components"]["virality_predictor"]
        
        # Get meme from database
        db = database.get_database()
        memes_collection = db.memes
        
        meme_doc = await memes_collection.find_one({"meme_id": meme_id})
        if not meme_doc:
            raise HTTPException(status_code=404, detail="Meme not found")
        
        # Get template information for scoring
        templates_collection = db.templates
        template_doc = await templates_collection.find_one({"template_id": meme_doc["template_id"]})
        
        # Prepare features for virality prediction
        virality_features = {
            "template_popularity": template_doc.get("popularity", 75) if template_doc else 75,
            "caption": meme_doc["caption"],
            "style": meme_doc["style"],
            "topic": meme_doc.get("generation_metadata", {}).get("topic", ""),
            "template_tags": template_doc.get("tags", []) if template_doc else [],
            "current_upvotes": meme_doc["upvotes"]
        }
        
        # Calculate updated virality score
        virality_result = virality_predictor.predict_virality(virality_features)
        new_virality_score = virality_result.get("virality_score", meme_doc.get("virality_score", 50.0))
        
        # Update score in database
        await memes_collection.update_one(
            {"meme_id": meme_id},
            {"$set": {"virality_score": new_virality_score}}
        )
        
        return ViralityScoreResponse(
            success=True,
            meme_id=meme_id,
            virality_score=new_virality_score,
            factors=virality_result.get("factors", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating virality score: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate virality score: {str(e)}")

# Helper functions for backwards compatibility
async def _store_meme_in_db(meme_doc: dict):
    """Store generated meme in database."""
    try:
        db = database.get_database()
        memes_collection = db.memes
        
        await memes_collection.insert_one(meme_doc)
        logger.debug(f"Stored meme {meme_doc['meme_id']} in database")
    except Exception as e:
        logger.warning(f"Failed to store meme in database: {e}")
