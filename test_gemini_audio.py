import os
import json
import google.generativeai as genai

# On Windows, we can just grab it if it's set, or read from .env manually
with open('.env', 'r') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY='):
            api_key = line.strip().split('=')[1]
            break

genai.configure(api_key=api_key)

def test_gemini_audio():
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    
    print("Uploading audio to Gemini...")
    audio_file = genai.upload_file(path=audio_path)
    
    segments = [
        {"start": 0.0, "end": 0.9, "text": "Am I going to heaven?"},
        {"start": 0.9, "end": 1.4, "text": "No."},
        {"start": 1.4, "end": 2.1, "text": "Then am I going to hell?"},
        {"start": 2.1, "end": 2.6, "text": "No!"},
    ]
    
    transcript = ""
    for i, seg in enumerate(segments):
        transcript += f"[{i}] {seg['start']}-{seg['end']}s: {seg['text']}\n"
        
    prompt = f"""
Listen to this audio file and look at the following transcript segments.
For each segment, identify if the speaker's voice sounds like a 'male' or 'female'.
The video contains a heavily pitch-shifted deep male voice (which is the male) and a normal female voice.

Transcript:
{transcript}

Return ONLY a valid JSON object mapping the segment index (as string) to 'male' or 'female'.
Example: {{"0": "female", "1": "male"}}
"""
    
    print("Prompting Gemini 1.5 Flash...")
    model = genai.GenerativeModel('models/gemini-1.5-flash')
    response = model.generate_content(
        [audio_file, prompt],
        generation_config={"response_mime_type": "application/json"}
    )
    
    print("Response:")
    print(response.text)

test_gemini_audio()
