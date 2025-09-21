"""
MemeNem — Viral Meme Generator Backend
Main FastAPI application entry point with comprehensive setup.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from loguru import logger

# Import application components
from app.config import config
from app.models.database import database
from app.routes.meme_routes import router as meme_router
from app.utils.error_handlers import (
    setup_logging, validate_environment, validate_database_connection, 
    validate_ai_components, api_error_handler, http_exception_handler,
    general_exception_handler, APIError, log_api_request, log_api_response
)

# Configure logging first
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown operations.
    """
    # Startup operations
    logger.info("🚀 Starting MemeNem — Viral Meme Generator Backend")
    
    try:
        # Validate environment
        logger.info("🔧 Validating environment configuration...")
        validate_environment()
        
        # Connect to database
        logger.info("🗄️ Connecting to MongoDB...")
        await database.connect_to_database()
        await validate_database_connection()
        
        # Initialize AI components (non-critical)
        logger.info("🤖 Initializing AI components...")
        ai_available = await validate_ai_components()
        if ai_available:
            logger.success("✅ AI components initialized successfully")
        else:
            logger.warning("⚠️ AI components initialized with limitations")
        
        # Application ready
        logger.success("🎉 MemeNem backend is ready to serve viral memes!")
        logger.info(f"📍 Running on {config.app_host}:{config.app_port}")
        logger.info(f"🔍 Debug mode: {'ON' if config.debug else 'OFF'}")
        
    except Exception as e:
        logger.critical(f"💥 Startup failed: {e}")
        raise
    
    yield  # Application runs here
    
    # Shutdown operations
    logger.info("🛑 Shutting down MemeNem backend...")
    
    try:
        # Close database connection
        await database.close_database_connection()
        logger.info("📊 Database connection closed")
        
        # Cleanup operations
        logger.info("🧹 Cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("👋 MemeNem backend shutdown complete")

# Create FastAPI application
app = FastAPI(
    title="MemeNem — Viral Meme Generator",
    description="""
    🚀 **MemeNem Backend API**
    
    A production-ready backend for generating viral memes using AI-powered caption generation,
    trending template scraping, and virality prediction.
    
    ## Features
    
    * 🎭 **Smart Caption Generation** - AI-powered captions with multiple humor styles
    * 🔥 **Trending Templates** - Real-time scraping from Imgflip, Reddit, and KnowYourMeme  
    * 📊 **Virality Prediction** - ML-based scoring to predict meme viral potential
    * 🎨 **Image Processing** - Professional meme generation with PIL
    * 💾 **MongoDB Storage** - Robust data persistence and retrieval
    
    ## Humor Styles
    
    * `sarcastic` - Witty, cynical humor
    * `gen_z_slang` - Modern internet terminology and slang
    * `wholesome` - Positive, uplifting content  
    * `dark_humor` - Edgy but tasteful humor
    * `corporate_irony` - Business buzzword satire
    
    ## Usage
    
    1. **Get Templates**: Fetch trending meme templates
    2. **Generate Memes**: Create memes with AI-generated captions
    3. **Track Trends**: Monitor viral memes and upvote favorites
    4. **Score Virality**: Predict meme viral potential
    """,
    version="1.0.0",
    lifespan=lifespan,
    debug=config.debug,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://memenem-frontend.vercel.app",
        "https://memenem-frontend-7iwxt70gh-s9bs-projects.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Request/response logging middleware
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """Log all API requests and responses."""
    start_time = time.time()
    
    # Log request
    log_api_request(request)
    
    # Process request
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    log_api_response(process_time, response.status_code)
    
    # Add timing header
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

# Add error handlers
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include API routes
app.include_router(
    meme_router,
    prefix="/api/v1",
    tags=["Meme Generation"]
)

# Serve static files (generated memes)
try:
    app.mount("/generated_memes", StaticFiles(directory=config.generated_memes_path), name="memes")
except Exception as e:
    logger.warning(f"Failed to mount static files: {e}")

# Health check endpoints
@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": "MemeNem — Viral Meme Generator",
        "version": "1.0.0",
        "status": "operational",
        "message": "Ready to generate viral memes! 🚀",
        "docs": "/docs",
        "api_prefix": "/api/v1"
    }

@app.get("/health", tags=["System"])
async def health_check():
    """Comprehensive health check endpoint."""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "1.0.0",
            "services": {}
        }
        
        # Check database connection
        try:
            db = database.get_database()
            await db.command("ping")
            health_status["services"]["database"] = "healthy"
        except Exception as e:
            health_status["services"]["database"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # Check AI components
        try:
            from app.ai.caption_generator import CaptionGenerator
            from app.ai.virality_model import ViralityPredictor
            
            # Quick component test
            caption_gen = CaptionGenerator()
            virality_pred = ViralityPredictor()
            
            health_status["services"]["ai_components"] = "healthy"
        except Exception as e:
            health_status["services"]["ai_components"] = f"degraded: {str(e)}"
            if health_status["status"] == "healthy":
                health_status["status"] = "degraded"
        
        # Check file system
        import os
        try:
            os.listdir(config.generated_memes_path)
            health_status["services"]["file_system"] = "healthy"
        except Exception as e:
            health_status["services"]["file_system"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )

@app.get("/api/v1/status", tags=["System"])
async def api_status():
    """API status with configuration information."""
    return {
        "api": "MemeNem v1.0.0",
        "status": "operational",
        "endpoints": {
            "templates": "/api/v1/templates",
            "generate": "/api/v1/generate", 
            "trending": "/api/v1/trending",
            "upvote": "/api/v1/upvote",
            "score": "/api/v1/score"
        },
        "humor_styles": [
            "sarcastic",
            "gen_z_slang", 
            "wholesome",
            "dark_humor",
            "corporate_irony"
        ],
        "features": [
            "AI-powered caption generation",
            "Multi-source template scraping",
            "Virality prediction modeling",
            "Real-time meme processing",
            "MongoDB persistence"
        ]
    }

# Development server runner
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"🚀 Starting development server...")
    
    uvicorn.run(
        "main:app",
        host=config.app_host,
        port=config.app_port,
        reload=config.debug,
        log_level=config.log_level.lower(),
        access_log=True
    )