import requests
import json
import time

def extract_segment(audio_path, start_s, end_s, output_path):
    from pydub import AudioSegment
    audio = AudioSegment.from_wav(audio_path)
    audio = audio[int(start_s*1000):int(end_s*1000)]
    audio.export(output_path, format="wav")

def test_api():
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    out_path = "tmp_segment.wav"
    
    extract_segment(audio_path, 0.0, 0.9, out_path)
    
    API_URL = "https://api-inference.huggingface.co/models/alefiury/wav2vec2-large-xlsr-53-gender-recognition-osmr"
    
    with open(out_path, "rb") as f:
        data = f.read()
    
    print("Requesting HF API...")
    response = requests.post(API_URL, data=data)
    print("Status:", response.status_code)
    print("Response:", response.text)

test_api()
