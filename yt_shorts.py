import os
import subprocess
from typing import List, Dict, Optional
import tempfile
from PIL import Image, ImageDraw, ImageFont
import textwrap
import json
from pydub import AudioSegment
import time
import shutil
from moviepy.editor import ImageSequenceClip, AudioFileClip, CompositeVideoClip, TextClip, ImageClip, concatenate_videoclips
from pydantic import BaseModel, Field

# Function to create short video clips from the results data
def process_shorts_from_results(results):
    """
    Process the results data to create short video clips
    """
    # Extract short video segments from the results
    all_segments = []
    for chunk in results:
        all_segments.extend(chunk.short_segments)
    
    print(f"Found {len(all_segments)} short video segments to process")
    
    # Create a directory for our short videos if it doesn't exist
    os.makedirs("shorts", exist_ok=True)
    
    # Process each segment into a short video
    video_paths = []
    for i, segment in enumerate(all_segments):
        video_path = create_short_video(segment, i, results[0].theme_colors)
        video_paths.append(video_path)
        print(f"✅ Created short video {i+1}/{len(all_segments)}")
    
    return video_paths

def create_short_video(segment, index, theme_colors):
    """
    Create a single short video for a segment
    """
    # Create temporary directory for this short
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Generate audio for this segment
        audio_file = os.path.join(tmpdir, f"audio_{index}.mp3")
        generate_audio_segment(segment.script, audio_file)
        
        # 2. Create frames for the short video
        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # Generate frames for the short video
        frames = generate_short_video_frames(segment, frames_dir, theme_colors)
        
        # 3. Create the video with the frames and audio
        output_path = f"shorts/short_video_{index+1}.mp4"
        create_short_clip(frames, audio_file, output_path, segment.duration)
        
        return output_path



def generate_short_video_frames(segment, frames_dir, theme_colors):
    """
    Generate frames for a short video
    """
    # Number of frames to generate (assuming 30fps)
    frame_count = int(segment.duration * 30)  # 30 frames per second
    frame_paths = []
    
    # Generate background frames
    for i in range(frame_count):
        frame_path = os.path.join(frames_dir, f"frame_{i:04d}.png")
        
        # Create a frame with title and content
        create_frame(
            title=segment.title,
            content=segment.content,
            output_path=frame_path,
            theme_colors=theme_colors,
            frame_number=i,
            total_frames=frame_count
        )
        frame_paths.append(frame_path)
    
    return frame_paths

def create_frame(title, content, output_path, theme_colors, frame_number, total_frames):
    """
    Create a single frame for the short video
    """
    # Create a 9:16 aspect ratio image (1080x1920 for high quality)
    width, height = 1080, 1920
    image = Image.new('RGBA', (width, height), theme_colors['background'])
    draw = ImageDraw.Draw(image)
    
    # Calculate animation progress (0 to 1)
    progress = frame_number / total_frames
    
    # Define fonts
    try:
        title_font = ImageFont.truetype("Arial.ttf", 60)
        content_font = ImageFont.truetype("Arial.ttf", 40)
    except IOError:
        # Fallback to default font if Arial is not available
        title_font = ImageFont.load_default()
        content_font = ImageFont.load_default()
    
    # Add a colored header background
    header_height = 200
    draw.rectangle([(0, 0), (width, header_height)], fill=theme_colors['primary'])
    
    # Add title
    title_wrapped = textwrap.fill(title, width=25)
    draw.text((width//2, header_height//2), title_wrapped, 
              font=title_font, fill='white', anchor='mm', align='center')
    
    # Add content with animation
    content_wrapped = textwrap.fill(content, width=35)
    
    # Simple fade-in animation
    if progress < 0.2:
        # Fade in
        alpha = int(255 * (progress / 0.2))
        content_color = theme_colors['text'][:-2] + format(alpha, '02x')
    else:
        content_color = theme_colors['text']
    
    draw.text((width//2, header_height + 300), content_wrapped, 
              font=content_font, fill=content_color, anchor='mm', align='center')
    
    # Add a decorative element
    circle_radius = 100 + int(20 * (0.5 - abs(0.5 - progress)) * 2)  # Breathing effect
    circle_position = (width//2, height - 300)
    draw.ellipse(
        [(circle_position[0] - circle_radius, circle_position[1] - circle_radius),
         (circle_position[0] + circle_radius, circle_position[1] + circle_radius)],
        fill=theme_colors['accent']
    )
    
    # Save the frame
    image.save(output_path)
    return output_path

def create_short_clip(frames, audio_file, output_path, duration):
    """
    Create a video clip from frames and audio
    """
    # Create clip from image sequence
    clip = ImageSequenceClip(frames, fps=30)
    
    # Add audio
    audio = AudioFileClip(audio_file)
    video = clip.set_audio(audio)
    
    # Set the clip duration
    if video.duration > duration:
        video = video.subclip(0, duration)
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Export the final video
    video.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    return output_path

def main():

    
    # Process the shorts from the results
    video_paths = process_shorts_from_results(results_data)
    
    print(f"✅ Created {len(video_paths)} short videos.")
    print("Videos are available in the 'shorts' directory.")

if __name__ == "__main__":
    main()