import fitz  # PyMuPDF
from openai import OpenAI
from pptx import Presentation
from pptx.util import Inches, Pt
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
from pydantic import BaseModel, ValidationError
import tempfile
import os
import json
import textwrap
from pydantic import BaseModel, Field
from typing import List, Optional,Dict
from dotenv import load_dotenv
from yt_shorts import process_shorts_from_results
from audio import generate_audio
from presentation import generate_presentation, slides_to_images

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

def create_video(slide_imgs, audio_path, output_path):
    audio = AudioFileClip(audio_path)
    duration = audio.duration / len(slide_imgs)
    clips = [ImageClip(p).set_duration(duration) for p in slide_imgs]
    video = concatenate_videoclips(clips, method="compose").set_audio(audio)
    video.write_videofile(output_path, fps=24)

def main():
    args = Args()
    # Create configuration
    config = VideoConfig(
        theme=args.theme,
        language=args.language,
        voice_style=args.voice,
        include_background_music=bool(args.music)
    )
    text = extract_text_from_pdf(args.pdf_path)
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
        print("✅ Main Video exported")

    yt_shorts = generate_yt_shorts(results)
    print(f"✅ Created {len(yt_shorts)} YouTube shorts videos")

class Args:
    pdf_path = 'contents/Basics_of_Machine_Learning_Notes.pdf'  # <-- Update with your actual PDF path
    avatar = '/content/man.png'  # <-- Update with your avatar image
    music = '/contents/breath-of-life_10-minutes-320859.mp3'  # Optional
    theme = 'creative'
    language = 'en'
    voice = 'enthusiastic'
    output = '/content/output/'

if __name__ == "__main__":
    main()
