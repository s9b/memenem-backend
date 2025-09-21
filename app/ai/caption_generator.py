"""
AI-powered caption generation system for memes.
Uses HuggingFace transformers, KeyBERT for keyword extraction,
and OpenAI/custom templates for humor generation.
"""

import re
import random
from typing import Dict, List, Any, Optional
from loguru import logger
from app.config import config

# Optional imports for AI features (with safe fallbacks)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    openai = None
    OPENAI_AVAILABLE = False

# Disable KeyBERT due to dependency conflicts
# try:
#     from keybert import KeyBERT
#     KEYBERT_AVAILABLE = True
# except ImportError:
KeyBERT = None
KEYBERT_AVAILABLE = False

# Disable transformers due to dependency conflicts
# try:
#     from transformers import pipeline
#     TRANSFORMERS_AVAILABLE = True
# except ImportError:
pipeline = None
TRANSFORMERS_AVAILABLE = False

# Humor style constants
HUMOR_STYLES = [
    "sarcastic",
    "gen_z_slang", 
    "wholesome",
    "dark_humor",
    "corporate_irony"
]

class CaptionGenerator:
    """AI-powered meme caption generator with multiple humor styles."""
    
    def __init__(self):
        """Initialize the caption generator with available AI models."""
        logger.info("Initializing caption generator...")
        
        self.keybert_model = None
        self.sentiment_analyzer = None
        self.gemini_model = None
        self.openai_client = None
        
        # Initialize Gemini (preferred and most reliable)
        if GEMINI_AVAILABLE and config.gemini_api_key:
            try:
                genai.configure(api_key=config.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("Gemini model initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini model: {e}")
        
        # KeyBERT disabled due to dependency conflicts
        logger.info("Using simple keyword extraction (KeyBERT disabled)")
        
        logger.success("Caption generator ready")
    
    async def generate_caption(self, topic: str, style: str, template_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate a meme caption based on topic and humor style.
        
        Args:
            topic: The topic/theme for the meme
            style: Humor style (sarcastic, gen_z_slang, etc.)
            template_context: Optional context about the template being used
            
        Returns:
            Dictionary with generated caption and metadata
        """
        try:
            logger.info(f"Generating {style} caption for topic: {topic}")
            
            # Extract keywords from topic
            keywords = await self._extract_keywords(topic)
            
            # Analyze sentiment of the topic
            sentiment = await self._analyze_sentiment(topic)
            
            # Generate caption based on style
            if style not in HUMOR_STYLES:
                logger.warning(f"Unknown humor style: {style}, defaulting to sarcastic")
                style = "sarcastic"
            
            # Try Gemini first, fallback to template-based generation
            caption = None
            method_used = "template"
            
            if self.gemini_model:
                try:
                    caption = await self._generate_with_gemini(topic, style, keywords, template_context)
                    method_used = "gemini"
                except Exception as e:
                    logger.warning(f"Gemini generation failed: {e}, falling back to templates")
            
            if not caption:
                caption = await self._generate_with_templates(topic, style, keywords, template_context)
            
            # Clean and validate caption
            caption = self._clean_caption(caption)
            
            # Generate metadata
            metadata = {
                "keywords": keywords,
                "sentiment": sentiment,
                "style": style,
                "method": method_used,
                "topic": topic
            }
            
            result = {
                "caption": caption,
                "metadata": metadata,
                "success": True
            }
            
            logger.info(f"Successfully generated caption: {caption[:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error generating caption: {e}")
            return {
                "caption": "When something goes wrong but you're too tired to care",
                "metadata": {"error": str(e)},
                "success": False
            }
    
    async def _extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """Extract relevant keywords from text using KeyBERT."""
        try:
            if not self.keybert_model:
                # Fallback to simple keyword extraction
                return self._simple_keyword_extraction(text)
            
            # Use KeyBERT for advanced keyword extraction
            keywords = self.keybert_model.extract_keywords(
                text, 
                keyphrase_ngram_range=(1, 2), 
                stop_words='english',
                top_k=max_keywords
            )
            
            # Extract just the keyword strings
            keyword_list = [keyword[0] for keyword in keywords]
            
            logger.debug(f"Extracted keywords: {keyword_list}")
            return keyword_list
            
        except Exception as e:
            logger.warning(f"KeyBERT extraction failed: {e}, using simple extraction")
            return self._simple_keyword_extraction(text)
    
    def _simple_keyword_extraction(self, text: str) -> List[str]:
        """Simple fallback keyword extraction."""
        # Remove common words and extract meaningful terms
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        return keywords[:5]
    
    async def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of the input text."""
        try:
            if not self.sentiment_analyzer:
                return {"label": "NEUTRAL", "score": 0.5}
            
            result = self.sentiment_analyzer(text)[0]
            
            # Convert labels to standard format
            label_mapping = {
                "LABEL_0": "NEGATIVE",
                "LABEL_1": "NEUTRAL", 
                "LABEL_2": "POSITIVE"
            }
            
            label = label_mapping.get(result["label"], result["label"])
            
            return {
                "label": label,
                "score": result["score"]
            }
            
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
            return {"label": "NEUTRAL", "score": 0.5}
    
    async def _generate_with_gemini(self, topic: str, style: str, keywords: List[str], template_context: Optional[Dict]) -> Optional[str]:
        """Generate caption using Gemini API."""
        try:
            if not self.gemini_model:
                return None
            
            # Create style-specific prompt
            style_prompts = {
                "sarcastic": "Generate a sarcastic, witty meme caption that's relatable but cynical.",
                "gen_z_slang": "Generate a meme caption using Gen Z slang, internet terminology, and modern references. Use words like 'periodt', 'slay', 'no cap', 'fr fr', 'hits different', etc.",
                "wholesome": "Generate a wholesome, positive meme caption that's uplifting and heartwarming.",
                "dark_humor": "Generate a darkly humorous meme caption that's edgy but not offensive.",
                "corporate_irony": "Generate a meme caption that ironically uses corporate/business terminology and buzzwords."
            }
            
            prompt = f"""{style_prompts.get(style, style_prompts['sarcastic'])}
            
Topic: {topic}
Keywords: {', '.join(keywords)}
Template context: {template_context.get('name', 'Generic meme template') if template_context else 'Generic meme template'}

Generate only the meme caption text, keep it under 2 lines, make it punchy and relatable:"""
            
            response = self.gemini_model.generate_content(prompt)
            caption = response.text.strip() if response.text else None
            return caption
            
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            return None
    
    async def _generate_with_templates(self, topic: str, style: str, keywords: List[str], template_context: Optional[Dict]) -> str:
        """Generate caption using template-based approach."""
        try:
            # Style-specific caption templates
            templates = {
                "sarcastic": [
                    f"Oh great, another {topic}",
                    f"Because {topic} is exactly what we needed",
                    f"Nothing says fun like {topic}",
                    f"Me pretending to care about {topic}",
                    f"That moment when {topic} happens",
                    f"Ah yes, {topic}, my favorite",
                    f"When someone mentions {topic} and you're like...",
                    f"*{topic} exists*\\nMe: Why though?"
                ],
                "gen_z_slang": [
                    f"{topic} hits different fr fr",
                    f"POV: {topic} and you're not having it",
                    f"This {topic} is sending me",
                    f"Not the {topic} again bestie",
                    f"{topic} really said 'im about to end this whole vibe'",
                    f"Me when {topic}: that's sus ngl",
                    f"{topic} is giving main character energy",
                    f"No cap, {topic} is not it chief"
                ],
                "wholesome": [
                    f"When {topic} brings everyone together",
                    f"The joy of {topic} never gets old",
                    f"Sometimes {topic} is exactly what we need",
                    f"Grateful for moments like {topic}",
                    f"Nothing beats the feeling of {topic}",
                    f"When {topic} makes your day better",
                    f"The simple pleasure of {topic}",
                    f"Spreading love through {topic}"
                ],
                "dark_humor": [
                    f"When {topic} but make it existential crisis",
                    f"Me accepting that {topic} is just life now",
                    f"The void stares back but at least there's {topic}",
                    f"Another day, another {topic} to question reality",
                    f"Embracing the chaos of {topic}",
                    f"When {topic} meets your abandonment issues",
                    f"Plot twist: {topic} was the real villain",
                    f"Me and {topic} against my mental health"
                ],
                "corporate_irony": [
                    f"Let's circle back on this {topic} initiative",
                    f"This {topic} is a real game-changer for our synergy",
                    f"We need to leverage {topic} for maximum ROI",
                    f"Taking {topic} to the next level of innovation",
                    f"Streamlining our {topic} workflow for optimal output",
                    f"Let's drill down into the {topic} metrics",
                    f"Moving the needle on {topic} deliverables",
                    f"Pivoting our {topic} strategy for scalability"
                ]
            }
            
            # Get templates for the style
            style_templates = templates.get(style, templates["sarcastic"])
            
            # Choose a random template
            selected_template = random.choice(style_templates)
            
            # Enhance with keywords if possible
            if keywords and len(keywords) > 0:
                # Try to incorporate additional keywords naturally
                primary_keyword = keywords[0]
                if len(selected_template.split()) < 8:  # If template is short, try to add a keyword
                    enhancement_patterns = [
                        f"{selected_template}\\n*{primary_keyword} intensifies*",
                        f"{selected_template}\\nClassic {primary_keyword} moment",
                        f"{selected_template}\\n{primary_keyword.title()}: 'Am I a joke to you?'"
                    ]
                    selected_template = random.choice(enhancement_patterns)
            
            return selected_template
            
        except Exception as e:
            logger.error(f"Template generation error: {e}")
            # Ultimate fallback
            return f"When {topic} but you're dead inside"
    
    def _clean_caption(self, caption: str) -> str:
        """Clean and validate the generated caption."""
        if not caption:
            return "This meme speaks to my soul"
        
        # Remove quotes if present
        caption = caption.strip('"\'\'"""\'\'\'"""""')
        
        # Limit length (most memes should be short)
        if len(caption) > 200:
            caption = caption[:197] + "..."
        
        # Ensure it's not empty after cleaning
        if not caption.strip():
            return "Me trying to come up with a caption"
        
        return caption.strip()
    
    async def suggest_templates_for_topic(self, topic: str, available_templates: List[Dict]) -> List[Dict]:
        """
        Suggest the best templates for a given topic.
        
        Args:
            topic: The meme topic
            available_templates: List of available template dictionaries
            
        Returns:
            Sorted list of templates best suited for the topic
        """
        try:
            # Extract keywords from topic
            keywords = await self._extract_keywords(topic)
            topic_lower = topic.lower()
            
            scored_templates = []
            
            for template in available_templates:
                score = 0
                template_name = template.get("name", "").lower()
                template_tags = [tag.lower() for tag in template.get("tags", [])]
                
                # Score based on keyword matches
                for keyword in keywords:
                    if keyword.lower() in template_name:
                        score += 3
                    if any(keyword.lower() in tag for tag in template_tags):
                        score += 2
                
                # Score based on direct topic matches
                if any(word in template_name for word in topic_lower.split()):
                    score += 4
                
                # Bonus for popular templates
                popularity = template.get("popularity", 0)
                score += min(popularity / 20, 5)  # Up to 5 bonus points for popularity
                
                scored_templates.append((template, score))
            
            # Sort by score and return top templates
            scored_templates.sort(key=lambda x: x[1], reverse=True)
            return [template for template, score in scored_templates[:10]]
            
        except Exception as e:
            logger.error(f"Error suggesting templates: {e}")
            return available_templates[:10]  # Fallback to first 10 templates