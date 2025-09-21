"""
Comprehensive error handling and logging utilities for MemeNem backend.
"""

import sys
import traceback
from typing import Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from app.config import config

# Configure loguru logger
def setup_logging():
    """Configure application logging with loguru."""
    
    # Remove default handler
    logger.remove()
    
    # Add console handler with formatting
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=config.log_level,
        colorize=True
    )
    
    # Add file handler for persistent logs
    logger.add(
        "logs/memenem.log",
        rotation="1 day",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        compression="zip"
    )
    
    # Add error file handler
    logger.add(
        "logs/errors.log", 
        rotation="1 day",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        backtrace=True,
        diagnose=True
    )

class APIError(Exception):
    """Custom API error with structured information."""
    
    def __init__(
        self, 
        message: str, 
        status_code: int = 500, 
        error_code: str = None,
        details: Dict[str, Any] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or f"API_ERROR_{status_code}"
        self.details = details or {}
        super().__init__(self.message)

class ConfigurationError(APIError):
    """Error related to configuration or environment setup."""
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="CONFIGURATION_ERROR",
            details=details
        )

class ScrapingError(APIError):
    """Error related to web scraping operations."""
    
    def __init__(self, message: str, source: str = None, details: Dict[str, Any] = None):
        details = details or {}
        if source:
            details["source"] = source
        
        super().__init__(
            message=message,
            status_code=503,
            error_code="SCRAPING_ERROR", 
            details=details
        )

class AIProcessingError(APIError):
    """Error related to AI/ML processing."""
    
    def __init__(self, message: str, component: str = None, details: Dict[str, Any] = None):
        details = details or {}
        if component:
            details["component"] = component
            
        super().__init__(
            message=message,
            status_code=500,
            error_code="AI_PROCESSING_ERROR",
            details=details
        )

class DatabaseError(APIError):
    """Error related to database operations."""
    
    def __init__(self, message: str, operation: str = None, details: Dict[str, Any] = None):
        details = details or {}
        if operation:
            details["operation"] = operation
            
        super().__init__(
            message=message,
            status_code=500,
            error_code="DATABASE_ERROR",
            details=details
        )

async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors."""
    logger.error(f"API Error: {exc.message} (Code: {exc.error_code})")
    
    if exc.details:
        logger.error(f"Error details: {exc.details}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.message,
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    logger.warning(f"HTTP Exception: {exc.detail} (Status: {exc.status_code})")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "error_code": f"HTTP_ERROR_{exc.status_code}"
        }
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {str(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Don't expose internal errors in production
    if config.debug:
        error_message = str(exc)
        details = {"traceback": traceback.format_exc()}
    else:
        error_message = "An internal server error occurred"
        details = {}
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": error_message,
            "error_code": "INTERNAL_SERVER_ERROR",
            "details": details
        }
    )

def log_api_request(request: Request):
    """Log incoming API request."""
    logger.info(f"{request.method} {request.url.path} - Client: {request.client.host}")

def log_api_response(response_time: float, status_code: int):
    """Log API response."""
    logger.info(f"Response: {status_code} - Time: {response_time:.3f}s")

class ErrorTracker:
    """Track and analyze application errors."""
    
    def __init__(self):
        self.error_counts = {}
        self.recent_errors = []
        
    def record_error(self, error: Exception, context: str = None):
        """Record an error occurrence."""
        error_type = type(error).__name__
        
        # Update counts
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        
        # Track recent errors (keep last 100)
        error_info = {
            "type": error_type,
            "message": str(error),
            "context": context,
            "timestamp": logger._core.now()
        }
        
        self.recent_errors.append(error_info)
        if len(self.recent_errors) > 100:
            self.recent_errors.pop(0)
        
        logger.error(f"Error recorded: {error_type} in {context}: {str(error)}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of recent errors."""
        return {
            "error_counts": self.error_counts,
            "recent_errors": self.recent_errors[-10:],  # Last 10 errors
            "total_errors": sum(self.error_counts.values())
        }

# Global error tracker instance
error_tracker = ErrorTracker()

def handle_scraper_errors(func):
    """Decorator to handle scraper errors gracefully."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            source = getattr(func, '__self__', {}).get('__class__', {}).get('__name__', 'Unknown')
            error_tracker.record_error(e, f"Scraper: {source}")
            
            # Don't fail completely, return empty results
            logger.warning(f"Scraper error in {source}: {e}")
            return []
    
    return wrapper

def handle_ai_errors(func):
    """Decorator to handle AI processing errors gracefully.""" 
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            component = getattr(func, '__self__', {}).get('__class__', {}).get('__name__', 'Unknown')
            error_tracker.record_error(e, f"AI: {component}")
            
            # Return fallback result for AI errors
            logger.warning(f"AI processing error in {component}: {e}")
            
            # Return appropriate fallback based on function name
            if 'caption' in func.__name__.lower():
                return {
                    "success": False,
                    "caption": "When AI fails but you still need a meme",
                    "metadata": {"error": str(e)}
                }
            elif 'virality' in func.__name__.lower():
                return {
                    "success": False, 
                    "virality_score": 50.0,
                    "factors": {"error": "Prediction unavailable"}
                }
            else:
                raise AIProcessingError(f"AI processing failed: {str(e)}", component)
    
    return wrapper

def handle_database_errors(func):
    """Decorator to handle database errors gracefully."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            operation = func.__name__
            error_tracker.record_error(e, f"Database: {operation}")
            
            logger.error(f"Database error in {operation}: {e}")
            raise DatabaseError(f"Database operation failed: {str(e)}", operation)
    
    return wrapper

# Startup validation functions
def validate_environment():
    """Validate environment configuration on startup."""
    try:
        # Test that config loads properly
        from app.config import config
        
        # Check required directories exist
        import os
        os.makedirs("logs", exist_ok=True)
        os.makedirs("data", exist_ok=True) 
        os.makedirs(config.generated_memes_path, exist_ok=True)
        
        logger.info("Environment validation passed")
        
    except Exception as e:
        logger.critical(f"Environment validation failed: {e}")
        raise ConfigurationError(f"Environment setup failed: {str(e)}")

async def validate_database_connection():
    """Validate database connection on startup."""
    try:
        from app.models.database import database
        
        # Test database connection
        db = database.get_database()
        if db is None:
            raise DatabaseError("Failed to get database instance")
            
        # Try to ping the database
        await db.command("ping")
        logger.info("Database connection validated")
        
    except Exception as e:
        logger.critical(f"Database validation failed: {e}")
        raise DatabaseError(f"Database connection failed: {str(e)}")

async def validate_ai_components():
    """Validate AI components on startup."""
    try:
        # Test that AI components can be imported and initialized
        from app.ai.caption_generator import CaptionGenerator
        from app.ai.virality_model import ViralityPredictor
        
        # Basic initialization test
        caption_gen = CaptionGenerator()
        virality_pred = ViralityPredictor()
        
        logger.info("AI components validation passed")
        
    except Exception as e:
        logger.warning(f"AI components validation failed: {e}")
        # AI failures are not critical for startup
        return False
    
    return True