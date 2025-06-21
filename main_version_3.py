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
import pandas as pd

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

class SlideChunk(BaseModel):
    slides: List[SlideItem]
    theme_colors: Optional[Dict[str, str]] = None
    description: str

class VideoConfig(BaseModel):
    theme: str = "professional"
    presenter_type: str = "human"
    language: str = "en"
    voice_style: str = "neutral"
    include_background_music: bool = True
    resolution: str = "1080p"
    aspect_ratio: str = "16:9"
    animation_level: str = "moderate"


def generate_chunk_content(topic, config):
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
        f"Generate a structured presentation based on the following topic. "
        f"Use a {theme_desc} visual approach and a {voice_desc} tone for narration.\n\n"
        "You are to collect and explain all the core concepts, key facts, examples, and supporting points "
        "related to the topic in simple, accessible language. Organize the content logically to enable a smooth, informative presentation.\n\n"
        "Create a JSON with these keys:\n"
        "1. 'slides': list of objects with 'title', 'content', 'key_points' (list of bullet points), "
        "and 'voice_over' (narration script for this specific slide)\n"
        "2. 'theme_colors': suggested color scheme (primary, secondary, accent, background, text)\n\n"
        "3. description: A short description of the topic, including relevant hashtags for SEO, in string format."
        f"Topic:\n{topic}\n\n"
        "Respond with valid JSON only. Keep all content factual and written in easy-to-understand language, suitable for general audiences."
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


EXCEL_FILE = "topics.xlsx"

def main():
    args = Args()
    os.makedirs("Output", exist_ok=True)

    while True:
        # Load Excel file
        if not os.path.exists(EXCEL_FILE):
            print("❌ Excel file not found.")
            break

        df = pd.read_excel(EXCEL_FILE)

        if df.empty:
            print("✅ All topics processed.")
            break

        row = df.iloc[0]
        topic = row['topic_name']
        subject = row['subject']
        print(f"🎯 Processing topic: {topic} (Subject: {subject})")

        # Prepare config
        config = VideoConfig(
            theme=args.theme,
            language=args.language,
            voice_style=args.voice,
            include_background_music=bool(args.music)
        )
        os.makedirs(f"Output/{topic}", exist_ok=True)
        # Generate results
        results = [generate_chunk_content(topic, config)]

        with open(f"Output/{topic}/description.txt", "w", encoding="utf-8") as file:
            description = str(results[0].description)
            file.write(description)
            
        serializable_results = [chunk.model_dump() for chunk in results]

        with open(f"Output/{topic}/chunk_results.json", "w", encoding="utf-8") as f:
            json.dump(serializable_results, f, ensure_ascii=False, indent=4)

        all_slides = [slide for result in results for slide in result.slides]

        # Generate presentation
        
        
        ppt_file = f"Output/{topic}/presentation.pptx"
        generate_presentation(results, ppt_file, config)

        # Create voice overs
        intro_voice_over = f"Hey folks! Welcome back to the channel. Today, we’re diving into something super cool — {topic}. Let’s get into it!"
        end_voice_over = "Thanks for learning with us! If you’re loving our content, hit that like button, share it with your friends, and smash that subscribe button. Drop your thoughts or ideas in the comments — we love hearing from you!"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            slide_imgs = slides_to_images(ppt_file, tmpdir)

            clips = []

            # Intro
            slide_img = slide_imgs[0]
            audio_path = f"Output/{topic}/intro_audio.mp3"
            generate_audio(intro_voice_over, audio_path)
            audio = AudioFileClip(audio_path)
            clips.append(ImageClip(slide_img).set_duration(audio.duration).set_audio(audio))

            # Slides
            for i, slide in enumerate(all_slides):
                slide_img = slide_imgs[i + 1]
                audio_path = f"Output/{topic}/{i}_audio.mp3"
                generate_audio(slide.voice_over, audio_path)
                audio = AudioFileClip(audio_path)
                clips.append(ImageClip(slide_img).set_duration(audio.duration).set_audio(audio))

            # Outro
            slide_img = slide_imgs[-1]
            audio_path = f"Output/{topic}/ending_audio.mp3"
            generate_audio(end_voice_over, audio_path)
            audio = AudioFileClip(audio_path)
            clips.append(ImageClip(slide_img).set_duration(audio.duration).set_audio(audio))

            # Final video
            final_video = concatenate_videoclips(clips, method="compose")
            final_video.write_videofile(
                f"Output/{topic}/{topic}_final_video.mp4",
                fps=24,
                codec="libx264",
                audio_codec="aac",
                audio_bitrate="192k"
            )
            print(f"✅ Video for topic '{topic}' exported.")

        # Remove the processed topic
        df = df.drop(index=0)
        df.to_excel(EXCEL_FILE, index=False)
        print(f"🗑️ Topic '{topic}' removed from Excel.\n")

class Args:
    avatar = '/content/man.png'
    music = '/contents/breath-of-life_10-minutes-320859.mp3'
    theme = 'creative'
    language = 'en'
    voice = 'enthusiastic'
    output = '/content/output/'

if __name__ == "__main__":
    main()