"""
Configuration module for MemeNem backend.
Handles loading and validating environment variables.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration class with environment variable validation."""
    
    def __init__(self):
        """Initialize configuration and validate required environment variables."""
        self._validate_required_vars()
    
    def _validate_required_vars(self):
        """Validate that all required environment variables are present."""
        required_vars = [
            'REDDIT_CLIENT_ID',
            'REDDIT_CLIENT_SECRET', 
            'REDDIT_USER_AGENT',
            'IMGFLIP_API_USERNAME',
            'IMGFLIP_API_PASSWORD',
            'MONGODB_URI'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            logger.error("Please create a .env file based on .env.template and fill in the required values.")
            raise ValueError(error_msg)
        
        # Check for at least one AI API key (Gemini is preferred for free tier)
        if not (os.getenv('GEMINI_API_KEY') or os.getenv('OPENAI_API_KEY') or os.getenv('STABLE_DIFFUSION_KEY')):
            error_msg = "At least one AI API key required: GEMINI_API_KEY (recommended, free), OPENAI_API_KEY, or STABLE_DIFFUSION_KEY"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    # Reddit API configuration
    @property
    def reddit_client_id(self) -> str:
        return os.getenv('REDDIT_CLIENT_ID')
    
    @property
    def reddit_client_secret(self) -> str:
        return os.getenv('REDDIT_CLIENT_SECRET')
    
    @property
    def reddit_user_agent(self) -> str:
        return os.getenv('REDDIT_USER_AGENT')
    
    # Imgflip API configuration
    @property
    def imgflip_username(self) -> str:
        return os.getenv('IMGFLIP_API_USERNAME')
    
    @property
    def imgflip_password(self) -> str:
        return os.getenv('IMGFLIP_API_PASSWORD')
    
    # AI API configuration
    @property
    def gemini_api_key(self) -> Optional[str]:
        return os.getenv('GEMINI_API_KEY')
    
    @property
    def openai_api_key(self) -> Optional[str]:
        return os.getenv('OPENAI_API_KEY')
    
    @property
    def stable_diffusion_key(self) -> Optional[str]:
        return os.getenv('STABLE_DIFFUSION_KEY')
    
    # Database configuration
    @property
    def mongodb_uri(self) -> str:
        return os.getenv('MONGODB_URI')
    
    # Application settings
    @property
    def app_host(self) -> str:
        return os.getenv('APP_HOST', '0.0.0.0')
    
    @property
    def app_port(self) -> int:
        return int(os.getenv('APP_PORT', 8000))
    
    @property
    def debug(self) -> bool:
        return os.getenv('DEBUG', 'False').lower() == 'true'
    
    @property
    def generated_memes_path(self) -> str:
        return os.getenv('GENERATED_MEMES_PATH', './generated_memes')
    
    @property
    def log_level(self) -> str:
        return os.getenv('LOG_LEVEL', 'INFO')
    
    @property
    def backend_url(self) -> str:
        # Use localhost for development, production URL for deployment
        if self.debug:
            return os.getenv('BACKEND_URL', 'http://localhost:8000')
        return os.getenv('BACKEND_URL', 'https://memenem-backend.onrender.com')

# Global configuration instance
config = Config()
