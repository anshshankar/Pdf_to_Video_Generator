import fitz  # PyMuPDF
from openai import OpenAI
from gtts import gTTS
from pptx import Presentation
from pptx.util import Inches, Pt
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
from pdf2image import convert_from_path
from pydantic import BaseModel, ValidationError
import subprocess
import tempfile
import os
import json
import textwrap
from pydantic import BaseModel, Field
from typing import List, Optional,Dict
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url=os.getenv("ENDPOINT"),
    api_key=os.getenv("TOKEN"),
)

# Data models
class SlideItem(BaseModel):
    title: str
    content: str
    key_points: List[str] = Field(default_factory=list)
    image_prompt: Optional[str] = None

class ShortVideoSegment(BaseModel):
    title: str
    content: str
    script: str
    duration: float = 60.0  # Target duration in seconds

class SlideChunk(BaseModel):
    slides: List[SlideItem]
    voice_over_script: str
    short_segments: List[ShortVideoSegment] = Field(default_factory=list)
    theme_colors: Optional[Dict[str, str]] = None

class VideoConfig(BaseModel):
    theme: str = "professional"  # professional, creative, minimal
    presenter_type: str = "human"  # human, cartoon, none
    language: str = "en"
    voice_style: str = "neutral"  # neutral, enthusiastic, formal
    include_background_music: bool = True
    resolution: str = "1080p"
    aspect_ratio: str = "16:9"
    animation_level: str = "moderate"  # none, subtle, moderate, dynamic

# Step 1: Extract PDF Content
def extract_text_from_pdf(pdf_path):
    print("Extracting text from PDF...")
    doc = fitz.open(pdf_path)

    # Extract text and any images
    text = ""
    images = []

    for page_num, page in enumerate(doc):
        text += page.get_text()

        # Extract images if needed
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            # Could save or process images here if needed

    print("✅ Text extracted.")
    return text

# Step 2: Chunk & Summarize
def chunk_text(text, chunk_size=100000):
    print("Chunking text...")
    chunks = textwrap.wrap(text, chunk_size, break_long_words=False)
    print(f"✅ Created {len(chunks)} chunks.")
    return chunks

def generate_chunk_content(chunks, config):
    print("Summarizing chunks with OpenAI...")
    combined_content = "\n\n".join(chunks)

    theme_desc = {
        "professional": "formal, corporate style with clean design",
        "creative": "vibrant, engaging style with dynamic elements",
        "minimal": "clean, simple style with focus on key content"
    }.get(config.theme, "professional style")

    voice_desc = {
        "neutral": "balanced and clear",
        "enthusiastic": "energetic and engaging",
        "formal": "serious and professional"
    }.get(config.voice_style, "clear and professional")

    prompt = (
        f"Generate a structured presentation based on the following content. "
        f"Use a {theme_desc} visual approach and a {voice_desc} tone for narration.\n\n"
        "Create a JSON with these keys:\n"
        "1. 'slides': list of objects with 'title', 'content', 'key_points' (list of bullet points), "
        "and 'image_prompt' (a description for generating a relevant image)\n"
        "2. 'voice_over_script': professional narration script covering all slides\n"
        "3. 'short_segments': 3-5 stand-alone segments for short-form videos (under 2 minutes each) "
        "with 'title', 'content', 'script', and 'duration' fields\n"
        "4. 'theme_colors': suggested color scheme (primary, secondary, accent, background, text)\n\n"
        f"Content:\n{combined_content}\n\n"
        "Respond with valid JSON only. Keep all content factual and based on the input material. "
        "Ensure 'voice_over_script' is a single string, not a list."
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=16000
    ).choices[0].message.content.strip()

    # Clean up response to get valid JSON
    if response.startswith("```json"):
        response = response.lstrip("```json").rstrip("```").strip()
    elif response.startswith("```"):
        response = response.lstrip("```").rstrip("```").strip()

    try:
        parsed_response = json.loads(response)

        # Fix: If voice_over_script is a list, join it into a single string
        if isinstance(parsed_response.get('voice_over_script'), list):
            parsed_response['voice_over_script'] = "\n\n".join(parsed_response['voice_over_script'])

        validated_chunk = SlideChunk(**parsed_response)
        print(validated_chunk)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"Parsing error: {e}\nResponse was: {response}")
        raise

    print("✅ Summarization complete.")
    return validated_chunk

# Step 3: Generate Audio from Script
def generate_audio(script, output_file):
    tts = gTTS(script)
    tts.save(output_file)

def generate_presentation(slide_contents, pptx_path, config=None):
    """
    Generate a PowerPoint presentation from slide contents, which can be:
    1. A list of SlideItem objects
    2. A SlideChunk object
    3. The raw parsed content from the paste.txt
    
    Parameters:
    - slide_contents: Slide content in one of the above formats
    - pptx_path: Path where the presentation will be saved
    - config: Optional configuration parameters
    
    Returns:
    - Path to the saved presentation
    """
    from pptx import Presentation
    from pptx.util import Pt, Inches
    from pptx.dml.color import RGBColor
    
    print("Creating enhanced slides...")
    prs = Presentation()
    
    # Handle different possible input formats
    if hasattr(slide_contents, 'slides'):
        # This is a SlideChunk object
        slides = slide_contents.slides
        voice_over_script = slide_contents.voice_over_script
        short_segments = slide_contents.short_segments
        theme_colors = slide_contents.theme_colors if slide_contents.theme_colors else {}
    elif isinstance(slide_contents, list) and all(hasattr(item, 'title') for item in slide_contents):
        # This is a list of SlideItem objects
        slides = slide_contents
        voice_over_script = ""
        short_segments = []
        theme_colors = {}
    elif isinstance(slide_contents, list) and len(slide_contents) > 0 and 'slides' in dir(slide_contents[0]):
        # This might be a list containing one SlideChunk object
        slides = slide_contents[0].slides
        voice_over_script = slide_contents[0].voice_over_script
        short_segments = slide_contents[0].short_segments
        theme_colors = slide_contents[0].theme_colors if slide_contents[0].theme_colors else {}
    else:
        # Assume raw data format like in paste.txt
        # Try to extract slides and other info
        slides = slide_contents
        voice_over_script = ""
        short_segments = []
        theme_colors = {}
        
        # Check if it's the raw parsed structure
        if hasattr(slide_contents, 'voice_over_script'):
            voice_over_script = slide_contents.voice_over_script
        if hasattr(slide_contents, 'short_segments'):
            short_segments = slide_contents.short_segments
        if hasattr(slide_contents, 'theme_colors'):
            theme_colors = slide_contents.theme_colors
    
    # Ensure we have default theme colors if not provided
    if not theme_colors:
        theme_colors = {
            "primary": "#1F497D",
            "secondary": "#4F81BD", 
            "accent": "#C0504D",
            "background": "#FFFFFF",
            "text": "#000000"
        }
    
    # Strip '#' prefix from colors if present
    for key in theme_colors:
        if isinstance(theme_colors[key], str) and theme_colors[key].startswith('#'):
            theme_colors[key] = theme_colors[key][1:]
    
    # Add a title slide
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title = title_slide.shapes.title
    subtitle = title_slide.placeholders[1]
    
    # Determine presentation title from first slide
    presentation_title = "Presentation"
    if slides and hasattr(slides[0], 'title'):
        first_title = slides[0].title
        if "Introduction" in first_title and "to" in first_title:
            presentation_title = first_title.split("to")[1].strip()
        else:
            presentation_title = first_title
    
    title.text = presentation_title
    subtitle.text = "A Comprehensive Guide"
    
    # Style the title slide
    title.text_frame.paragraphs[0].font.size = Pt(44)
    title.text_frame.paragraphs[0].font.color.rgb = RGBColor.from_string(theme_colors["primary"])
    subtitle.text_frame.paragraphs[0].font.size = Pt(28)
    subtitle.text_frame.paragraphs[0].font.color.rgb = RGBColor.from_string(theme_colors["secondary"])
    
    # Process each slide
    for i, slide_item in enumerate(slides):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        title_shape = slide.shapes.title
        content_placeholder = slide.placeholders[1]
        
        # Get slide title
        slide_title = f"Slide {i+1}"
        if hasattr(slide_item, 'title'):
            slide_title = slide_item.title
        
        # Set the title
        title_shape.text = slide_title
        title_shape.text_frame.paragraphs[0].font.size = Pt(36)
        title_shape.text_frame.paragraphs[0].font.color.rgb = RGBColor.from_string(theme_colors["primary"])
        
        # Set the content
        content_frame = content_placeholder.text_frame
        content_frame.clear()
        
        # Add main content
        slide_content = "Content"
        if hasattr(slide_item, 'content'):
            slide_content = slide_item.content
            
        p = content_frame.add_paragraph()
        p.text = slide_content
        p.font.size = Pt(24)
        p.font.color.rgb = RGBColor.from_string(theme_colors["text"])
        
        # Add key points as bullets
        key_points = []
        if hasattr(slide_item, 'key_points'):
            key_points = slide_item.key_points
            
        if key_points:
            content_frame.add_paragraph().text = ""  # Add spacing
            for point in key_points:
                bullet_p = content_frame.add_paragraph()
                bullet_p.text = point
                bullet_p.font.size = Pt(20)
                bullet_p.level = 1
                bullet_p.font.color.rgb = RGBColor.from_string(theme_colors["secondary"])
    
   
    
    # Add a final slide
    final_slide = prs.slides.add_slide(prs.slide_layouts[2])
    final_title = final_slide.shapes.title
    final_content = final_slide.placeholders[1]
    
    final_title.text = "Thank You!"
    final_title.text_frame.paragraphs[0].font.size = Pt(40)
    final_title.text_frame.paragraphs[0].font.color.rgb = RGBColor.from_string(theme_colors["primary"])
    
    final_p = final_content.text_frame.add_paragraph()
    final_p.text = "Any questions?"
    final_p.font.size = Pt(32)
    final_p.font.color.rgb = RGBColor.from_string(theme_colors["accent"])
    
    # Save the presentation
    prs.save(pptx_path)
    print(f"✅ Enhanced slides created and saved to {pptx_path}")
    return pptx_path

# Step 5: Convert Slides to Images
def slides_to_images(ppt_path, output_folder):
    subprocess.run([
        '/Applications/LibreOffice.app/Contents/MacOS/soffice', '--headless', '--convert-to', 'pdf', ppt_path, '--outdir', output_folder
    ], check=True)
    pdf_path = os.path.join(output_folder, os.path.splitext(os.path.basename(ppt_path))[0] + ".pdf")
    return [img.save(os.path.join(output_folder, f"slide_{i}.png"), 'PNG') or os.path.join(output_folder, f"slide_{i}.png")
            for i, img in enumerate(convert_from_path(pdf_path, dpi=200))]

# Step 6: Generate Video

def create_video(slide_imgs, audio_path, output_path):
    audio = AudioFileClip(audio_path)
    duration = audio.duration / len(slide_imgs)
    clips = [ImageClip(p).set_duration(duration) for p in slide_imgs]
    video = concatenate_videoclips(clips, method="compose").set_audio(audio)
    video.write_videofile(output_path, fps=24)

# Main

class Args:
    pdf = '/content/LLM_Overview.pdf'  # <-- Update with your actual PDF path
    avatar = '/content/man.png'  # <-- Update with your avatar image
    music = '/contents/breath-of-life_10-minutes-320859.mp3'  # Optional
    theme = 'creative'
    language = 'en'
    voice = 'enthusiastic'
    output = '/content/output/'

def main(pdf_path):

    args = Args()
    # Create configuration
    config = VideoConfig(
        theme=args.theme,
        language=args.language,
        voice_style=args.voice,
        include_background_music=bool(args.music)
    )
    text = extract_text_from_pdf(pdf_path)
    print("✅ Extracted text")

    chunks = chunk_text(text)
    print(f"✅ Split into {len(chunks)} chunks")

    results = [generate_chunk_content(chunk,config) for chunk in chunks]
    print("✅ Generated slide + script chunks")

    full_script = "\n\n".join(r.voice_over_script for r in results)
    audio_file = "voice.mp3"
    generate_audio(full_script, audio_file)
    print("✅ Audio saved")

    ppt_file = "presentation.pptx"
    generate_presentation(results, ppt_file, config)
    print("✅ Slides created")

    with tempfile.TemporaryDirectory() as tmpdir:
        imgs = slides_to_images(ppt_file, tmpdir)
        create_video(imgs, audio_file, "final_video.mp4")
        print("✅ Video exported")

if __name__ == "__main__":
    main("./contents/Promises_in_JavaScript_Notes.pdf")
