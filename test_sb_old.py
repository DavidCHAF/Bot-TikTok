import os
import shutil
import pathlib
import sys

original_symlink_to = pathlib.Path.symlink_to

def patched_symlink_to(self, target, target_is_directory=False):
    try:
        original_symlink_to(self, target, target_is_directory)
    except OSError:
        if target.is_dir():
            shutil.copytree(target, self)
        else:
            shutil.copy2(target, self)

pathlib.Path.symlink_to = patched_symlink_to

import torch
import torchaudio
from speechbrain.pretrained import EncoderClassifier

def test():
    print("Loading SpeechBrain...")
    classifier = EncoderClassifier.from_hparams(source="speechbrain/spkrec-xvect-voxceleb", savedir="tmpdir_sb3")
    
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    
    def get_embedding(start_s, end_s):
        y, sr = torchaudio.load(audio_path)
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
            y = resampler(y)
        start_frame = int(start_s * 16000)
        end_frame = int(end_s * 16000)
        y_seg = y[:, start_frame:end_frame]
        embeddings = classifier.encode_batch(y_seg)
        return embeddings.squeeze().detach().numpy()

    segments = [
        {"start": 0.0, "end": 0.9, "label": "Female 1"},
        {"start": 0.9, "end": 1.4, "label": "Deep Male 1"},
        {"start": 1.4, "end": 2.1, "label": "Female 2"},
        {"start": 2.1, "end": 2.6, "label": "Deep Male 2"},
    ]
    
    vectors = []
    for s in segments:
        vec = get_embedding(s["start"], s["end"])
        vectors.append(vec)
        
    from sklearn.cluster import KMeans
    import numpy as np
    from scipy.spatial.distance import cosine
    
    print("Sim(F1, F2):", 1 - cosine(vectors[0], vectors[2]))
    print("Sim(M1, M2):", 1 - cosine(vectors[1], vectors[3]))
    print("Sim(F1, M1):", 1 - cosine(vectors[0], vectors[1]))

test()
