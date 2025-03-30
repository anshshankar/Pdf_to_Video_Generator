# PDF-to-Video Converter

A powerful Python utility that automatically converts PDF documents into narrated video presentations with synchronized slides and audio.

## Overview

This tool takes a PDF document as input and performs the following transformations:
1. Extracts text content from the PDF
2. Uses GPT-4o to generate slide content and voice-over scripts
3. Creates a PowerPoint presentation with bullet points
4. Generates text-to-speech audio narration
5. Combines slide images and audio into a complete video presentation

Perfect for quickly converting documentation, articles, or educational materials into engaging video content without manual editing.

## Features

- **Automated Content Processing**: Extracts and chunks PDF text for optimal processing
- **AI-Powered Summarization**: Uses OpenAI's GPT-4o to create concise slide bullets and detailed voice-over scripts
- **Professional Presentation Generation**: Creates structured PowerPoint presentations
- **Natural Text-to-Speech**: Converts scripts to audio using gTTS (Google Text-to-Speech)
- **Complete Video Production**: Combines slides and audio into a synchronized video

## Requirements

### Python Libraries
- PyMuPDF (fitz): For PDF text extraction
- OpenAI: For AI-powered content generation
- gTTS: For text-to-speech conversion
- python-pptx: For PowerPoint generation
- moviepy: For video creation
- pdf2image: For converting slides to images
- pydantic: For data validation
- python-dotenv: For environment variable management

### External Dependencies
- LibreOffice: Required for converting PowerPoint to PDF
- Poppler: Required by pdf2image for PDF processing

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/pdf-to-video-converter.git
   cd pdf-to-video-converter
   ```

2. Install required Python packages:
   ```
   pip install PyMuPDF openai gTTS python-pptx moviepy pdf2image pydantic python-dotenv
   ```

3. Install external dependencies:
   - LibreOffice: https://www.libreoffice.org/download/
   - Poppler:
     - On Ubuntu: `sudo apt-get install poppler-utils`
     - On macOS: `brew install poppler`
     - On Windows: Download from http://blog.alivate.com.au/poppler-windows/

4. Create a `.env` file with your OpenAI configuration:
   ```
   ENDPOINT=https://api.openai.com/v1  # Or your custom endpoint
   TOKEN=your_openai_api_key
   ```

## Usage

1. Import the main function and provide a path to your PDF:

```python
from pdf_to_video import main

main("/path/to/your/document.pdf")
```

2. The script will generate:
   - `voice.mp3`: The narration audio file
   - `presentation.pptx`: The PowerPoint presentation
   - `final_video.mp4`: The complete presentation video

## Customization

- Adjust `max_chunk_chars` in `chunk_text()` to modify how the PDF content is split
- Modify the prompt in `generate_chunk_content()` to change how the AI creates slides and scripts
- Update the presentation styling in `generate_presentation()` for different visual designs

## How It Works

1. **Text Extraction**: The PDF is processed to extract all text content
2. **Content Chunking**: Text is divided into manageable chunks (default 2500 chars)
3. **AI Processing**: Each chunk is sent to GPT-4o to generate slide bullet points and voice-over script
4. **Audio Generation**: The complete script is converted to speech using gTTS
5. **Presentation Creation**: A PowerPoint presentation is created with the bullet points
6. **Slide Conversion**: Slides are converted to images via LibreOffice and pdf2image
7. **Video Assembly**: Slides and audio are combined into the final video using moviepy

## Acknowledgments

- This project uses OpenAI's GPT-4o for natural language processing
- Text-to-speech provided by Google's TTS service