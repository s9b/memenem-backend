"""
FastAPI routes for meme generation and management.
Implements all required endpoints: /templates, /generate, /trending, /upvote, /score
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from loguru import logger
from datetime import datetime
import uuid

from app.models.schemas import (
    GenerateMemeRequest, GenerateMemeResponse, GenerateMemesResponse, TemplatesResponse, TrendingMemesResponse,
    UpvoteRequest, UpvoteResponse, ViralityScoreResponse, ErrorResponse,
    Template, Meme, MemeTemplate, MemeVariation, HUMOR_STYLES
)
from app.models.database import database
from app.scrapers.imgflip_scraper import ImgflipScraper
from app.scrapers.reddit_scraper import RedditScraper
from app.scrapers.knowyourmeme_scraper import KnowYourMemeScraper
from app.ai.caption_generator import CaptionGenerator
from app.ai.meme_generator import MemeGenerator
from app.ai.virality_model import ViralityPredictor

# Create router
router = APIRouter()

# Initialize components (will be properly dependency injected in production)
imgflip_scraper = ImgflipScraper()
reddit_scraper = RedditScraper()
kym_scraper = KnowYourMemeScraper()
caption_generator = CaptionGenerator()
meme_generator = MemeGenerator()
virality_predictor = ViralityPredictor()

@router.get("/templates", response_model=TemplatesResponse)
async def get_trending_templates(limit: int = 50, source: Optional[str] = None):
    """
    Get trending meme templates from various sources.
    
    Args:
        limit: Maximum number of templates to return
        source: Specific source to fetch from (imgflip, reddit, knowyourmeme)
    """
    try:
        logger.info(f"Fetching trending templates (limit={limit}, source={source})")
        
        all_templates = []
        
        if source is None or source == "imgflip":
            try:
                # Fetch all available templates if limit is high, otherwise use proportional split
                imgflip_limit = 0 if limit > 200 else max(50, limit // 2)  # Get more from Imgflip as it's most reliable
                imgflip_templates = await imgflip_scraper.get_trending_templates(imgflip_limit)
                all_templates.extend(imgflip_templates)
            except Exception as e:
                logger.warning(f"Imgflip scraping failed: {e}")
        
        if source is None or source == "reddit":
            try:
                # Limit Reddit templates to avoid rate limits
                reddit_limit = min(50, limit // 4) if limit > 20 else limit // 4
                reddit_templates = await reddit_scraper.get_trending_templates(reddit_limit)
                all_templates.extend(reddit_templates)
            except Exception as e:
                logger.warning(f"Reddit scraping failed: {e}")
        
        if source is None or source == "knowyourmeme":
            try:
                kym_templates = await kym_scraper.get_trending_templates(limit // 3)
                all_templates.extend(kym_templates)
            except Exception as e:
                logger.warning(f"KnowYourMeme scraping failed: {e}")
        
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
        
        # Store templates in database for future use
        await _store_templates_in_db(limited_templates)
        
        # Convert to response format
        templates = [Template(**template) for template in limited_templates]
        
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
    Generate a new meme based on topic and style.
    
    Args:
        request: Meme generation request with topic, style, and optional template_id
    """
    try:
        logger.info(f"Generating meme: topic='{request.topic}', style='{request.style}'")
        
        # Validate humor style
        if request.style not in HUMOR_STYLES:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid humor style. Must be one of: {HUMOR_STYLES}"
            )
        
        # Get available templates from database or scrape new ones
        templates = await _get_templates_for_topic(request.topic, request.template_id, limit=10)
        
        if not templates:
            raise HTTPException(
                status_code=404,
                detail="No suitable templates found for the given topic"
            )
        
        # Select best template for the topic
        selected_template = templates[0]  # Already sorted by relevance
        
        # Generate caption
        caption_result = await caption_generator.generate_caption(
            topic=request.topic,
            style=request.style,
            template_context=selected_template
        )
        
        if not caption_result["success"]:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate caption"
            )
        
        caption = caption_result["caption"]
        
        # Create meme image
        meme_result = await meme_generator.create_meme(
            template_data=selected_template,
            caption=caption,
            style=request.style
        )
        
        if not meme_result["success"]:
            raise HTTPException(
                status_code=500,
                detail="Failed to create meme image"
            )
        
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
        
        # Schedule cleanup of old memes
        background_tasks.add_task(meme_generator.cleanup_old_memes)
        
        logger.info(f"Successfully generated meme {meme_id} with virality score {virality_score}")
        
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

@router.post("/generate-variations", response_model=GenerateMemesResponse)
async def generate_meme_variations(request: GenerateMemeRequest, background_tasks: BackgroundTasks):
    """
    Generate multiple meme variations with 4-5 caption options per relevant template.
    
    Args:
        request: Meme generation request with topic, style, and optional template_id
    """
    try:
        logger.info(f"Generating meme variations: topic='{request.topic}', style='{request.style}'")
        
        # Validate humor style
        if request.style not in HUMOR_STYLES:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid humor style. Must be one of: {HUMOR_STYLES}"
            )
        
        # Get relevant templates (top 10-15 for topic)
        templates = await _get_templates_for_topic(request.topic, request.template_id, limit=15)
        
        if not templates:
            raise HTTPException(
                status_code=404,
                detail="No suitable templates found for the given topic"
            )
        
        # Take top 5 most relevant templates to avoid API rate limits
        selected_templates = templates[:5]
        
        meme_templates = []
        
        # Generate variations for each template
        for template in selected_templates:
            try:
                # Generate 4-5 caption variations for this template
                variations = await caption_generator.generate_caption_variations(
                    topic=request.topic,
                    style=request.style,
                    template_context=template,
                    count=4
                )
                
                meme_variations = []
                virality_scores = []
                
                # Process each variation
                for var_data in variations:
                    # Calculate virality score for this variation
                    caption_text = var_data.get("caption", "")
                    if not caption_text and var_data.get("captions"):
                        # For multi-panel, combine all captions for scoring
                        caption_text = " / ".join(var_data["captions"].values())
                    
                    virality_features = {
                        "template_popularity": template.get("popularity", 75),
                        "caption": caption_text,
                        "style": request.style,
                        "topic": request.topic,
                        "template_tags": template.get("tags", [])
                    }
                    
                    virality_result = virality_predictor.predict_virality(virality_features)
                    virality_score = virality_result.get("virality_score", 50.0)
                    virality_scores.append(virality_score)
                    
                    # Create variation object
                    variation = MemeVariation(
                        variation_id=var_data.get("variation_id", 1),
                        caption=var_data.get("caption"),
                        captions=var_data.get("captions"),
                        virality_score=virality_score,
                        metadata=var_data.get("metadata", {})
                    )
                    meme_variations.append(variation)
                
                # Calculate average virality score
                avg_virality = sum(virality_scores) / len(virality_scores) if virality_scores else 50.0
                
                # Create template object with variations
                meme_template = MemeTemplate(
                    template_id=template["template_id"],
                    template_name=template["name"],
                    image_url=template["url"],
                    panel_count=template.get("panel_count", 1),
                    characters=template.get("characters", []),
                    variations=meme_variations,
                    average_virality_score=avg_virality
                )
                
                meme_templates.append(meme_template)
                
            except Exception as e:
                logger.warning(f"Failed to generate variations for template {template.get('name')}: {e}")
                continue
        
        if not meme_templates:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate meme variations for any templates"
            )
        
        # Sort by average virality score
        meme_templates.sort(key=lambda x: x.average_virality_score, reverse=True)
        
        # Schedule cleanup
        background_tasks.add_task(meme_generator.cleanup_old_memes)
        
        logger.info(f"Successfully generated {len(meme_templates)} templates with variations")
        
        return GenerateMemesResponse(
            success=True,
            templates=meme_templates,
            count=len(meme_templates),
            message=f"Generated {len(meme_templates)} meme templates with multiple variations"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating meme variations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meme variations: {str(e)}")

@router.get("/trending", response_model=TrendingMemesResponse)
async def get_trending_memes(limit: int = 20, sort_by: str = "virality_score"):
    """
    Get trending memes sorted by virality score and upvotes.
    
    Args:
        limit: Maximum number of memes to return
        sort_by: Sort criteria (virality_score, upvotes, timestamp)
    """
    try:
        logger.info(f"Fetching trending memes (limit={limit}, sort_by={sort_by})")
        
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
    """
    Upvote a meme by its ID.
    
    Args:
        request: Upvote request with meme_id
    """
    try:
        logger.info(f"Upvoting meme: {request.meme_id}")
        
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
        
        logger.info(f"Meme {request.meme_id} now has {new_upvote_count} upvotes")
        
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

@router.post("/score", response_model=ViralityScoreResponse)
async def calculate_virality_score(meme_id: str):
    """
    Calculate virality score for an existing meme.
    
    Args:
        meme_id: ID of the meme to score
    """
    try:
        logger.info(f"Calculating virality score for meme: {meme_id}")
        
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

# Helper functions

async def _store_templates_in_db(templates: List[dict]):
    """Store templates in database for future use."""
    try:
        db = database.get_database()
        templates_collection = db.templates
        
        for template in templates:
            # Use upsert to avoid duplicates
            await templates_collection.update_one(
                {"template_id": template["template_id"]},
                {
                    "$set": {
                        **template,
                        "updated_at": datetime.utcnow()
                    },
                    "$setOnInsert": {"created_at": datetime.utcnow()}
                },
                upsert=True
            )
    except Exception as e:
        logger.warning(f"Failed to store templates in database: {e}")

async def _store_meme_in_db(meme_doc: dict):
    """Store generated meme in database."""
    try:
        db = database.get_database()
        memes_collection = db.memes
        
        await memes_collection.insert_one(meme_doc)
        logger.debug(f"Stored meme {meme_doc['meme_id']} in database")
    except Exception as e:
        logger.warning(f"Failed to store meme in database: {e}")

async def _get_templates_for_topic(topic: str, preferred_template_id: Optional[str] = None, limit: int = 50) -> List[dict]:
    """Get templates suitable for the given topic."""
    try:
        db = database.get_database()
        templates_collection = db.templates
        
        # If specific template requested, try to get it
        if preferred_template_id:
            template_doc = await templates_collection.find_one({"template_id": preferred_template_id})
            if template_doc:
                template_doc.pop("_id", None)  # Remove MongoDB _id field
                return [template_doc]
        
        # Otherwise, get all templates and let the caption generator suggest best ones
        cursor = templates_collection.find({}).sort("popularity", -1).limit(limit * 2)  # Get more for better selection
        template_docs = await cursor.to_list(length=limit * 2)
        
        # Remove MongoDB _id field
        templates = []
        for doc in template_docs:
            doc.pop("_id", None)
            templates.append(doc)
        
        if not templates:
            # Fallback: fetch some templates from scrapers
            logger.info("No templates in database, fetching from scrapers")
            templates = await imgflip_scraper.get_trending_templates(20)
        
        # Use AI to suggest best templates for the topic
        if templates:
            suggested_templates = await caption_generator.suggest_templates_for_topic(topic, templates)
            return suggested_templates
        
        return templates
        
    except Exception as e:
        logger.error(f"Error getting templates for topic: {e}")
        return []