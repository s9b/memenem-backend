"""
Pydantic models and schemas for MemeNem application.
Defines data structures for templates, memes, and API requests/responses.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Annotated
from pydantic import BaseModel, Field, BeforeValidator
from bson import ObjectId

# Simple ObjectId validator for Pydantic v2
def validate_object_id(v) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str):
        if ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid ObjectId")
    raise ValueError("Invalid ObjectId")

# Use Annotated type for ObjectId fields
PyObjectId = Annotated[str, BeforeValidator(validate_object_id), Field(description="MongoDB ObjectId")]

# Template Models
class TemplateBase(BaseModel):
    """Base template model with common fields."""
    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template name")
    url: str = Field(..., description="Template image URL")
    tags: List[str] = Field(default_factory=list, description="Template tags/categories")
    popularity: float = Field(default=0.0, description="Template popularity score")

class TemplateInDB(TemplateBase):
    """Template model as stored in database."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(..., description="Source of template (reddit, imgflip, knowyourmeme)")
    box_count: Optional[int] = Field(None, description="Number of text boxes for template")
    width: Optional[int] = Field(None, description="Template image width")
    height: Optional[int] = Field(None, description="Template image height")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class Template(TemplateBase):
    """Template model for API responses."""
    source: str
    created_at: Optional[datetime] = None
    box_count: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None

# Meme Models
class MemeBase(BaseModel):
    """Base meme model with common fields."""
    template_id: str = Field(..., description="Reference to template used")
    caption: str = Field(..., description="Generated meme caption")
    style: str = Field(..., description="Humor style used for generation")

class MemeInDB(MemeBase):
    """Meme model as stored in database."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    meme_id: str = Field(..., description="Unique meme identifier")
    template_name: str = Field(..., description="Name of template used")
    image_url: str = Field(..., description="URL to generated meme image")
    virality_score: float = Field(default=0.0, description="Predicted virality score (0-100)")
    upvotes: int = Field(default=0, description="Number of upvotes")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    generation_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata about generation process")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class Meme(MemeBase):
    """Meme model for API responses."""
    meme_id: str
    template_name: str
    image_url: str
    virality_score: float
    upvotes: int
    timestamp: datetime

class MemeVariation(BaseModel):
    """Single meme variation with caption(s) and metadata."""
    variation_id: int = Field(..., description="Variation identifier")
    caption: Optional[str] = Field(None, description="Single caption for simple templates")
    captions: Optional[Dict[str, str]] = Field(None, description="Multiple captions for multi-panel templates")
    virality_score: float = Field(..., description="Predicted virality score for this variation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Generation metadata")

class MemeTemplate(BaseModel):
    """Enhanced meme template with generation results."""
    template_id: str
    template_name: str
    image_url: str
    panel_count: int = Field(default=1, description="Number of panels/sections in template")
    characters: List[str] = Field(default_factory=list, description="Characters/subjects in template")
    variations: List[MemeVariation] = Field(..., description="Generated caption variations")
    average_virality_score: float = Field(..., description="Average virality score across variations")

# Request Models
class GenerateMemeRequest(BaseModel):
    """Request model for meme generation."""
    topic: str = Field(..., min_length=1, max_length=200, description="Topic/theme for meme generation")
    style: str = Field(..., description="Humor style for caption generation")
    template_id: Optional[str] = Field(None, description="Specific template to use (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Monday morning meetings",
                "style": "sarcastic",
                "template_id": "drake_pointing"
            }
        }

class UpvoteRequest(BaseModel):
    """Request model for upvoting memes."""
    meme_id: str = Field(..., description="ID of meme to upvote")

# Response Models
class GenerateMemeResponse(BaseModel):
    """Response model for meme generation."""
    success: bool
    meme: Meme
    message: Optional[str] = None

class GenerateMemesResponse(BaseModel):
    """Response model for multi-variation meme generation."""
    success: bool
    templates: List[MemeTemplate] = Field(..., description="Generated meme templates with variations")
    count: int = Field(..., description="Total number of templates returned")
    message: Optional[str] = None

class TemplatesResponse(BaseModel):
    """Response model for templates listing."""
    success: bool
    templates: List[Template]
    count: int

class TrendingMemesResponse(BaseModel):
    """Response model for trending memes."""
    success: bool
    memes: List[Meme]
    count: int

class UpvoteResponse(BaseModel):
    """Response model for upvote action."""
    success: bool
    new_upvote_count: int
    message: Optional[str] = None

class ViralityScoreResponse(BaseModel):
    """Response model for virality score calculation."""
    success: bool
    meme_id: str
    virality_score: float
    factors: Dict[str, Any]

class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    error: str
    detail: Optional[str] = None

# Job Management Models for Async Processing
class JobStatus(BaseModel):
    """Job status for async meme generation."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: queued, processing, completed, failed")
    progress: float = Field(default=0.0, description="Progress percentage (0-100)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    total_templates: Optional[int] = Field(None, description="Total number of templates to process")
    completed_templates: Optional[int] = Field(None, description="Number of completed templates")
    error_message: Optional[str] = Field(None, description="Error message if failed")

class JobRequest(BaseModel):
    """Request model for async meme generation job."""
    topic: str = Field(..., min_length=1, max_length=200, description="Topic/theme for meme generation")
    style: str = Field(..., description="Humor style for caption generation")
    max_templates: int = Field(default=5, ge=1, le=10, description="Maximum number of templates to generate")
    variations_per_template: int = Field(default=4, ge=1, le=6, description="Number of caption variations per template")
    template_id: Optional[str] = Field(None, description="Specific template to use (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Monday morning meetings",
                "style": "sarcastic",
                "max_templates": 5,
                "variations_per_template": 4
            }
        }

class JobSubmissionResponse(BaseModel):
    """Response model for job submission."""
    success: bool
    job_id: str
    status: str
    estimated_completion_time: Optional[int] = Field(None, description="Estimated completion time in seconds")
    message: Optional[str] = None

class JobResultResponse(BaseModel):
    """Response model for job results."""
    success: bool
    job_id: str
    status: str
    progress: float
    templates: List[MemeTemplate] = Field(default_factory=list, description="Generated meme templates with variations")
    count: int = Field(default=0, description="Total number of templates returned")
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    processing_time: Optional[float] = Field(None, description="Total processing time in seconds")

class CachedCaption(BaseModel):
    """Cached caption model for MongoDB storage."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    cache_key: str = Field(..., description="Unique cache key for caption")
    topic: str = Field(..., description="Meme topic")
    style: str = Field(..., description="Humor style")
    template_id: str = Field(..., description="Template ID")
    caption: Optional[str] = Field(None, description="Single caption")
    captions: Optional[Dict[str, str]] = Field(None, description="Multi-panel captions")
    virality_score: float = Field(..., description="Virality score")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    hit_count: int = Field(default=1, description="Number of times this caption was used")
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class BatchProgress(BaseModel):
    """Progress tracking for batch processing."""
    batch_id: str
    total_items: int
    completed_items: int
    failed_items: int
    current_item: Optional[str] = None
    errors: List[str] = Field(default_factory=list)

# Humor style enum
HUMOR_STYLES = [
    "sarcastic",
    "gen_z_slang", 
    "wholesome",
    "dark_humor",
    "corporate_irony"
]

# Job status constants
JOB_STATUS = {
    "QUEUED": "queued",
    "PROCESSING": "processing", 
    "COMPLETED": "completed",
    "FAILED": "failed",
    "CANCELLED": "cancelled"
}
