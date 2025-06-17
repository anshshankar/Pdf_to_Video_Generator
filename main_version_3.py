import fitz  # PyMuPDF
from openai import OpenAI
from pptx import Presentation
from pptx.util import Inches, Pt
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip
from pydantic import BaseModel, ValidationError
import tempfile
import os
import json
import textwrap
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from dotenv import load_dotenv
from yt_shorts import process_shorts_from_results
from presentation import generate_presentation, slides_to_images
from audio import generate_audio
import time
import requests
import json

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
    voice_over: str

class ShortVideoSegment(BaseModel):
    title: str
    content: str
    script: str
    duration: float = 60.0  # Target duration in seconds

class SlideChunk(BaseModel):
    slides: List[SlideItem]
    short_segments: List[ShortVideoSegment] = Field(default_factory=list)
    theme_colors: Optional[Dict[str, str]] = None

class VideoConfig(BaseModel):
    theme: str = "professional"
    presenter_type: str = "human"
    language: str = "en"
    voice_style: str = "neutral"
    include_background_music: bool = True
    resolution: str = "1080p"
    aspect_ratio: str = "16:9"
    animation_level: str = "moderate"

# Step 1: Extract PDF Content
def extract_text_from_pdf(pdf_path):
    print("Extracting text from PDF...")
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    print("✅ Text extracted.")
    return text

def chunk_text(text, chunk_size=100000):
    print("Chunking text...")
    chunks = textwrap.wrap(text, chunk_size, break_long_words=False)
    print(f"✅ Created {len(chunks)} chunks.")
    return chunks

def generate_chunk_content(chunk, config):
    print("Generating structured content with OpenAI...")
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
        "and 'voice_over' (narration script for this specific slide)\n"
        "2. 'short_segments': 3-5 stand-alone segments for short-form videos (under 2 minutes each) "
        "with 'title', 'content', 'script', and 'duration' (in seconds) fields\n"
        "3. 'theme_colors': suggested color scheme (primary, secondary, accent, background, text)\n\n"
        f"Content:\n{chunk}\n\n"
        "Respond with valid JSON only. Keep all content factual and based on the input material."
    )

    response = client.chat.completions.create(
        model="openai/gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=16000
    ).choices[0].message.content.strip()

    if response.startswith("```json"):
        response = response.lstrip("```json").rstrip("```").strip()
    elif response.startswith("```"):
        response = response.lstrip("```").rstrip("```").strip()

    try:
        parsed_response = json.loads(response)
        validated_chunk = SlideChunk(**parsed_response)
        print(validated_chunk)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"Parsing error: {e}\nResponse was: {response}")
        raise

    print("✅ Structured content generated.")
    return validated_chunk


def main():
    args = Args()
    os.makedirs("Output", exist_ok=True)
    config = VideoConfig(
        theme=args.theme,
        language=args.language,
        voice_style=args.voice,
        include_background_music=bool(args.music)
    )
    text = extract_text_from_pdf(args.pdf_path)
    chunks = chunk_text(text)
    results = [generate_chunk_content(chunk, config) for chunk in chunks]

    serializable_results = [chunk.model_dump() for chunk in results]

    with open("Output/chunk_results.json", "w", encoding="utf-8") as f:
        json.dump(serializable_results, f, ensure_ascii=False, indent=4)

    # Flatten all slides from all chunks
    all_slides = [slide for result in results for slide in result.slides]

    # Generate presentation and slide images
    ppt_file = "Output/presentation.pptx"
    topic = generate_presentation(results, ppt_file, config)

    intro_voice_over = f"Hey folks! Welcome back to the channel. Today, we’re diving into something super cool — {topic}. Let’s get into it!"
    end_voice_over = "Thanks for hanging out with us! If you’re vibing with the content, hit that like button, share it with your crew, and smash that subscribe. Drop your thoughts or ideas in the comments — we love hearing from you!"

    with tempfile.TemporaryDirectory() as tmpdir:
        slide_imgs = slides_to_images(ppt_file, tmpdir)

        clips = []

        slide_img = slide_imgs[0]
        audio_path = f"Output/intro_audio.mp3"
        generate_audio(intro_voice_over,audio_path)
        audio = AudioFileClip(audio_path)
        image_clip = ImageClip(slide_img).set_duration(audio.duration)
        final_clip = CompositeVideoClip([image_clip]).set_audio(audio)
        clips.append(final_clip)

        for i, slide in enumerate(all_slides):
            slide_img = slide_imgs[i+1]
            audio_path = f"Output/{i}_audio.mp3"
            generate_audio(slide.voice_over,audio_path)
            audio = AudioFileClip(audio_path)
            image_clip = ImageClip(slide_img).set_duration(audio.duration)
           
            final_clip = CompositeVideoClip([image_clip]).set_audio(audio)
            clips.append(final_clip)

        slide_img = slide_imgs[-1]
        audio_path = f"Output/ending_audio.mp3"
        generate_audio(end_voice_over,audio_path)
        audio = AudioFileClip(audio_path)
        image_clip = ImageClip(slide_img).set_duration(audio.duration)
        final_clip = CompositeVideoClip([image_clip]).set_audio(audio)
        clips.append(final_clip)

        # Concatenate all clips
        final_video = concatenate_videoclips(clips, method="compose")
        #final_video.write_videofile("final_video.mp4", fps=24)
        final_video.write_videofile(
                 "Output/final_video2.mp4",
                 fps=24,
                 codec="libx264",         # Good video codec
                 audio_codec="aac",       # Ensure AAC audio
                 audio_bitrate="192k"     # Reasonable audio quality
        )
        print("✅ Main Video exported")

        # # Generate YouTube Shorts
        # shorts_config = VideoConfig(
        #     theme=config.theme,
        #     language=config.language,
        #     voice_style=config.voice_style,
        #     aspect_ratio="9:16"
        # )
        # process_shorts_from_results(results, shorts_config)
        # print("✅ YouTube Shorts generated")

class Args:
    pdf_path = 'contents/Basics_of_Machine_Learning_Notes.pdf'
    avatar = '/content/man.png'
    music = '/contents/breath-of-life_10-minutes-320859.mp3'
    theme = 'creative'
    language = 'en'
    voice = 'enthusiastic'
    output = '/content/output/'
    api_path = ''

if __name__ == "__main__":
    main()