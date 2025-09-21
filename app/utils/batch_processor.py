"""
Optimized batch processing system for async meme generation.
Handles batching, memory management, and rate limiting for Render free tier.
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from app.models.schemas import MemeTemplate, MemeVariation, HUMOR_STYLES
from app.utils.cache_manager import cache_manager

logger = logging.getLogger(__name__)

class BatchProcessor:
    """Optimized batch processor for meme generation with memory management."""
    
    def __init__(self):
        self.batch_size = 2  # Process 2 templates at a time for memory efficiency
        self.max_concurrent_batches = 1  # Only 1 batch at a time on free tier
        self.rate_limit_delay = 2.0  # 2 seconds between AI API calls
        self.max_retries = 2
        self._active_jobs = {}  # Track active jobs
        
    async def process_meme_generation_job(
        self, 
        job_id: str, 
        topic: str, 
        style: str, 
        max_templates: int,
        variations_per_template: int,
        template_id: Optional[str] = None
    ):
        """
        Process meme generation job with batching and caching.
        
        Args:
            job_id: Unique job identifier
            topic: Meme topic/theme
            style: Humor style
            max_templates: Maximum number of templates to process
            variations_per_template: Number of caption variations per template
            template_id: Optional specific template ID
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting batch job {job_id}: topic='{topic}', style='{style}', max_templates={max_templates}")
            
            # Update job status to processing
            await cache_manager.update_job_status(job_id, "processing", 0.0)
            
            # Get relevant templates (with caching)
            templates = await self._get_templates_for_job(topic, template_id, max_templates)
            
            if not templates:
                await cache_manager.update_job_status(
                    job_id, 
                    error_message=f"No suitable templates found for topic: {topic}"
                )
                return
            
            # Process templates in batches
            generated_templates = []
            total_templates = len(templates)
            
            # Split templates into batches
            batches = [templates[i:i + self.batch_size] for i in range(0, len(templates), self.batch_size)]
            
            completed_templates = 0
            
            for batch_idx, batch_templates in enumerate(batches):
                try:
                    logger.info(f"Job {job_id}: Processing batch {batch_idx + 1}/{len(batches)}")
                    
                    # Process batch
                    batch_results = await self._process_template_batch(
                        batch_templates, topic, style, variations_per_template, job_id
                    )
                    
                    generated_templates.extend(batch_results)
                    completed_templates += len(batch_results)
                    
                    # Update progress
                    progress = (completed_templates / total_templates) * 100
                    await cache_manager.update_job_status(
                        job_id, 
                        progress=progress, 
                        completed_templates=completed_templates
                    )
                    
                    # Rate limiting between batches
                    if batch_idx < len(batches) - 1:  # Don't delay after last batch
                        await asyncio.sleep(self.rate_limit_delay)
                    
                except Exception as e:
                    logger.error(f"Job {job_id}: Error processing batch {batch_idx + 1}: {e}")
                    # Continue with next batch on error
                    continue
            
            # Sort by average virality score
            if generated_templates:
                generated_templates.sort(key=lambda x: x.average_virality_score, reverse=True)
            
            # Cache results
            await cache_manager.cache_job_results(job_id, generated_templates)
            
            # Update job status to completed
            processing_time = time.time() - start_time
            await cache_manager.update_job_status(job_id, "completed")
            
            logger.info(f"Job {job_id} completed in {processing_time:.2f}s with {len(generated_templates)} templates")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            await cache_manager.update_job_status(
                job_id, 
                error_message=f"Job processing failed: {str(e)}"
            )
    
    async def _get_templates_for_job(
        self, 
        topic: str, 
        template_id: Optional[str], 
        max_templates: int
    ) -> List[Dict[str, Any]]:
        """Get templates for job with caching and topic relevance."""
        try:
            # Check cache first
            cached_templates = await cache_manager.get_cached_templates(limit=max_templates * 2)
            
            if cached_templates:
                logger.info(f"Using {len(cached_templates)} cached templates")
                
                # If specific template requested
                if template_id:
                    specific_template = next(
                        (t for t in cached_templates if t["template_id"] == template_id), 
                        None
                    )
                    if specific_template:
                        return [specific_template]
                
                # Use AI to suggest best templates for topic
                suggested_templates = await self._suggest_templates_for_topic(topic, cached_templates)
                return suggested_templates[:max_templates]
            
            # Fallback: fetch fresh templates
            logger.info("No cached templates, fetching fresh templates")
            return await self._fetch_fresh_templates(topic, template_id, max_templates)
            
        except Exception as e:
            logger.error(f"Error getting templates for job: {e}")
            return []
    
    async def _fetch_fresh_templates(
        self, 
        topic: str, 
        template_id: Optional[str], 
        max_templates: int
    ) -> List[Dict[str, Any]]:
        """Fetch fresh templates from scrapers."""
        try:
            # Import scrapers lazily to save memory
            from main import get_lazy_component
            scrapers = get_lazy_component("scrapers")
            
            all_templates = []
            
            # Fetch from different sources with limits
            try:
                imgflip_templates = await scrapers["imgflip"].get_trending_templates(max_templates)
                all_templates.extend(imgflip_templates)
            except Exception as e:
                logger.warning(f"Imgflip fetch failed: {e}")
            
            try:
                reddit_templates = await scrapers["reddit"].get_trending_templates(max_templates // 2)
                all_templates.extend(reddit_templates)
            except Exception as e:
                logger.warning(f"Reddit fetch failed: {e}")
            
            # Remove duplicates and cache templates
            unique_templates = self._deduplicate_templates(all_templates)
            
            if unique_templates:
                await cache_manager.cache_templates(unique_templates)
            
            # Suggest best templates for topic
            suggested_templates = await self._suggest_templates_for_topic(topic, unique_templates)
            return suggested_templates[:max_templates]
            
        except Exception as e:
            logger.error(f"Error fetching fresh templates: {e}")
            return []
    
    def _deduplicate_templates(self, templates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate templates based on template_id."""
        seen_ids = set()
        unique_templates = []
        
        for template in templates:
            template_id = template.get("template_id")
            if template_id and template_id not in seen_ids:
                seen_ids.add(template_id)
                unique_templates.append(template)
        
        return unique_templates
    
    async def _suggest_templates_for_topic(
        self, 
        topic: str, 
        templates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Suggest best templates for topic using simple keyword matching."""
        try:
            topic_lower = topic.lower()
            topic_words = topic_lower.split()
            
            scored_templates = []
            
            for template in templates:
                score = 0
                template_name = template.get("name", "").lower()
                template_tags = [tag.lower() for tag in template.get("tags", [])]
                
                # Score based on name matches
                for word in topic_words:
                    if word in template_name:
                        score += 3
                    if any(word in tag for tag in template_tags):
                        score += 2
                
                # Bonus for popularity
                popularity = template.get("popularity", 0)
                score += min(popularity / 20, 5)
                
                scored_templates.append((template, score))
            
            # Sort by score and return top templates
            scored_templates.sort(key=lambda x: x[1], reverse=True)
            return [template for template, score in scored_templates]
            
        except Exception as e:
            logger.error(f"Error suggesting templates: {e}")
            return templates  # Fallback to original list
    
    async def _process_template_batch(
        self, 
        batch_templates: List[Dict[str, Any]], 
        topic: str, 
        style: str, 
        variations_per_template: int,
        job_id: str
    ) -> List[MemeTemplate]:
        """Process a batch of templates with memory optimization."""
        batch_results = []
        
        for template in batch_templates:
            try:
                # Check cache first
                cached_variations = await cache_manager.get_cached_captions(
                    topic, style, template["template_id"], variations_per_template
                )
                
                if cached_variations:
                    logger.info(f"Using cached captions for template {template['name']}")
                    variations = cached_variations
                else:
                    # Generate new variations
                    variations = await self._generate_caption_variations(
                        template, topic, style, variations_per_template
                    )
                    
                    # Cache the variations
                    if variations:
                        await cache_manager.cache_captions(
                            topic, style, template["template_id"], variations
                        )
                
                if variations:
                    # Calculate average virality score
                    avg_virality = sum(v.virality_score for v in variations) / len(variations)
                    
                    # Create MemeTemplate object
                    meme_template = MemeTemplate(
                        template_id=template["template_id"],
                        template_name=template["name"],
                        image_url=template["url"],
                        panel_count=template.get("panel_count", 1),
                        characters=template.get("characters", []),
                        variations=variations,
                        average_virality_score=avg_virality
                    )
                    
                    batch_results.append(meme_template)
                
                # Small delay between templates to manage API rate limits
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Failed to process template {template.get('name')}: {e}")
                continue
        
        return batch_results
    
    async def _generate_caption_variations(
        self, 
        template: Dict[str, Any], 
        topic: str, 
        style: str, 
        count: int
    ) -> List[MemeVariation]:
        """Generate caption variations for a template with memory optimization."""
        try:
            # Import AI components lazily
            from main import get_lazy_component
            ai_components = get_lazy_component("ai_components")
            
            caption_generator = ai_components["caption_generator"]
            virality_predictor = ai_components["virality_predictor"]
            
            variations = []
            
            # Handle multi-panel templates
            if template.get("panel_count", 1) > 1:
                variations = await self._generate_multi_panel_variations(
                    template, topic, style, count, caption_generator, virality_predictor
                )
            else:
                # Generate single-panel variations
                for i in range(count):
                    try:
                        caption_result = await caption_generator.generate_caption(
                            topic=topic,
                            style=style,
                            template_context=template
                        )
                        
                        if caption_result.get("success"):
                            # Calculate virality score
                            virality_features = {
                                "template_popularity": template.get("popularity", 75),
                                "caption": caption_result["caption"],
                                "style": style,
                                "topic": topic,
                                "template_tags": template.get("tags", [])
                            }
                            
                            virality_result = virality_predictor.predict_virality(virality_features)
                            virality_score = virality_result.get("virality_score", 50.0)
                            
                            variation = MemeVariation(
                                variation_id=i + 1,
                                caption=caption_result["caption"],
                                virality_score=virality_score,
                                metadata=caption_result.get("metadata", {})
                            )
                            variations.append(variation)
                        
                        # Rate limiting for AI calls
                        if i < count - 1:  # Don't delay after last variation
                            await asyncio.sleep(1.0)
                            
                    except Exception as e:
                        logger.warning(f"Failed to generate variation {i + 1}: {e}")
                        continue
            
            return variations
            
        except Exception as e:
            logger.error(f"Error generating caption variations: {e}")
            return []
    
    async def _generate_multi_panel_variations(
        self, 
        template: Dict[str, Any], 
        topic: str, 
        style: str, 
        count: int,
        caption_generator,
        virality_predictor
    ) -> List[MemeVariation]:
        """Generate variations for multi-panel memes."""
        try:
            variations = []
            
            for i in range(count):
                try:
                    # Generate multi-panel captions
                    multi_variations = await caption_generator.generate_caption_variations(
                        topic=topic,
                        style=style,
                        template_context=template,
                        count=1  # Generate one multi-panel variation at a time
                    )
                    
                    if multi_variations:
                        var_data = multi_variations[0]
                        
                        # Calculate virality score for multi-panel caption
                        caption_text = ""
                        if var_data.get("captions"):
                            caption_text = " / ".join(var_data["captions"].values())
                        elif var_data.get("caption"):
                            caption_text = var_data["caption"]
                        
                        virality_features = {
                            "template_popularity": template.get("popularity", 75),
                            "caption": caption_text,
                            "style": style,
                            "topic": topic,
                            "template_tags": template.get("tags", [])
                        }
                        
                        virality_result = virality_predictor.predict_virality(virality_features)
                        virality_score = virality_result.get("virality_score", 50.0)
                        
                        variation = MemeVariation(
                            variation_id=i + 1,
                            caption=var_data.get("caption"),
                            captions=var_data.get("captions"),
                            virality_score=virality_score,
                            metadata=var_data.get("metadata", {})
                        )
                        variations.append(variation)
                    
                    # Rate limiting
                    if i < count - 1:
                        await asyncio.sleep(1.5)  # Longer delay for multi-panel
                    
                except Exception as e:
                    logger.warning(f"Failed to generate multi-panel variation {i + 1}: {e}")
                    continue
            
            return variations
            
        except Exception as e:
            logger.error(f"Error generating multi-panel variations: {e}")
            return []
    
    def get_estimated_completion_time(self, max_templates: int, variations_per_template: int) -> int:
        """Estimate job completion time in seconds."""
        try:
            # Base time estimates (in seconds)
            template_fetch_time = 5  # Time to fetch templates
            caption_generation_time = 3  # Time per caption variation
            batch_overhead = 2  # Overhead per batch
            
            # Calculate total time
            total_variations = max_templates * variations_per_template
            total_caption_time = total_variations * caption_generation_time
            
            num_batches = (max_templates + self.batch_size - 1) // self.batch_size
            total_batch_overhead = num_batches * batch_overhead
            
            # Add rate limiting delays
            rate_limit_time = (num_batches - 1) * self.rate_limit_delay
            
            estimated_time = template_fetch_time + total_caption_time + total_batch_overhead + rate_limit_time
            
            # Add 20% buffer for safety
            return int(estimated_time * 1.2)
            
        except Exception:
            # Fallback estimate
            return max_templates * variations_per_template * 4

# Global batch processor instance
batch_processor = BatchProcessor()