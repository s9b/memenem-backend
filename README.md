# MemeNem — Viral Meme Generator Backend 🚀

A production-ready FastAPI backend for generating viral memes using AI-powered caption generation, trending template scraping, and virality prediction.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green.svg)
![MongoDB](https://img.shields.io/badge/MongoDB-5.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-blue.svg)

## 🎯 Features

- 🎭 **Smart Caption Generation** - AI-powered captions with multiple humor styles
- 🔥 **Trending Templates** - Real-time scraping from Imgflip, Reddit, and KnowYourMeme
- 📊 **Virality Prediction** - ML-based scoring to predict meme viral potential
- 🎨 **Image Processing** - Professional meme generation with PIL
- 💾 **MongoDB Storage** - Robust data persistence and retrieval
- 🛡️ **Production Ready** - Comprehensive error handling, logging, and monitoring

## 🏗️ Architecture

```
memenem-backend/
├── app/
│   ├── __init__.py
│   ├── config.py              # Environment configuration
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py        # MongoDB connection
│   │   └── schemas.py         # Pydantic models
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── imgflip_scraper.py # Imgflip API scraper
│   │   ├── reddit_scraper.py  # Reddit/PRAW scraper
│   │   └── knowyourmeme_scraper.py # Web scraper
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── caption_generator.py # AI caption generation
│   │   ├── meme_generator.py    # Image processing
│   │   └── virality_model.py    # ML virality prediction
│   ├── routes/
│   │   ├── __init__.py
│   │   └── meme_routes.py     # FastAPI endpoints
│   └── utils/
│       ├── __init__.py
│       └── error_handlers.py  # Error handling & logging
├── data/
│   └── sample_memes/
│       └── sample_dataset.json # Training data
├── generated_memes/           # Generated meme storage
├── logs/                      # Application logs
├── main.py                    # FastAPI app entry point
├── requirements.txt           # Python dependencies
├── .env.template             # Environment variables template
├── .gitignore
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- MongoDB 5.0+
- Redis (optional, for caching)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd memenem-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.template .env
   # Edit .env with your credentials (see Configuration section)
   ```

5. **Start MongoDB**
   ```bash
   # Using Docker
   docker run -d -p 27017:27017 --name mongodb mongo:5.0
   
   # Or using local MongoDB
   mongod --dbpath /path/to/your/db
   ```

6. **Run the application**
   ```bash
   python main.py
   # Or using uvicorn directly
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health
   - API Status: http://localhost:8000/api/v1/status

## ⚙️ Configuration

Create a `.env` file with the following variables:

```env
# Required: Reddit API credentials
REDDIT_CLIENT_ID=your_reddit_client_id_here
REDDIT_CLIENT_SECRET=your_reddit_client_secret_here
REDDIT_USER_AGENT=MemeNem:v1.0.0 (by /u/yourusername)

# Required: Imgflip API credentials
IMGFLIP_API_USERNAME=your_imgflip_username
IMGFLIP_API_PASSWORD=your_imgflip_password

# Required: At least one AI API key
OPENAI_API_KEY=your_openai_api_key_here
# OR
STABLE_DIFFUSION_KEY=your_stable_diffusion_key_here

# Required: MongoDB connection
MONGODB_URI=mongodb://localhost:27017/memenem

# Application settings
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=True
LOG_LEVEL=INFO
GENERATED_MEMES_PATH=./generated_memes
```

### Getting API Keys

#### Reddit API
1. Go to https://www.reddit.com/prefs/apps
2. Create a new application (type: script)
3. Note your client ID and secret

#### Imgflip API
1. Register at https://imgflip.com/api
2. Get your username and password

#### OpenAI API
1. Sign up at https://platform.openai.com/
2. Create an API key in your dashboard

## 📡 API Endpoints

### Templates
```http
GET /api/v1/templates?limit=50&source=imgflip
```
Get trending meme templates from various sources.

**Parameters:**
- `limit` (int): Maximum number of templates (default: 50)
- `source` (str): Specific source (imgflip, reddit, knowyourmeme)

### Generate Meme
```http
POST /api/v1/generate
Content-Type: application/json

{
  "topic": "Monday morning meetings",
  "style": "sarcastic",
  "template_id": "drake_pointing" // optional
}
```

**Humor Styles:**
- `sarcastic` - Witty, cynical humor
- `gen_z_slang` - Modern internet terminology
- `wholesome` - Positive, uplifting content
- `dark_humor` - Edgy but tasteful humor
- `corporate_irony` - Business buzzword satire

### Trending Memes
```http
GET /api/v1/trending?limit=20&sort_by=virality_score
```
Get trending memes sorted by popularity metrics.

**Parameters:**
- `limit` (int): Maximum number of memes (default: 20)
- `sort_by` (str): Sort criteria (virality_score, upvotes, timestamp)

### Upvote Meme
```http
POST /api/v1/upvote
Content-Type: application/json

{
  "meme_id": "abc12345"
}
```

### Calculate Virality Score
```http
POST /api/v1/score?meme_id=abc12345
```

## 🤖 AI Components

### Caption Generation
The AI caption generator uses:
- **KeyBERT** for keyword extraction
- **HuggingFace Transformers** for sentiment analysis
- **OpenAI GPT** for advanced caption generation (when available)
- **Template-based fallback** for reliable operation

### Virality Prediction
The ML model predicts viral potential using:
- Template popularity
- Caption characteristics
- Humor style effectiveness
- Timing factors
- Historical performance data

**Model Features:**
- Template popularity score
- Caption length optimization
- Humor style encoding
- Keyword relevance matching
- Temporal factors (time of day, weekday)

## 🗄️ Database Schema

### Templates Collection
```javascript
{
  "_id": ObjectId,
  "template_id": "imgflip_123456",
  "name": "Drake Pointing",
  "url": "https://i.imgflip.com/123.jpg",
  "tags": ["choice", "preference", "reaction"],
  "popularity": 95.0,
  "source": "imgflip",
  "box_count": 2,
  "width": 400,
  "height": 400,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### Memes Collection
```javascript
{
  "_id": ObjectId,
  "meme_id": "abc12345",
  "template_id": "imgflip_123456",
  "template_name": "Drake Pointing",
  "caption": "Checking email vs Actually responding to email",
  "style": "sarcastic",
  "image_url": "/generated_memes/meme_abc12345_20240120_143000.jpg",
  "virality_score": 87.5,
  "upvotes": 1250,
  "timestamp": ISODate,
  "generation_metadata": {
    "topic": "work productivity",
    "template_source": "imgflip",
    "caption_method": "openai",
    "virality_factors": { ... }
  }
}
```

## 🔧 Development

### Running Tests
```bash
pytest tests/ -v
```

### Code Formatting
```bash
black app/ main.py
isort app/ main.py
```

### Type Checking
```bash
mypy app/ main.py
```

## 📊 Monitoring & Logging

### Health Checks
- `GET /health` - Comprehensive system health
- `GET /api/v1/status` - API-specific status

### Logging
Logs are written to:
- Console (formatted with colors in development)
- `logs/memenem.log` (application logs, 7-day retention)
- `logs/errors.log` (error logs, 30-day retention)

### Error Tracking
The application includes comprehensive error tracking:
- Custom error types for different components
- Automatic fallbacks for AI processing failures
- Graceful degradation when external APIs fail
- Detailed error context and debugging information

## 🚀 Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production
```env
DEBUG=False
LOG_LEVEL=INFO
MONGODB_URI=mongodb://prod-mongodb:27017/memenem
APP_HOST=0.0.0.0
APP_PORT=8000
```

### Performance Optimization
- Use MongoDB connection pooling
- Enable Redis caching for templates
- Configure proper CORS origins
- Set up reverse proxy (nginx)
- Enable gzip compression
- Implement rate limiting

## 📈 Scaling Considerations

### Horizontal Scaling
- Stateless design allows easy horizontal scaling
- Generated memes should be stored in shared storage (S3, etc.)
- Database connections are pooled and thread-safe
- API responses include timing headers for monitoring

### Caching Strategy
- Template data (Redis, 1-hour TTL)
- Virality model predictions (Redis, 24-hour TTL)
- Generated meme metadata (Database indexes)

## 🔐 Security

### API Security
- Input validation with Pydantic models
- SQL injection prevention (NoSQL MongoDB)
- Rate limiting (recommended: 100 req/min per IP)
- CORS configuration for production
- Error message sanitization in production mode

### Credential Management
- Environment variables for all sensitive data
- No credentials stored in code or logs
- Secure API key rotation procedures
- MongoDB authentication enabled

## 🐛 Troubleshooting

### Common Issues

1. **"Missing required environment variables"**
   - Ensure `.env` file exists and contains all required variables
   - Check that environment variables are properly loaded

2. **"Database connection failed"**
   - Verify MongoDB is running and accessible
   - Check MONGODB_URI format and credentials
   - Ensure database exists and user has proper permissions

3. **"AI components initialized with limitations"**
   - Check API keys for OpenAI/Stable Diffusion
   - Verify internet connectivity for model downloads
   - Review logs for specific AI component errors

4. **"Template scraping failed"**
   - Verify API credentials for Reddit and Imgflip
   - Check internet connectivity and firewall settings
   - Review rate limiting and API quotas

### Debug Mode
Enable debug mode for detailed error information:
```env
DEBUG=True
LOG_LEVEL=DEBUG
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run pre-commit hooks
pre-commit install

# Run tests before committing
pytest tests/ --cov=app/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **FastAPI** for the excellent async web framework
- **MongoDB** for reliable document storage
- **HuggingFace** for transformer models and AI tools
- **OpenAI** for advanced language model capabilities
- **Reddit API & PRAW** for meme template sourcing
- **Imgflip** for meme template data
- **PIL/Pillow** for robust image processing

## 📞 Support

For support, please:
1. Check the troubleshooting section above
2. Review application logs in the `logs/` directory
3. Open an issue on GitHub with:
   - Error messages and stack traces
   - Environment configuration (without sensitive data)
   - Steps to reproduce the issue

---

**Made with ❤️ for the meme community** 🚀