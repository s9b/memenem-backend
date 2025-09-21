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
            limit: Maximum number of templates to fetch (0 for all available)
            
        Returns:
            List of template data dictionaries
        """
        try:
            logger.info("Fetching templates from Imgflip API")
            
            async with httpx.AsyncClient() as client:
                # Get all available templates
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
                
                # Process all templates or up to limit
                memes_to_process = memes if limit == 0 else memes[:limit]
                
                for i, meme in enumerate(memes_to_process):
                    meme["_position"] = i  # Add position for popularity calculation
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
            
            # Generate tags and detect characters/panels
            tags = await self._generate_tags(name)
            characters = await self._detect_characters(name)
            panel_info = await self._analyze_panel_structure(name, box_count)
            
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
                "panel_count": panel_info["panel_count"],
                "characters": characters,
                "panel_layout": panel_info["layout"],
                "width": width,
                "height": height,
                "created_at": None,
                "updated_at": None
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
    
    async def _detect_characters(self, template_name: str) -> List[str]:
        """
        Detect characters/subjects in a meme template based on its name.
        
        Args:
            template_name: Name of the template
            
        Returns:
            List of character names or descriptions
        """
        name_lower = template_name.lower()
        characters = []
        
        # Character detection patterns
        character_patterns = {
            "batman": ["Batman", "Robin"],
            "drake": ["Drake"],
            "distracted boyfriend": ["Boyfriend", "Girlfriend", "Other Woman"],
            "disaster girl": ["Girl"],
            "success kid": ["Kid"],
            "grumpy cat": ["Grumpy Cat"],
            "doge": ["Doge"],
            "woman yelling": ["Woman", "Cat"],
            "expanding brain": ["Person"],
            "bernie": ["Bernie Sanders"],
            "change my mind": ["Steven Crowder"],
            "leonardo dicaprio": ["Leonardo DiCaprio"],
            "morpheus": ["Morpheus"],
            "ancient aliens": ["Giorgio Tsoukalos"],
            "picard": ["Captain Picard"],
            "gru": ["Gru"],
            "two buttons": ["Person"],
            "running away balloon": ["Person"],
            "epic handshake": ["Person 1", "Person 2"],
            "anakin padme": ["Anakin", "Padme"],
            "waiting skeleton": ["Skeleton"],
            "pablo escobar": ["Pablo Escobar"]
        }
        
        # Detect characters based on name
        for pattern, chars in character_patterns.items():
            if pattern in name_lower:
                characters.extend(chars)
                break
        
        # Fallback: generic character detection
        if not characters:
            if any(word in name_lower for word in ["guy", "man", "person"]):
                characters = ["Person"]
            elif any(word in name_lower for word in ["woman", "girl"]):
                characters = ["Woman"]
            elif any(word in name_lower for word in ["cat", "dog", "animal"]):
                characters = ["Animal"]
            else:
                characters = ["Character"]
        
        return characters
    
    async def _analyze_panel_structure(self, template_name: str, box_count: int) -> Dict[str, Any]:
        """
        Analyze the panel structure of a meme template.
        
        Args:
            template_name: Name of the template
            box_count: Number of text boxes in the template
            
        Returns:
            Dictionary with panel information
        """
        name_lower = template_name.lower()
        
        # Multi-panel templates
        multi_panel_patterns = {
            "batman slapping robin": {"panel_count": 2, "layout": "side_by_side"},
            "drake hotline bling": {"panel_count": 2, "layout": "vertical"},
            "distracted boyfriend": {"panel_count": 1, "layout": "single"},
            "two buttons": {"panel_count": 3, "layout": "mixed"},
            "expanding brain": {"panel_count": 4, "layout": "vertical"},
            "gru's plan": {"panel_count": 4, "layout": "grid"},
            "anakin padme": {"panel_count": 4, "layout": "grid"},
            "running away balloon": {"panel_count": 5, "layout": "mixed"},
            "epic handshake": {"panel_count": 3, "layout": "mixed"}
        }
        
        # Check for known multi-panel templates
        for pattern, info in multi_panel_patterns.items():
            if pattern in name_lower:
                return info
        
        # Fallback based on box_count
        if box_count <= 1:
            return {"panel_count": 1, "layout": "single"}
        elif box_count == 2:
            return {"panel_count": 2, "layout": "vertical"}
        elif box_count >= 3:
            return {"panel_count": box_count, "layout": "mixed"}
        else:
            return {"panel_count": 1, "layout": "single"}
    
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