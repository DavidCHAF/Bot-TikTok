import os
import zipfile
import urllib.request
from vosk import Model, SpkModel, KaldiRecognizer
import wave
import json
import librosa
import soundfile as sf
import numpy as np

def test_vosk():
    model_dir = "vosk-model-small-en-us-0.15"
    spk_model_dir = "vosk-model-spk-0.4"
    
    # Download tiny speech model
    if not os.path.exists(model_dir):
        print("Downloading vosk language model...")
        urllib.request.urlretrieve("https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip", "model.zip")
        with zipfile.ZipFile("model.zip", 'r') as zip_ref:
            zip_ref.extractall(".")
        os.remove("model.zip")
        
    # Download speaker model
    if not os.path.exists(spk_model_dir):
        print("Downloading vosk speaker model...")
        urllib.request.urlretrieve("https://alphacephei.com/vosk/models/vosk-model-spk-0.4.zip", "spk_model.zip")
        with zipfile.ZipFile("spk_model.zip", 'r') as zip_ref:
            zip_ref.extractall(".")
        os.remove("spk_model.zip")

    print("Loading models...")
    model = Model(model_dir)
    spk_model = SpkModel(spk_model_dir)
    
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    
    segments = [
        {"start": 0.0, "end": 0.9, "label": "Female 1"},
        {"start": 0.9, "end": 1.4, "label": "Deep Male 1"},
        {"start": 1.4, "end": 2.1, "label": "Female 2"},
        {"start": 2.1, "end": 2.6, "label": "Deep Male 2"},
    ]
    
    def get_xvector(start_s, end_s):
        y, sr = librosa.load(audio_path, sr=16000, offset=start_s, duration=(end_s - start_s))
        if len(y) == 0: return None
        
        # Convert to 16-bit PCM for Vosk
        y_int16 = (y * 32767).astype(np.int16)
        
        rec = KaldiRecognizer(model, 16000)
        rec.SetSpkModel(spk_model)
        
        rec.AcceptWaveform(y_int16.tobytes())
        res = json.loads(rec.FinalResult())
        
        if 'spk' in res:
            return np.array(res['spk'])
        return None

    vectors = []
    labels = []
    for s in segments:
        vec = get_xvector(s["start"], s["end"])
        if vec is not None:
            vectors.append(vec)
            labels.append(s["label"])
            print(f"Extracted vector for {s['label']}")
        else:
            print(f"Failed to extract for {s['label']}")

    # Check cosine similarity
    from scipy.spatial.distance import cosine
    
    if len(vectors) == 4:
        print("Sim(F1, F2):", 1 - cosine(vectors[0], vectors[2]))
        print("Sim(M1, M2):", 1 - cosine(vectors[1], vectors[3]))
        print("Sim(F1, M1):", 1 - cosine(vectors[0], vectors[1]))
        print("Sim(F2, M2):", 1 - cosine(vectors[2], vectors[3]))

test_vosk()
