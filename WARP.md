# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

MemeNem is a production-ready FastAPI backend for generating viral memes using AI-powered caption generation, trending template scraping, and virality prediction. The system combines multiple data sources (Reddit, Imgflip, KnowYourMeme) with AI models to create contextually relevant and humorous memes.

## Quick Start Commands

### Development Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.template .env
# Edit .env with your API credentials

# Start MongoDB (if using Docker)
docker run -d -p 27017:27017 --name mongodb mongo:5.0

# Run the development server
python main.py
# Alternative: uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing and Quality
```bash
# Run all tests
pytest tests/ -v

# Code formatting
black app/ main.py
isort app/ main.py

# Type checking
mypy app/ main.py

# Check API documentation
# Navigate to http://localhost:8000/docs
```

### Database Operations
```bash
# Connect to MongoDB shell
mongosh mongodb://localhost:27017/memenem

# Check collections
db.templates.countDocuments({})
db.memes.countDocuments({})

# View recent memes
db.memes.find().sort({timestamp: -1}).limit(5)
```

## Architecture Overview

### Core Application Structure
- **FastAPI Application**: Async web framework with automatic OpenAPI documentation
- **MongoDB with Motor**: Async database operations for templates and generated memes
- **AI Pipeline**: Multi-stage caption generation with keyword extraction, sentiment analysis, and OpenAI integration
- **Web Scrapers**: Template acquisition from Reddit (PRAW), Imgflip API, and KnowYourMeme
- **Image Processing**: PIL-based meme generation with text overlay

### Key Components

#### Database Layer (`app/models/`)
- `database.py`: Motor async MongoDB client with connection pooling and index management
- `schemas.py`: Pydantic models for templates, memes, and API contracts
- Collections: `templates` (scraped meme templates), `memes` (generated content)

#### AI System (`app/ai/`)
- `caption_generator.py`: Multi-model caption generation (KeyBERT + HuggingFace + OpenAI)
- `virality_model.py`: ML-based virality prediction using template popularity and content features
- `meme_generator.py`: PIL-based image processing for text overlay generation

#### Data Sources (`app/scrapers/`)
- `reddit_scraper.py`: PRAW-based trending template discovery
- `imgflip_scraper.py`: Imgflip API integration for popular templates
- `knowyourmeme_scraper.py`: Web scraping for meme template metadata

#### API Layer (`app/routes/`)
- `meme_routes.py`: All API endpoints with comprehensive error handling
- Endpoints: `/templates`, `/generate`, `/trending`, `/upvote`, `/score`

### Humor Styles System
The application supports multiple humor generation styles:
- `sarcastic`: Witty, cynical humor
- `gen_z_slang`: Modern internet terminology
- `wholesome`: Positive, uplifting content
- `dark_humor`: Edgy but tasteful humor
- `corporate_irony`: Business buzzword satire

### Configuration Management
Environment-based configuration via `app/config.py` with validation for:
- Required API keys (Reddit, Imgflip, at least one AI provider)
- Database connection strings
- Application settings (host, port, debug mode)
- File paths for generated content

## Development Guidelines

### API Credentials Required
The application requires multiple external API credentials:
- **Reddit API**: Client ID, secret, user agent (for template scraping)
- **Imgflip API**: Username, password (for template data)
- **AI Provider**: OpenAI API key or Stable Diffusion key (for caption generation)
- **MongoDB**: Connection URI (for data persistence)

### Error Handling Pattern
The codebase uses comprehensive error handling with graceful degradation:
- AI components fall back to template-based generation when APIs fail
- Scraper failures don't block the entire template fetching process
- Custom `APIError` exceptions with detailed logging via Loguru
- Health check endpoints for monitoring system component status

### Database Design
MongoDB collections with strategic indexing:
- **Templates**: Indexed on `template_id` (unique), `popularity`, and `tags`
- **Memes**: Indexed on `meme_id` (unique), `timestamp`, `virality_score`, and composite upvotes+virality

### AI Pipeline Architecture
Three-tier caption generation system:
1. **Keyword Extraction**: KeyBERT for topic-relevant terms
2. **Sentiment Analysis**: CardiffNLP Twitter RoBERTa model
3. **Caption Generation**: OpenAI GPT (primary) with template-based fallback

### Background Processing
Uses FastAPI's `BackgroundTasks` for non-blocking operations:
- Template storage and database updates
- Virality score calculations
- Image processing and file I/O operations

## Common Debugging Approaches

### Component Health Checks
```bash
# Check overall system health
curl http://localhost:8000/health

# Test database connectivity
curl http://localhost:8000/api/v1/status

# Verify AI components initialization
# Check application logs for "AI components initialized" messages
```

### Template Scraping Issues
If template fetching fails, check each source individually:
- Reddit API rate limiting and credential validity
- Imgflip API quota and authentication
- Network connectivity for KnowYourMeme web scraping

### AI Generation Failures
The system includes multiple fallback layers:
1. OpenAI API (if available and configured)
2. HuggingFace local models (GPT-2, RoBERTa)
3. Template-based humor generation
4. Hard-coded fallback captions

### Performance Monitoring
Response timing headers are automatically added (`X-Process-Time`), and comprehensive logging tracks:
- API request/response patterns
- AI model initialization and usage
- Database query performance
- External API call latencies

## Testing Approaches

When writing tests for this codebase:
- Mock external API calls (Reddit, Imgflip, OpenAI) to avoid rate limiting
- Use MongoDB test containers or in-memory databases
- Test humor style variations and caption quality metrics
- Validate error handling paths and graceful degradation
- Test image processing with various template formats and sizes

## Production Considerations

- Enable MongoDB authentication and SSL
- Configure CORS origins appropriately (currently set to `*` for development)
- Set up reverse proxy (nginx) for static file serving
- Implement API rate limiting per client IP
- Use Redis caching for template data and virality predictions
- Monitor AI model memory usage and implement model rotation if needed