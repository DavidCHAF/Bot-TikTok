import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

import librosa
import numpy as np
import torch
import torchaudio
from speechbrain.inference.speaker import EncoderClassifier

def extract_features():
    print("Loading SpeechBrain model...")
    # This downloads the model from HF (takes ~15MB for xvector)
    # savedir avoids symlink issues if HF_HUB_DISABLE_SYMLINKS is set
    classifier = EncoderClassifier.from_hparams(source="speechbrain/spkrec-xvect-voxceleb", savedir="tmpdir_sb")
    
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    
    def get_embedding(start_s, end_s):
        # Load exactly the segment
        y, sr = torchaudio.load(audio_path)
        # Convert to 16kHz for speechbrain
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
            y = resampler(y)
        
        start_frame = int(start_s * 16000)
        end_frame = int(end_s * 16000)
        y_seg = y[:, start_frame:end_frame]
        
        embeddings = classifier.encode_batch(y_seg)
        return embeddings.squeeze().detach().numpy()

    emb1 = get_embedding(0.0, 0.9) # Female
    emb2 = get_embedding(0.9, 1.4) # Deep Male
    emb3 = get_embedding(1.4, 2.1) # Female
    emb4 = get_embedding(2.1, 2.6) # Deep Male
    
    # Check cosine similarity
    from scipy.spatial.distance import cosine
    print("Sim(F1, F2):", 1 - cosine(emb1, emb3))
    print("Sim(M1, M2):", 1 - cosine(emb2, emb4))
    print("Sim(F1, M1):", 1 - cosine(emb1, emb2))
    print("Sim(F2, M2):", 1 - cosine(emb3, emb4))

extract_features()
