"""
KnowYourMeme web scraper for fetching trending meme templates.
Uses BeautifulSoup for web scraping of trending pages.
"""

import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from loguru import logger
import re
import asyncio

class KnowYourMemeScraper:
    """Web scraper for KnowYourMeme trending pages."""
    
    def __init__(self):
        self.base_url = "https://knowyourmeme.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
    
    async def get_trending_templates(self, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch trending meme templates from KnowYourMeme.
        
        Args:
            limit: Maximum number of templates to fetch
            
        Returns:
            List of template data dictionaries
        """
        try:
            logger.info("Fetching trending templates from KnowYourMeme")
            
            templates = []
            
            # Scrape multiple pages for more variety
            pages_to_scrape = [
                "/memes/trending",
                "/memes/popular", 
                "/photos/trending"
            ]
            
            for page_path in pages_to_scrape:
                try:
                    page_templates = await self._scrape_page(page_path, limit // len(pages_to_scrape) + 5)
                    templates.extend(page_templates)
                    
                    # Add delay between requests to be respectful
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"Failed to scrape {page_path}: {e}")
                    continue
            
            # Remove duplicates and sort by popularity
            seen_ids = set()
            unique_templates = []
            for template in templates:
                if template["template_id"] not in seen_ids:
                    seen_ids.add(template["template_id"])
                    unique_templates.append(template)
            
            unique_templates.sort(key=lambda x: x.get("popularity", 0), reverse=True)
            unique_templates = unique_templates[:limit]
            
            logger.info(f"Successfully fetched {len(unique_templates)} unique templates from KnowYourMeme")
            return unique_templates
            
        except Exception as e:
            logger.error(f"Error fetching KnowYourMeme templates: {e}")
            return []
    
    async def _scrape_page(self, page_path: str, limit: int) -> List[Dict[str, Any]]:
        """
        Scrape a specific page on KnowYourMeme.
        
        Args:
            page_path: Path to scrape (e.g., "/memes/trending")
            limit: Maximum templates to extract from this page
            
        Returns:
            List of template data from the page
        """
        try:
            url = f"{self.base_url}{page_path}"
            
            async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch {url}: HTTP {response.status_code}")
                    return []
                
                soup = BeautifulSoup(response.content, 'html.parser')
                templates = []
                
                # Find meme entries on the page
                meme_entries = soup.find_all(['td', 'div', 'article'], class_=re.compile(r'(meme|entry|item)'))
                
                for entry in meme_entries[:limit]:
                    template_data = await self._process_entry(entry)
                    if template_data:
                        templates.append(template_data)
                
                return templates
                
        except Exception as e:
            logger.error(f"Error scraping page {page_path}: {e}")
            return []
    
    async def _process_entry(self, entry) -> Optional[Dict[str, Any]]:
        """
        Process a single meme entry from KnowYourMeme.
        
        Args:
            entry: BeautifulSoup element containing meme data
            
        Returns:
            Template data dictionary or None if processing failed
        """
        try:
            # Extract title/name
            title_elem = entry.find(['h1', 'h2', 'h3', 'h4', 'a'], class_=re.compile(r'(title|name|link)'))
            if not title_elem:
                title_elem = entry.find('a')
            
            if not title_elem or not title_elem.get_text(strip=True):
                return None
            
            name = title_elem.get_text(strip=True)
            name = self._clean_title(name)
            
            if not name or len(name) < 3:
                return None
            
            # Extract image URL
            img_elem = entry.find('img')
            if not img_elem or not img_elem.get('src'):
                return None
            
            image_url = img_elem.get('src')
            
            # Convert relative URLs to absolute
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = self.base_url + image_url
            
            # Skip very small images (likely icons/avatars)
            if 'icon' in image_url or 'avatar' in image_url or '/small/' in image_url:
                return None
            
            # Generate template ID from name or URL
            template_id = self._generate_template_id(name, image_url)
            
            # Extract additional metadata if available
            views = self._extract_views(entry)
            likes = self._extract_likes(entry)
            
            # Generate tags based on title and content
            tags = await self._generate_tags(name, entry)
            
            # Calculate popularity based on available metrics
            popularity = await self._calculate_popularity(name, views, likes)
            
            template_data = {
                "template_id": f"kym_{template_id}",
                "name": name,
                "url": image_url,
                "tags": tags,
                "popularity": popularity,
                "source": "knowyourmeme",
                "views": views,
                "likes": likes
            }
            
            return template_data
            
        except Exception as e:
            logger.error(f"Error processing KYM entry: {e}")
            return None
    
    def _clean_title(self, title: str) -> str:
        """
        Clean and normalize KnowYourMeme title.
        
        Args:
            title: Raw title from KYM
            
        Returns:
            Cleaned title
        """
        # Remove common KYM artifacts
        cleaned = re.sub(r'\\s*\\|\\s*Know Your Meme', '', title, flags=re.IGNORECASE)
        cleaned = re.sub(r'Meme\\s*:', '', cleaned, flags=re.IGNORECASE)
        
        # Clean excessive punctuation
        cleaned = re.sub(r'[!]{2,}', '!', cleaned)
        cleaned = re.sub(r'[?]{2,}', '?', cleaned)
        
        # Clean whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Remove quotes
        cleaned = cleaned.strip('"\'\'"""\'\'\'')
        
        # Limit length
        if len(cleaned) > 80:
            cleaned = cleaned[:77] + "..."
        
        return cleaned.strip()
    
    def _generate_template_id(self, name: str, url: str) -> str:
        """
        Generate a unique template ID from name or URL.
        
        Args:
            name: Template name
            url: Template image URL
            
        Returns:
            Unique template identifier
        """
        # Try to extract ID from URL first
        url_match = re.search(r'/([^/]+)\\.(jpg|jpeg|png|gif|webp)', url, re.IGNORECASE)
        if url_match:
            return url_match.group(1)
        
        # Fallback to name-based ID
        cleaned_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
        return cleaned_name[:30]
    
    def _extract_views(self, entry) -> Optional[int]:
        """Extract view count if available."""
        try:
            views_elem = entry.find(text=re.compile(r'\\d+\\s*(views?|Views?)', re.IGNORECASE))
            if views_elem:
                views_match = re.search(r'([\\d,]+)', views_elem)
                if views_match:
                    return int(views_match.group(1).replace(',', ''))
        except:
            pass
        return None
    
    def _extract_likes(self, entry) -> Optional[int]:
        """Extract like/upvote count if available."""
        try:
            likes_elem = entry.find(class_=re.compile(r'(like|vote|point)'))
            if likes_elem:
                likes_text = likes_elem.get_text()
                likes_match = re.search(r'([\\d,]+)', likes_text)
                if likes_match:
                    return int(likes_match.group(1).replace(',', ''))
        except:
            pass
        return None
    
    async def _generate_tags(self, name: str, entry) -> List[str]:
        """
        Generate relevant tags for a KnowYourMeme template.
        
        Args:
            name: Template name
            entry: BeautifulSoup entry element
            
        Returns:
            List of relevant tags
        """
        tags = ["meme", "knowyourmeme", "template"]
        name_lower = name.lower()
        
        # Extract text from entry for additional context
        entry_text = entry.get_text().lower() if entry else ""
        
        # Common meme categories and keywords
        category_patterns = {
            "reaction": ["reaction", "facial", "expression", "response"],
            "animal": ["cat", "dog", "pet", "animal", "bear", "bird"],
            "person": ["guy", "girl", "man", "woman", "person", "face"],
            "character": ["character", "cartoon", "anime", "movie", "tv"],
            "object": ["object", "thing", "item"],
            "text": ["text", "caption", "words", "saying"],
            "situation": ["situation", "scenario", "moment", "when"],
            "emotion": ["happy", "sad", "angry", "surprised", "confused", "excited"],
            "internet": ["internet", "online", "social", "twitter", "facebook"],
            "gaming": ["game", "gaming", "gamer", "video game"],
            "pop_culture": ["movie", "tv", "celebrity", "famous", "show"],
            "workplace": ["work", "office", "job", "boss", "meeting"],
            "school": ["school", "student", "teacher", "education"]
        }
        
        # Add category tags based on name and content
        for category, keywords in category_patterns.items():
            if any(keyword in name_lower or keyword in entry_text for keyword in keywords):
                tags.append(category)
        
        # Add specific keywords found in name
        specific_keywords = {
            "drake": ["choice", "preference"], 
            "distracted": ["distraction", "choice"],
            "success": ["achievement", "win"],
            "disaster": ["fail", "chaos"],
            "surprised": ["shock", "unexpected"],
            "thinking": ["contemplation", "decision"],
            "pointing": ["accusation", "blame"],
            "crying": ["sad", "tears"],
            "laughing": ["humor", "funny"],
            "ancient": ["old", "historical"],
            "modern": ["new", "contemporary"]
        }
        
        for keyword, related_tags in specific_keywords.items():
            if keyword in name_lower:
                tags.extend(related_tags)
        
        return list(set(tags))
    
    async def _calculate_popularity(self, name: str, views: Optional[int], likes: Optional[int]) -> float:
        """
        Calculate popularity score for KnowYourMeme template.
        
        Args:
            name: Template name
            views: View count (if available)
            likes: Like count (if available)
            
        Returns:
            Popularity score (0-100)
        """
        score = 30.0  # Base score
        
        # Add points for views (log scale)
        if views:
            view_score = min(40.0, 10.0 * (views ** 0.2))
            score += view_score
        
        # Add points for likes/votes
        if likes:
            like_score = min(20.0, likes * 0.1)
            score += like_score
        
        # Bonus points for well-known meme names
        name_lower = name.lower()
        famous_memes = [
            "drake", "distracted boyfriend", "woman yelling at cat", 
            "surprised pikachu", "this is fine", "expanding brain",
            "change my mind", "two buttons", "first time", "disaster girl"
        ]
        
        if any(famous in name_lower for famous in famous_memes):
            score += 15.0
        
        return min(100.0, score)