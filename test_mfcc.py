import librosa
import numpy as np
from sklearn.cluster import KMeans

def test_mfcc():
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    
    def get_mfcc(start_s, end_s):
        y, sr = librosa.load(audio_path, sr=None, offset=start_s, duration=(end_s - start_s))
        if len(y) == 0: return np.zeros(20)
        # Extract 20 MFCCs (standard for speech)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        # Average over time
        return np.mean(mfcc, axis=1)

    segments = [
        {"start": 0.0, "end": 0.9, "label": "Female 1"},
        {"start": 0.9, "end": 1.4, "label": "Deep Male 1"},
        {"start": 1.4, "end": 2.1, "label": "Female 2"},
        {"start": 2.1, "end": 2.6, "label": "Deep Male 2"},
    ]
    
    features = []
    for s in segments:
        features.append(get_mfcc(s["start"], s["end"]))
    
    X = np.array(features)
    # Standardize
    X = (X - np.mean(X, axis=0)) / (np.std(X, axis=0) + 1e-6)
    
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10).fit(X)
    labels = kmeans.labels_
    
    for i, s in enumerate(segments):
        print(f"{s['label']}: Cluster {labels[i]}")

test_mfcc()
