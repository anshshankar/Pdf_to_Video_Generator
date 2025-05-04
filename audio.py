from gtts import gTTS

def generate_audio(script, output_file):
    tts = gTTS(script)
    tts.save(output_file)
