"""
Imgflip API scraper for fetching trending meme templates.
Uses Imgflip API with authentication to get popular templates.
"""

import httpx
from typing import List, Dict, Any
from loguru import logger
from app.config import config
from app.models.schemas import TemplateInDB

class ImgflipScraper:
    """Scraper for Imgflip API to fetch trending meme templates."""
    
    def __init__(self):
        self.base_url = "https://api.imgflip.com"
        self.username = config.imgflip_username
        self.password = config.imgflip_password
    
    async def get_trending_templates(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch trending meme templates from Imgflip API.
        
        Args:
            limit: Maximum number of templates to fetch
            
        Returns:
            List of template data dictionaries
        """
        try:
            logger.info("Fetching trending templates from Imgflip API")
            
            async with httpx.AsyncClient() as client:
                # Get popular templates
                response = await client.get(f"{self.base_url}/get_memes")
                
                if response.status_code != 200:
                    logger.error(f"Imgflip API returned status {response.status_code}")
                    return []
                
                data = response.json()
                
                if not data.get("success"):
                    logger.error("Imgflip API request failed")
                    return []
                
                memes = data.get("data", {}).get("memes", [])
                templates = []
                
                for meme in memes[:limit]:
                    template_data = await self._process_template(meme)
                    if template_data:
                        templates.append(template_data)
                
                logger.info(f"Successfully fetched {len(templates)} templates from Imgflip")
                return templates
                
        except Exception as e:
            logger.error(f"Error fetching Imgflip templates: {e}")
            return []
    
    async def _process_template(self, meme_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single template from Imgflip API response.
        
        Args:
            meme_data: Raw meme data from API
            
        Returns:
            Processed template data dictionary
        """
        try:
            # Extract template information
            template_id = str(meme_data.get("id", ""))
            name = meme_data.get("name", "").strip()
            url = meme_data.get("url", "")
            box_count = meme_data.get("box_count", 2)
            width = meme_data.get("width")
            height = meme_data.get("height")
            
            if not all([template_id, name, url]):
                logger.warning(f"Incomplete template data: {meme_data}")
                return None
            
            # Generate tags based on template name
            tags = await self._generate_tags(name)
            
            # Calculate popularity based on position in trending list
            # Templates appearing earlier are considered more popular
            popularity = 100.0 - (meme_data.get("_position", 0) * 2)
            popularity = max(popularity, 10.0)  # Minimum popularity score
            
            template_data = {
                "template_id": f"imgflip_{template_id}",
                "name": name,
                "url": url,
                "tags": tags,
                "popularity": popularity,
                "source": "imgflip",
                "box_count": box_count,
                "width": width,
                "height": height
            }
            
            return template_data
            
        except Exception as e:
            logger.error(f"Error processing template {meme_data}: {e}")
            return None
    
    async def _generate_tags(self, template_name: str) -> List[str]:
        """
        Generate relevant tags for a template based on its name.
        
        Args:
            template_name: Name of the template
            
        Returns:
            List of relevant tags
        """
        name_lower = template_name.lower()
        tags = ["meme", "imgflip"]
        
        # Tag patterns based on common meme types
        tag_patterns = {
            "drake": ["reaction", "choice", "preference"],
            "distracted": ["distraction", "choice", "temptation"],
            "success": ["success", "celebration"],
            "disaster": ["disaster", "chaos", "failure"],
            "guy": ["person", "reaction"],
            "woman": ["person", "reaction"],
            "cat": ["animal", "pet"],
            "dog": ["animal", "pet"],
            "crying": ["sad", "emotion"],
            "laughing": ["happy", "joy"],
            "angry": ["mad", "emotion"],
            "surprised": ["shock", "reaction"],
            "thinking": ["contemplation", "decision"],
            "pointing": ["accusation", "blame"],
            "change": ["mind", "opinion"],
            "board": ["meeting", "presentation"],
            "office": ["work", "corporate"],
            "student": ["school", "education"],
            "first": ["first time", "new"],
            "ancient": ["old", "historical"],
            "modern": ["contemporary", "current"]
        }
        
        # Add tags based on name patterns
        for pattern, pattern_tags in tag_patterns.items():
            if pattern in name_lower:
                tags.extend(pattern_tags)
        
        # Remove duplicates and return
        return list(set(tags))
    
    async def search_templates(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for specific templates by name/query.
        
        Args:
            query: Search query for templates
            limit: Maximum number of results
            
        Returns:
            List of matching template data
        """
        try:
            logger.info(f"Searching Imgflip templates for: {query}")
            
            # Get all templates and filter by query
            all_templates = await self.get_trending_templates(200)
            
            query_lower = query.lower()
            matching_templates = []
            
            for template in all_templates:
                name_lower = template["name"].lower()
                tags_lower = [tag.lower() for tag in template.get("tags", [])]
                
                if (query_lower in name_lower or 
                    any(query_lower in tag for tag in tags_lower)):
                    matching_templates.append(template)
                
                if len(matching_templates) >= limit:
                    break
            
            logger.info(f"Found {len(matching_templates)} matching templates")
            return matching_templates
            
        except Exception as e:
            logger.error(f"Error searching Imgflip templates: {e}")
            return []