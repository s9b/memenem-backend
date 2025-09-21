"""
Meme generation system using PIL for image processing.
Handles template downloading, caption overlay, and meme creation.
"""

import os
import io
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont
import requests
from loguru import logger
from app.config import config

class MemeGenerator:
    """PIL-based meme generator for creating memes with caption overlays."""
    
    def __init__(self):
        self.generated_memes_path = config.generated_memes_path
        self.default_fonts = self._load_system_fonts()
        
        # Ensure output directory exists
        os.makedirs(self.generated_memes_path, exist_ok=True)
    
    def _load_system_fonts(self) -> Dict[str, str]:
        """Load available system fonts for text rendering."""
        fonts = {}
        
        # Common font paths by OS
        font_paths = [
            # macOS
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Arial.ttf", 
            "/System/Library/Fonts/Impact.ttc",
            
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            
            # Windows (if running on Windows)
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/impact.ttf"
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                font_name = os.path.basename(font_path).split('.')[0].lower()
                fonts[font_name] = font_path
                break
        
        # Fallback to default if no system fonts found
        if not fonts:
            logger.warning("No system fonts found, using PIL default font")
            fonts["default"] = None
        
        logger.info(f"Available fonts: {list(fonts.keys())}")
        return fonts
    
    async def create_meme(self, template_data: Dict[str, Any], caption: str, style: str) -> Dict[str, Any]:
        """
        Create a meme by overlaying caption on template image.
        
        Args:
            template_data: Template information including URL
            caption: Caption text to overlay
            style: Humor style (affects text styling)
            
        Returns:
            Dictionary with meme creation results
        """
        try:
            logger.info(f"Creating meme with template: {template_data.get('name', 'Unknown')}")
            
            # Download template image
            template_image = await self._download_template(template_data["url"])
            if not template_image:
                return {"success": False, "error": "Failed to download template image"}
            
            # Process caption for optimal display
            processed_caption = self._process_caption_text(caption)
            
            # Create meme with caption overlay
            meme_image = await self._overlay_caption(template_image, processed_caption, style)
            
            # Generate unique filename
            meme_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"meme_{meme_id}_{timestamp}.jpg"
            file_path = os.path.join(self.generated_memes_path, filename)
            
            # Save meme image
            meme_image.save(file_path, "JPEG", quality=95, optimize=True)
            
            # Get file size and dimensions
            file_size = os.path.getsize(file_path)
            width, height = meme_image.size
            
            result = {
                "success": True,
                "meme_id": meme_id,
                "filename": filename,
                "file_path": file_path,
                "width": width,
                "height": height,
                "file_size": file_size,
                "template_id": template_data["template_id"],
                "caption": caption,
                "style": style
            }
            
            logger.info(f"Successfully created meme: {filename}")
            return result
            
        except Exception as e:
            logger.error(f"Error creating meme: {e}")
            return {"success": False, "error": str(e)}
    
    async def _download_template(self, template_url: str) -> Optional[Image.Image]:
        """
        Download template image from URL.
        
        Args:
            template_url: URL of the template image
            
        Returns:
            PIL Image object or None if failed
        """
        try:
            logger.debug(f"Downloading template from: {template_url}")
            
            # Set up headers to avoid blocks
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(template_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Load image from response content
            image = Image.open(io.BytesIO(response.content))
            
            # Convert to RGB if needed (handles RGBA, P, etc.)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            logger.debug(f"Template downloaded successfully: {image.size}")
            return image
            
        except Exception as e:
            logger.error(f"Failed to download template: {e}")
            return None
    
    def _process_caption_text(self, caption: str) -> str:
        """
        Process caption text for optimal display on meme.
        
        Args:
            caption: Raw caption text
            
        Returns:
            Processed caption text
        """
        # Convert newline characters to actual newlines
        caption = caption.replace('\\n', '\n')
        
        # Split long lines for better readability
        lines = caption.split('\n')
        processed_lines = []
        
        for line in lines:
            if len(line) > 40:  # If line is too long, try to split it
                words = line.split()
                current_line = []
                current_length = 0
                
                for word in words:
                    if current_length + len(word) + 1 <= 40:
                        current_line.append(word)
                        current_length += len(word) + 1
                    else:
                        if current_line:
                            processed_lines.append(' '.join(current_line))
                            current_line = [word]
                            current_length = len(word)
                        else:
                            # Word itself is too long, just add it
                            processed_lines.append(word)
                
                if current_line:
                    processed_lines.append(' '.join(current_line))
            else:
                processed_lines.append(line)
        
        return '\\n'.join(processed_lines)
    
    async def _overlay_caption(self, template_image: Image.Image, caption: str, style: str) -> Image.Image:
        """
        Overlay caption text on template image.
        
        Args:
            template_image: PIL Image object of template
            caption: Processed caption text
            style: Humor style for text formatting
            
        Returns:
            PIL Image with caption overlaid
        """
        try:
            # Create a copy of the template to work with
            meme_image = template_image.copy()
            draw = ImageDraw.Draw(meme_image)
            
            # Get image dimensions
            img_width, img_height = meme_image.size
            
            # Split caption into lines
            lines = caption.split('\\n')
            
            # Determine text positioning strategy
            positioning = self._determine_text_positioning(lines, img_width, img_height)
            
            # Load appropriate font
            font = self._get_font_for_style(style, img_width)
            
            # Style-specific text properties
            text_color, stroke_color, stroke_width = self._get_text_style_properties(style)
            
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                
                # Calculate text position
                x, y = self._calculate_text_position(
                    line, font, positioning, i, len(lines), img_width, img_height, draw
                )
                
                # Draw text with outline for better readability
                self._draw_text_with_outline(
                    draw, x, y, line, font, text_color, stroke_color, stroke_width
                )
            
            return meme_image
            
        except Exception as e:
            logger.error(f"Error overlaying caption: {e}")
            return template_image  # Return original if overlay fails
    
    def _determine_text_positioning(self, lines: List[str], img_width: int, img_height: int) -> Dict[str, Any]:
        """
        Determine optimal text positioning strategy based on content and image.
        
        Args:
            lines: Caption lines
            img_width: Image width
            img_height: Image height
            
        Returns:
            Positioning strategy dictionary
        """
        # Default to classic top/bottom positioning for memes
        if len(lines) == 1:
            return {"strategy": "center", "position": "center"}
        elif len(lines) == 2:
            return {"strategy": "top_bottom", "positions": ["top", "bottom"]}
        else:
            # Multiple lines - stack them
            return {"strategy": "stacked", "position": "top"}
    
    def _get_font_for_style(self, style: str, img_width: int) -> ImageFont.FreeTypeFont:
        """
        Get appropriate font based on style and image size.
        
        Args:
            style: Humor style
            img_width: Image width for font sizing
            
        Returns:
            PIL Font object
        """
        try:
            # Calculate font size based on image width
            base_font_size = max(20, min(img_width // 20, 60))
            
            # Style-specific font preferences
            style_fonts = {
                "sarcastic": ["impact", "helvetica", "arial"],
                "gen_z_slang": ["arial", "helvetica"],
                "wholesome": ["helvetica", "arial"],
                "dark_humor": ["impact", "arial"],
                "corporate_irony": ["arial", "helvetica"]
            }
            
            preferred_fonts = style_fonts.get(style, ["impact", "arial", "helvetica"])
            
            # Try to load preferred fonts
            for font_name in preferred_fonts:
                if font_name in self.default_fonts and self.default_fonts[font_name]:
                    try:
                        return ImageFont.truetype(self.default_fonts[font_name], base_font_size)
                    except Exception:
                        continue
            
            # Fallback to default font
            return ImageFont.load_default()
            
        except Exception as e:
            logger.warning(f"Error loading font: {e}, using default")
            return ImageFont.load_default()
    
    def _get_text_style_properties(self, style: str) -> Tuple[str, str, int]:
        """
        Get text color, stroke color, and stroke width for style.
        
        Args:
            style: Humor style
            
        Returns:
            Tuple of (text_color, stroke_color, stroke_width)
        """
        style_properties = {
            "sarcastic": ("white", "black", 3),
            "gen_z_slang": ("white", "black", 2),
            "wholesome": ("white", "black", 2),
            "dark_humor": ("white", "black", 3),
            "corporate_irony": ("white", "black", 2)
        }
        
        return style_properties.get(style, ("white", "black", 2))
    
    def _calculate_text_position(self, text: str, font: ImageFont.FreeTypeFont, 
                                positioning: Dict[str, Any], line_index: int, 
                                total_lines: int, img_width: int, img_height: int,
                                draw: ImageDraw.Draw) -> Tuple[int, int]:
        """
        Calculate optimal position for text line.
        
        Args:
            text: Text line to position
            font: Font to use
            positioning: Positioning strategy
            line_index: Index of current line
            total_lines: Total number of lines
            img_width: Image width
            img_height: Image height
            draw: ImageDraw object for text measurement
            
        Returns:
            Tuple of (x, y) coordinates
        """
        try:
            # Get text bounding box for centering
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Center horizontally by default
            x = (img_width - text_width) // 2
            
            # Vertical positioning based on strategy
            strategy = positioning.get("strategy", "center")
            
            if strategy == "center":
                y = (img_height - text_height) // 2
            
            elif strategy == "top_bottom":
                positions = positioning.get("positions", ["top", "bottom"])
                position = positions[line_index] if line_index < len(positions) else "top"
                
                if position == "top":
                    y = img_height // 10  # 10% from top
                else:  # bottom
                    y = img_height - img_height // 8 - text_height  # 12.5% from bottom
            
            elif strategy == "stacked":
                # Stack lines from top
                y = (img_height // 10) + (line_index * text_height * 1.2)
                y = int(y)
            
            else:
                # Default center
                y = (img_height - text_height) // 2
            
            return (x, y)
            
        except Exception as e:
            logger.warning(f"Error calculating text position: {e}")
            # Fallback to simple center
            return (img_width // 4, img_height // 2)
    
    def _draw_text_with_outline(self, draw: ImageDraw.Draw, x: int, y: int, 
                               text: str, font: ImageFont.FreeTypeFont,
                               text_color: str, stroke_color: str, stroke_width: int):
        """
        Draw text with outline for better visibility.
        
        Args:
            draw: ImageDraw object
            x, y: Text position
            text: Text to draw
            font: Font to use
            text_color: Main text color
            stroke_color: Outline color
            stroke_width: Outline width
        """
        try:
            # Draw text with stroke/outline
            draw.text(
                (x, y), 
                text, 
                font=font, 
                fill=text_color,
                stroke_fill=stroke_color,
                stroke_width=stroke_width
            )
            
        except Exception as e:
            # Fallback for older PIL versions without stroke support
            logger.debug(f"Stroke not supported, drawing simple text: {e}")
            
            # Draw outline manually by drawing text multiple times offset
            for adj_x in range(-stroke_width, stroke_width + 1):
                for adj_y in range(-stroke_width, stroke_width + 1):
                    if adj_x != 0 or adj_y != 0:
                        draw.text((x + adj_x, y + adj_y), text, font=font, fill=stroke_color)
            
            # Draw main text on top
            draw.text((x, y), text, font=font, fill=text_color)
    
    def get_meme_url(self, filename: str) -> str:
        """
        Generate URL for accessing generated meme.
        
        Args:
            filename: Meme filename
            
        Returns:
            URL string for accessing the meme
        """
        # Return full backend URL for cross-origin access
        return f"{config.backend_url}/generated_memes/{filename}"
    
    def cleanup_old_memes(self, days_old: int = 7):
        """
        Clean up old meme files to save disk space.
        
        Args:
            days_old: Delete memes older than this many days
        """
        try:
            import time
            current_time = time.time()
            cutoff_time = current_time - (days_old * 24 * 60 * 60)
            
            deleted_count = 0
            for filename in os.listdir(self.generated_memes_path):
                file_path = os.path.join(self.generated_memes_path, filename)
                if os.path.isfile(file_path):
                    file_time = os.path.getmtime(file_path)
                    if file_time < cutoff_time:
                        os.remove(file_path)
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old meme files")
                
        except Exception as e:
            logger.error(f"Error during meme cleanup: {e}")