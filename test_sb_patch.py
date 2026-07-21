import os
import shutil
import pathlib

# Monkey patch symlink_to to bypass Windows Admin restrictions
original_symlink_to = pathlib.Path.symlink_to

def patched_symlink_to(self, target, target_is_directory=False):
    try:
        original_symlink_to(self, target, target_is_directory)
    except OSError:
        # If symlink fails (e.g. WinError 1314), fallback to copy
        if target.is_dir():
            shutil.copytree(target, self)
        else:
            shutil.copy2(target, self)

pathlib.Path.symlink_to = patched_symlink_to

import torch
import torchaudio
from speechbrain.inference.speaker import EncoderClassifier

def test():
    print("Loading SpeechBrain...")
    classifier = EncoderClassifier.from_hparams(source="speechbrain/spkrec-xvect-voxceleb", savedir="tmpdir_sb2")
    
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
    
    X = np.array(vectors)
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10).fit(X)
    labels = kmeans.labels_
    
    for i, s in enumerate(segments):
        print(f"{s['label']}: Cluster {labels[i]}")

test()
