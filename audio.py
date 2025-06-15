import asyncio
import edge_tts

def generate_audio(script, output_file, voice="en-GB-RyanNeural", rate="+30%"):
    """
    Generate realistic speech with control over voice characteristics using edge-tts Python API.

    Parameters:
    script: Your text script
    output_file: Output filename (default: output.mp3)
    voice: Voice selection (default: en-GB-RyanNeural - deep male voice)
    rate: Speaking rate adjustment (default: +30% faster)
    """
    async def _generate():
        communicate = edge_tts.Communicate(script, voice, rate=rate)
        await communicate.save(output_file)
    
    asyncio.run(_generate())
