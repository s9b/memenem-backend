"""
MemeNem — Viral Meme Generator Backend
Optimized for Render Free Tier with lazy loading and minimal memory usage.
"""

import os
import time
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

# Only import essential FastAPI components at startup
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

# Essential imports only - heavy imports are done lazily
from app.config import config
from app.models.database import database

# Configure logging for startup tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global lazy-loaded components cache
_lazy_components = {}

def get_lazy_component(component_name: str):
    """Lazy loading for heavy components to minimize startup memory."""
    if component_name in _lazy_components:
        return _lazy_components[component_name]
    
    logger.info(f"🔄 Lazy loading component: {component_name}")
    start_time = time.time()
    
    if component_name == "scrapers":
        from app.scrapers.imgflip_scraper import ImgflipScraper
        from app.scrapers.reddit_scraper import RedditScraper
        from app.scrapers.knowyourmeme_scraper import KnowYourMemeScraper
        
        _lazy_components["scrapers"] = {
            "imgflip": ImgflipScraper(),
            "reddit": RedditScraper(), 
            "kym": KnowYourMemeScraper()
        }
        
    elif component_name == "ai_components":
        from app.ai.caption_generator import CaptionGenerator
        from app.ai.meme_generator import MemeGenerator
        from app.ai.virality_model import ViralityPredictor
        
        _lazy_components["ai_components"] = {
            "caption_generator": CaptionGenerator(),
            "meme_generator": MemeGenerator(),
            "virality_predictor": ViralityPredictor()
        }
    
    elif component_name == "routes":
        # Import routes lazily to avoid loading dependencies at startup
        from app.routes.meme_routes_optimized import router as meme_router
        _lazy_components["routes"] = {"meme_router": meme_router}
    
    load_time = time.time() - start_time
    logger.info(f"✅ Loaded {component_name} in {load_time:.2f}s")
    
    return _lazy_components[component_name]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lightweight application lifespan manager for Render free tier.
    Heavy initialization is deferred to first request.
    """
    startup_start = time.time()
    logger.info("🚀 Starting MemeNem Backend (Render Optimized)")
    
    try:
        # Only validate environment (fast)
        logger.info("🔧 Validating environment configuration...")
        from app.utils.error_handlers import validate_environment
        validate_environment()
        
        # Connect to database (essential)
        logger.info("🗄️ Connecting to MongoDB...")
        await database.connect_to_database()
        
        # Quick database ping (no complex validation)
        db = database.get_database()
        await db.command("ping")
        logger.info("📊 Database connected successfully")
        
        # Create generated_memes directory if it doesn't exist
        os.makedirs(config.generated_memes_path, exist_ok=True)
        logger.info(f"📁 Generated memes path ready: {config.generated_memes_path}")
        
        # Load routes (lightweight)
        routes = get_lazy_component("routes")
        app.include_router(
            routes["meme_router"],
            prefix="/api/v1",
            tags=["Meme Generation"]
        )
        
        startup_time = time.time() - startup_start
        logger.info(f"🎉 MemeNem backend startup complete in {startup_time:.2f}s!")
        logger.info(f"📍 Ready to serve on port {config.app_port}")
        logger.info("💡 Heavy components (AI, scrapers) will load on first request")
        
    except Exception as e:
        logger.error(f"💥 Startup failed: {e}")
        raise
    
    yield  # Application runs here
    
    # Shutdown operations
    logger.info("🛑 Shutting down MemeNem backend...")
    
    try:
        await database.close_database_connection()
        logger.info("📊 Database connection closed")
        
        # Clear lazy components cache
        _lazy_components.clear()
        logger.info("🧹 Component cache cleared")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("👋 MemeNem backend shutdown complete")

# Create FastAPI application with minimal configuration
app = FastAPI(
    title="MemeNem — Viral Meme Generator",
    description="""
    🚀 **MemeNem Backend API (Render Optimized)**
    
    A production-ready backend for generating viral memes with AI-powered captions,
    optimized for Render free tier with lazy loading and minimal memory usage.
    
    ## Features
    
    * 🎭 **Smart Caption Generation** - AI-powered captions with multiple humor styles
    * 🔥 **Multi-Variation Templates** - 4-5 caption options per relevant template  
    * 📊 **Virality Prediction** - ML-based scoring for viral potential
    * 🎨 **Multi-Panel Support** - Batman/Robin, Drake, and complex meme formats
    * 💾 **MongoDB Caching** - Template and meme persistence
    
    ## Optimization Features
    
    * ⚡ **Lazy Loading** - Heavy components load only when needed
    * 🔄 **Memory Efficient** - Optimized for 512MB free tier limits
    * 🚀 **Fast Startup** - Essential services only during initialization
    
    ## Usage
    
    1. **Get Templates**: `GET /api/v1/templates` - Fetch available meme templates
    2. **Generate Single Meme**: `POST /api/v1/generate` - Quick single meme generation
    3. **Generate Variations**: `POST /api/v1/generate-variations` - Multiple caption options
    4. **Health Check**: `GET /health` - Service status
    """,
    version="1.0.0",
    lifespan=lifespan,
    debug=config.debug,
)

# Add CORS middleware (lightweight)
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
    allowed_hosts=["*"]
)

# Request timing middleware (lightweight)
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header for monitoring."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Serve static files (generated memes)
try:
    app.mount("/generated_memes", StaticFiles(directory=config.generated_memes_path), name="memes")
    logger.info(f"📁 Static files mounted: {config.generated_memes_path}")
except Exception as e:
    logger.warning(f"Failed to mount static files: {e}")

# Lightweight health check endpoint (no dependencies)
@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": "MemeNem — Viral Meme Generator",
        "version": "1.0.0",
        "status": "operational",
        "message": "Ready to generate viral memes! 🚀",
        "optimization": "Render Free Tier Optimized",
        "docs": "/docs",
        "api_prefix": "/api/v1",
        "features": [
            "Lazy loading for memory efficiency",
            "Multi-variation meme generation", 
            "AI-powered captions",
            "Multi-panel support"
        ]
    }

@app.get("/health", tags=["System"])
async def health_check():
    """Fast health check endpoint without heavy dependencies."""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "1.0.0",
            "memory_optimized": True,
            "services": {}
        }
        
        # Quick database check
        try:
            db = database.get_database()
            await db.command("ping")
            health_status["services"]["database"] = "healthy"
        except Exception as e:
            health_status["services"]["database"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # File system check
        try:
            import os
            os.listdir(config.generated_memes_path)
            health_status["services"]["file_system"] = "healthy"
        except Exception as e:
            health_status["services"]["file_system"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # Lazy components status (don't load them, just check if cached)
        health_status["services"]["lazy_components"] = {
            "scrapers": "cached" if "scrapers" in _lazy_components else "lazy",
            "ai_components": "cached" if "ai_components" in _lazy_components else "lazy",
            "routes": "cached" if "routes" in _lazy_components else "lazy"
        }
        
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
        "optimization": "Render Free Tier",
        "memory_model": "Lazy Loading",
        "endpoints": {
            "templates": "/api/v1/templates",
            "generate": "/api/v1/generate", 
            "generate_variations": "/api/v1/generate-variations",
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
            "Lazy-loaded AI components",
            "Memory-optimized scrapers",
            "Multi-variation generation",
            "Multi-panel meme support",
            "Template caching",
            "Rate limit handling"
        ],
        "lazy_components": {
            component: "loaded" if component in _lazy_components else "pending"
            for component in ["scrapers", "ai_components", "routes"]
        }
    }

# Error handlers (lightweight)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": time.time()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "timestamp": time.time()
        }
    )

# Development server runner
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", config.app_port))
    logger.info(f"🚀 Starting development server on port {port}...")
    
    uvicorn.run(
        "main_optimized:app",
        host="0.0.0.0",
        port=port,
        reload=config.debug,
        log_level="info" if not config.debug else "debug",
        access_log=True
    )