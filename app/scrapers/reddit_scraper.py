"""
Reddit scraper using PRAW for fetching trending meme templates.
Scrapes popular posts from meme-related subreddits.
"""

import praw
import re
from typing import List, Dict, Any, Optional
from loguru import logger
from app.config import config

class RedditScraper:
    """Scraper for Reddit API using PRAW to fetch trending meme content."""
    
    def __init__(self):
        """Initialize Reddit client with credentials."""
        try:
            self.reddit = praw.Reddit(
                client_id=config.reddit_client_id,
                client_secret=config.reddit_client_secret,
                user_agent=config.reddit_user_agent
            )
            
            # Test connection
            logger.info("Reddit client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {e}")
            raise
    
    async def get_trending_templates(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch trending meme templates from Reddit.
        
        Args:
            limit: Maximum number of templates to fetch
            
        Returns:
            List of template data dictionaries
        """
        try:
            logger.info("Fetching trending meme templates from Reddit")
            
            # Target subreddits for meme templates
            subreddits = [
                "memetemplate",
                "MemeTemplatesOfficial", 
                "dankmemes",
                "memes",
                "wholesomememes",
                "AdviceAnimals"
            ]
            
            templates = []
            
            for subreddit_name in subreddits:
                try:
                    subreddit_templates = await self._scrape_subreddit(
                        subreddit_name, 
                        limit // len(subreddits) + 5
                    )
                    templates.extend(subreddit_templates)
                    
                except Exception as e:
                    logger.warning(f"Failed to scrape r/{subreddit_name}: {e}")
                    continue
            
            # Sort by popularity and limit results
            templates.sort(key=lambda x: x.get("popularity", 0), reverse=True)
            templates = templates[:limit]
            
            logger.info(f"Successfully fetched {len(templates)} templates from Reddit")
            return templates
            
        except Exception as e:
            logger.error(f"Error fetching Reddit templates: {e}")
            return []
    
    async def _scrape_subreddit(self, subreddit_name: str, limit: int) -> List[Dict[str, Any]]:
        """
        Scrape a specific subreddit for meme templates.
        
        Args:
            subreddit_name: Name of subreddit to scrape
            limit: Maximum posts to process
            
        Returns:
            List of template data from the subreddit
        """
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            templates = []
            
            # Get hot posts from subreddit
            for submission in subreddit.hot(limit=limit):
                template_data = await self._process_submission(submission, subreddit_name)
                if template_data:
                    templates.append(template_data)
            
            return templates
            
        except Exception as e:
            logger.error(f"Error scraping r/{subreddit_name}: {e}")
            return []
    
    async def _process_submission(self, submission, subreddit_name: str) -> Optional[Dict[str, Any]]:
        """
        Process a Reddit submission into template data.
        
        Args:
            submission: PRAW submission object
            subreddit_name: Name of the source subreddit
            
        Returns:
            Template data dictionary or None if not suitable
        """
        try:
            # Skip text posts or posts without images
            if not hasattr(submission, 'url') or not submission.url:
                return None
            
            # Check if URL contains image
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            url_lower = submission.url.lower()
            
            # Handle different image hosting sites
            image_url = None
            if any(ext in url_lower for ext in image_extensions):
                image_url = submission.url
            elif 'imgur.com' in url_lower:
                image_url = await self._process_imgur_url(submission.url)
            elif 'reddit.com' in url_lower and '/r/' in url_lower:
                # Reddit hosted image
                if hasattr(submission, 'preview') and submission.preview:
                    try:
                        image_url = submission.preview['images'][0]['source']['url']
                    except (KeyError, IndexError):
                        pass
            
            if not image_url:
                return None
            
            # Generate template ID
            template_id = f"reddit_{submission.id}"
            
            # Clean and process title
            title = self._clean_title(submission.title)
            if not title:
                return None
            
            # Generate tags
            tags = await self._generate_tags(title, subreddit_name)
            
            # Calculate popularity based on Reddit metrics
            popularity = await self._calculate_popularity(submission)
            
            template_data = {
                "template_id": template_id,
                "name": title,
                "url": image_url,
                "tags": tags,
                "popularity": popularity,
                "source": "reddit",
                "subreddit": subreddit_name,
                "upvotes": submission.score,
                "comments": submission.num_comments
            }
            
            return template_data
            
        except Exception as e:
            logger.error(f"Error processing submission {submission.id}: {e}")
            return None
    
    async def _process_imgur_url(self, url: str) -> Optional[str]:
        """
        Convert Imgur URLs to direct image links.
        
        Args:
            url: Imgur URL
            
        Returns:
            Direct image URL or None
        """
        try:
            # Convert imgur gallery/album URLs to direct image URLs
            if 'imgur.com/' in url:
                if '/gallery/' in url or '/a/' in url:
                    # Extract image ID and convert to direct link
                    img_id = url.split('/')[-1]
                    return f"https://i.imgur.com/{img_id}.jpg"
                elif 'imgur.com/' in url and not url.startswith('https://i.imgur.com'):
                    # Add i. subdomain and .jpg extension if needed
                    img_id = url.split('/')[-1]
                    if '.' not in img_id:
                        return f"https://i.imgur.com/{img_id}.jpg"
                    else:
                        return f"https://i.imgur.com/{img_id}"
            
            return url
            
        except Exception:
            return url
    
    def _clean_title(self, title: str) -> str:
        """
        Clean and normalize Reddit post title for use as template name.
        
        Args:
            title: Raw Reddit post title
            
        Returns:
            Cleaned template name
        """
        # Remove common Reddit prefixes/suffixes
        cleaned = re.sub(r'\\[(OC|Original Content|Template|Meme Template)\\]', '', title, flags=re.IGNORECASE)
        cleaned = re.sub(r'Template:?\\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'Meme\\s*Template:?\\s*', '', cleaned, flags=re.IGNORECASE)
        
        # Remove excessive punctuation
        cleaned = re.sub(r'[!]{2,}', '!', cleaned)
        cleaned = re.sub(r'[?]{2,}', '?', cleaned)
        
        # Clean whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Limit length
        if len(cleaned) > 100:
            cleaned = cleaned[:97] + "..."
        
        return cleaned.strip()
    
    async def _generate_tags(self, title: str, subreddit: str) -> List[str]:
        """
        Generate relevant tags based on title and subreddit.
        
        Args:
            title: Template title
            subreddit: Source subreddit
            
        Returns:
            List of relevant tags
        """
        tags = ["meme", "reddit", subreddit.lower()]
        title_lower = title.lower()
        
        # Common meme/template keywords
        keyword_patterns = {
            "drake": ["choice", "preference"],
            "cat": ["animal", "pet"],
            "dog": ["animal", "pet"],
            "woman": ["person", "reaction"],
            "guy": ["person", "reaction"],
            "thinking": ["contemplation"],
            "pointing": ["accusation"],
            "success": ["celebration"],
            "fail": ["failure"],
            "surprised": ["shock", "reaction"],
            "angry": ["mad", "emotion"],
            "happy": ["joy", "emotion"],
            "sad": ["emotion"],
            "work": ["office", "job"],
            "school": ["education"],
            "meeting": ["corporate"],
            "monday": ["weekday"],
            "friday": ["weekday"],
            "morning": ["time"],
            "night": ["time"]
        }
        
        for keyword, related_tags in keyword_patterns.items():
            if keyword in title_lower:
                tags.extend(related_tags)
        
        # Subreddit-specific tags
        subreddit_tags = {
            "dankmemes": ["dank", "edgy"],
            "wholesomememes": ["wholesome", "positive"],
            "adviceanimals": ["advice", "animal"],
            "memetemplate": ["template"],
            "memetemplatesofficial": ["template", "official"]
        }
        
        if subreddit.lower() in subreddit_tags:
            tags.extend(subreddit_tags[subreddit.lower()])
        
        return list(set(tags))
    
    async def _calculate_popularity(self, submission) -> float:
        """
        Calculate popularity score based on Reddit metrics.
        
        Args:
            submission: PRAW submission object
            
        Returns:
            Popularity score (0-100)
        """
        try:
            # Base score from upvotes (log scale)
            upvotes = max(submission.score, 1)
            upvote_score = min(50.0, 10.0 * (upvotes ** 0.3))
            
            # Engagement score from comments
            comments = submission.num_comments
            comment_score = min(25.0, comments * 0.5)
            
            # Award score (if available)
            award_score = 0
            if hasattr(submission, 'all_awardings') and submission.all_awardings:
                award_count = sum(award.get('count', 0) for award in submission.all_awardings)
                award_score = min(15.0, award_count * 2)
            
            # Recency bonus (newer posts get slight boost)
            import time
            hours_old = (time.time() - submission.created_utc) / 3600
            recency_score = max(0, 10.0 - (hours_old * 0.1))
            
            total_score = upvote_score + comment_score + award_score + recency_score
            return min(100.0, total_score)
            
        except Exception:
            return 50.0  # Default score if calculation fails