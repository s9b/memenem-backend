"""
MongoDB-based caching system for MemeNem backend.
Handles caching of templates, captions, and generated memes for performance optimization.
"""

import hashlib
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from app.models.database import database
from app.models.schemas import CachedCaption, MemeVariation, MemeTemplate

logger = logging.getLogger(__name__)

class CacheManager:
    """MongoDB-based cache manager for meme generation data."""
    
    def __init__(self):
        self.db = None
        self._cache_ttl = {
            "templates": 3600,  # 1 hour
            "captions": 86400,  # 24 hours 
            "jobs": 7200,       # 2 hours
            "results": 43200    # 12 hours
        }
    
    def _get_database(self):
        """Get database connection lazily."""
        if not self.db:
            self.db = database.get_database()
        return self.db
    
    def _generate_cache_key(self, topic: str, style: str, template_id: str, variation_count: int = 4) -> str:
        """Generate unique cache key for caption requests."""
        data = f"{topic.lower()}:{style}:{template_id}:{variation_count}"
        return hashlib.md5(data.encode()).hexdigest()
    
    # Template Caching
    async def get_cached_templates(self, source: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get cached templates from database."""
        try:
            db = self._get_database()
            templates_collection = db.templates
            
            # Build query
            query = {}
            if source:
                query["source"] = source
            
            # Get templates with freshness check
            cutoff_time = datetime.utcnow() - timedelta(seconds=self._cache_ttl["templates"])
            query["updated_at"] = {"$gte": cutoff_time}
            
            cursor = templates_collection.find(query).sort("popularity", -1).limit(limit)
            template_docs = await cursor.to_list(length=limit)
            
            # Convert to list and remove MongoDB _id
            templates = []
            for doc in template_docs:
                doc.pop("_id", None)
                templates.append(doc)
            
            logger.info(f"Retrieved {len(templates)} cached templates")
            return templates
            
        except Exception as e:
            logger.warning(f"Failed to get cached templates: {e}")
            return []
    
    async def cache_templates(self, templates: List[Dict[str, Any]]) -> bool:
        """Cache templates in database with upsert."""
        try:
            if not templates:
                return False
                
            db = self._get_database()
            templates_collection = db.templates
            
            cached_count = 0
            for template in templates:
                # Add cache metadata
                template["updated_at"] = datetime.utcnow()
                template.setdefault("created_at", datetime.utcnow())
                
                # Upsert template
                await templates_collection.update_one(
                    {"template_id": template["template_id"]},
                    {
                        "$set": template,
                        "$setOnInsert": {"created_at": datetime.utcnow()}
                    },
                    upsert=True
                )
                cached_count += 1
            
            logger.info(f"Cached {cached_count} templates")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache templates: {e}")
            return False
    
    # Caption Caching
    async def get_cached_captions(self, topic: str, style: str, template_id: str, 
                                variation_count: int = 4) -> Optional[List[MemeVariation]]:
        """Get cached caption variations for specific parameters."""
        try:
            cache_key = self._generate_cache_key(topic, style, template_id, variation_count)
            
            db = self._get_database()
            captions_collection = db.cached_captions
            
            # Check for cached captions within TTL
            cutoff_time = datetime.utcnow() - timedelta(seconds=self._cache_ttl["captions"])
            
            cursor = captions_collection.find({
                "cache_key": cache_key,
                "created_at": {"$gte": cutoff_time}
            }).sort("created_at", -1).limit(variation_count)
            
            cached_docs = await cursor.to_list(length=variation_count)
            
            if not cached_docs:
                return None
            
            # Convert to MemeVariation objects
            variations = []
            for i, doc in enumerate(cached_docs):
                variation = MemeVariation(
                    variation_id=i + 1,
                    caption=doc.get("caption"),
                    captions=doc.get("captions"),
                    virality_score=doc.get("virality_score", 50.0),
                    metadata={
                        "cached": True,
                        "cache_hit_time": datetime.utcnow(),
                        "original_created": doc.get("created_at")
                    }
                )
                variations.append(variation)
            
            # Update hit count
            await captions_collection.update_many(
                {"cache_key": cache_key},
                {"$inc": {"hit_count": 1}}
            )
            
            logger.info(f"Cache hit: Retrieved {len(variations)} cached caption variations")
            return variations
            
        except Exception as e:
            logger.warning(f"Failed to get cached captions: {e}")
            return None
    
    async def cache_captions(self, topic: str, style: str, template_id: str, 
                           variations: List[MemeVariation]) -> bool:
        """Cache caption variations for future use."""
        try:
            if not variations:
                return False
                
            cache_key = self._generate_cache_key(topic, style, template_id, len(variations))
            
            db = self._get_database()
            captions_collection = db.cached_captions
            
            # Prepare documents for caching
            cache_docs = []
            for variation in variations:
                doc = {
                    "cache_key": cache_key,
                    "topic": topic,
                    "style": style,
                    "template_id": template_id,
                    "caption": variation.caption,
                    "captions": variation.captions,
                    "virality_score": variation.virality_score,
                    "created_at": datetime.utcnow(),
                    "hit_count": 0,
                    "variation_metadata": variation.metadata
                }
                cache_docs.append(doc)
            
            # Insert all variations
            if cache_docs:
                await captions_collection.insert_many(cache_docs)
                logger.info(f"Cached {len(cache_docs)} caption variations")
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache captions: {e}")
            return False
    
    # Job Status Caching
    async def create_job_status(self, job_id: str, topic: str, style: str, 
                              max_templates: int, variations_per_template: int) -> bool:
        """Create initial job status in database."""
        try:
            db = self._get_database()
            jobs_collection = db.job_status
            
            job_doc = {
                "job_id": job_id,
                "status": "queued",
                "progress": 0.0,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "total_templates": max_templates,
                "completed_templates": 0,
                "request_params": {
                    "topic": topic,
                    "style": style,
                    "max_templates": max_templates,
                    "variations_per_template": variations_per_template
                },
                "error_message": None,
                "processing_time": None,
                "completed_at": None
            }
            
            await jobs_collection.insert_one(job_doc)
            logger.info(f"Created job status for job_id: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create job status: {e}")
            return False
    
    async def update_job_status(self, job_id: str, status: str = None, progress: float = None,
                              completed_templates: int = None, error_message: str = None) -> bool:
        """Update job status in database."""
        try:
            db = self._get_database()
            jobs_collection = db.job_status
            
            update_doc = {"updated_at": datetime.utcnow()}
            
            if status is not None:
                update_doc["status"] = status
                if status == "completed":
                    update_doc["completed_at"] = datetime.utcnow()
                    update_doc["progress"] = 100.0
            
            if progress is not None:
                update_doc["progress"] = min(100.0, max(0.0, progress))
            
            if completed_templates is not None:
                update_doc["completed_templates"] = completed_templates
            
            if error_message is not None:
                update_doc["error_message"] = error_message
                update_doc["status"] = "failed"
            
            result = await jobs_collection.update_one(
                {"job_id": job_id},
                {"$set": update_doc}
            )
            
            return result.matched_count > 0
            
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            return False
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status from database."""
        try:
            db = self._get_database()
            jobs_collection = db.job_status
            
            job_doc = await jobs_collection.find_one({"job_id": job_id})
            if job_doc:
                job_doc.pop("_id", None)
                return job_doc
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None
    
    # Result Caching
    async def cache_job_results(self, job_id: str, templates: List[MemeTemplate]) -> bool:
        """Cache job results for retrieval."""
        try:
            db = self._get_database()
            results_collection = db.job_results
            
            # Convert MemeTemplate objects to dict for storage
            templates_data = []
            for template in templates:
                template_data = {
                    "template_id": template.template_id,
                    "template_name": template.template_name,
                    "image_url": template.image_url,
                    "panel_count": template.panel_count,
                    "characters": template.characters,
                    "average_virality_score": template.average_virality_score,
                    "variations": []
                }
                
                for variation in template.variations:
                    variation_data = {
                        "variation_id": variation.variation_id,
                        "caption": variation.caption,
                        "captions": variation.captions,
                        "virality_score": variation.virality_score,
                        "metadata": variation.metadata
                    }
                    template_data["variations"].append(variation_data)
                
                templates_data.append(template_data)
            
            result_doc = {
                "job_id": job_id,
                "templates": templates_data,
                "count": len(templates),
                "cached_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(seconds=self._cache_ttl["results"])
            }
            
            # Upsert results
            await results_collection.update_one(
                {"job_id": job_id},
                {"$set": result_doc},
                upsert=True
            )
            
            logger.info(f"Cached results for job_id: {job_id} ({len(templates)} templates)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache job results: {e}")
            return False
    
    async def get_cached_job_results(self, job_id: str) -> Optional[Tuple[List[MemeTemplate], int]]:
        """Get cached job results."""
        try:
            db = self._get_database()
            results_collection = db.job_results
            
            # Check for non-expired results
            result_doc = await results_collection.find_one({
                "job_id": job_id,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            if not result_doc:
                return None
            
            # Convert back to MemeTemplate objects
            templates = []
            for template_data in result_doc["templates"]:
                variations = []
                for var_data in template_data["variations"]:
                    variation = MemeVariation(
                        variation_id=var_data["variation_id"],
                        caption=var_data.get("caption"),
                        captions=var_data.get("captions"),
                        virality_score=var_data["virality_score"],
                        metadata=var_data.get("metadata", {})
                    )
                    variations.append(variation)
                
                template = MemeTemplate(
                    template_id=template_data["template_id"],
                    template_name=template_data["template_name"],
                    image_url=template_data["image_url"],
                    panel_count=template_data["panel_count"],
                    characters=template_data["characters"],
                    variations=variations,
                    average_virality_score=template_data["average_virality_score"]
                )
                templates.append(template)
            
            return templates, result_doc["count"]
            
        except Exception as e:
            logger.warning(f"Failed to get cached job results: {e}")
            return None
    
    # Cache Cleanup
    async def cleanup_expired_cache(self) -> Dict[str, int]:
        """Clean up expired cache entries."""
        try:
            db = self._get_database()
            cleanup_stats = {}
            
            # Clean expired captions
            caption_cutoff = datetime.utcnow() - timedelta(seconds=self._cache_ttl["captions"])
            result = await db.cached_captions.delete_many({
                "created_at": {"$lt": caption_cutoff}
            })
            cleanup_stats["captions"] = result.deleted_count
            
            # Clean old job statuses
            job_cutoff = datetime.utcnow() - timedelta(seconds=self._cache_ttl["jobs"])
            result = await db.job_status.delete_many({
                "updated_at": {"$lt": job_cutoff},
                "status": {"$in": ["completed", "failed", "cancelled"]}
            })
            cleanup_stats["jobs"] = result.deleted_count
            
            # Clean expired results
            result = await db.job_results.delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })
            cleanup_stats["results"] = result.deleted_count
            
            # Clean old templates (keep popular ones)
            template_cutoff = datetime.utcnow() - timedelta(seconds=self._cache_ttl["templates"] * 24)  # 24 hours for templates
            result = await db.templates.delete_many({
                "updated_at": {"$lt": template_cutoff},
                "popularity": {"$lt": 50}  # Keep popular templates longer
            })
            cleanup_stats["templates"] = result.deleted_count
            
            total_cleaned = sum(cleanup_stats.values())
            if total_cleaned > 0:
                logger.info(f"Cache cleanup completed: {cleanup_stats}")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup cache: {e}")
            return {}

# Global cache manager instance
cache_manager = CacheManager()