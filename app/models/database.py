"""
Database connection and initialization module for MemeNem.
Handles MongoDB connection using Motor for async operations.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from loguru import logger
from app.config import config

class Database:
    """MongoDB database manager with async connection handling."""
    
    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.database: AsyncIOMotorDatabase = None
    
    async def connect_to_database(self):
        """Establish connection to MongoDB database."""
        try:
            logger.info("Connecting to MongoDB...")
            self.client = AsyncIOMotorClient(config.mongodb_uri)
            
            # Extract database name from URI or use default
            if '/' in config.mongodb_uri:
                # Parse URI to get database name, removing query parameters
                db_part = config.mongodb_uri.split('/')[-1]
                db_name = db_part.split('?')[0] if '?' in db_part else db_part
                if not db_name:  # Handle case where URI ends with /
                    db_name = "memenem"
            else:
                db_name = "memenem"
            
            self.database = self.client[db_name]
            
            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"Successfully connected to MongoDB database: {db_name}")
            
            # Initialize collections and indexes
            await self._initialize_collections()
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def close_database_connection(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")
    
    async def _initialize_collections(self):
        """Initialize database collections with proper indexes."""
        try:
            # Create indexes for templates collection
            templates_collection = self.database.templates
            await templates_collection.create_index("template_id", unique=True)
            await templates_collection.create_index("popularity", background=True)
            await templates_collection.create_index([("tags", 1)], background=True)
            
            # Create indexes for memes collection  
            memes_collection = self.database.memes
            await memes_collection.create_index("meme_id", unique=True)
            await memes_collection.create_index("timestamp", background=True)
            await memes_collection.create_index("virality_score", background=True)
            await memes_collection.create_index("upvotes", background=True)
            await memes_collection.create_index([("upvotes", -1), ("virality_score", -1)], background=True)
            
            logger.info("Database collections and indexes initialized successfully")
            
        except Exception as e:
            logger.warning(f"Failed to create some indexes: {e}")
    
    def get_database(self) -> AsyncIOMotorDatabase:
        """Get database instance."""
        return self.database

# Global database instance
database = Database()