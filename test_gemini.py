import os
from google import genai
from google.genai import types

def test_gemini_audio():
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    
    try:
        print("Uploading audio to Gemini...")
        audio_file = client.files.upload(file=audio_path)
        
        prompt = """
        Listen to this audio. I have 4 segments of speech:
        1. 0.0s to 0.9s: "Am I going to heaven?"
        2. 0.9s to 1.4s: "No."
        3. 1.4s to 2.1s: "Then am I going to hell?"
        4. 2.1s to 2.6s: "No!"
        
        For each segment, tell me if the speaker is 'male' or 'female'.
        Output exactly this format:
        [
          {"segment": 1, "gender": "female"},
          {"segment": 2, "gender": "male"}
        ]
        """
        
        print("Generating content...")
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[audio_file, prompt]
        )
        print("Response:")
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

test_gemini_audio()
