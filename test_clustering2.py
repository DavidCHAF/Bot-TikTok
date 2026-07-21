import librosa
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

def get_features(y, sr):
    # F0 Pitch
    f0, voiced_flag, _ = librosa.pyin(y, fmin=50, fmax=300, sr=sr)
    valid_f0 = f0[voiced_flag]
    pitch = np.percentile(valid_f0, 25) if len(valid_f0) > 0 else 0
    
    # MFCC 3
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc3 = mfcc_mean[3]
    
    return [pitch, mfcc3]

def test():
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    segments = [
        {"start": 0.0, "end": 0.9, "label": "Female 1"},
        {"start": 0.9, "end": 1.4, "label": "Deep Male 1"},
        {"start": 1.4, "end": 2.1, "label": "Female 2"},
        {"start": 2.1, "end": 2.6, "label": "Deep Male 2"},
    ]
    
    X = []
    for s in segments:
        y, sr = librosa.load(audio_path, sr=None, offset=s['start'], duration=(s['end'] - s['start']))
        if len(y) > 0:
            X.append(get_features(y, sr))
    
    X = np.array(X)
    X_scaled = StandardScaler().fit_transform(X)
    
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10).fit(X_scaled)
    labels = kmeans.labels_
    
    for i, s in enumerate(segments):
        print(f"{s['label']}: Cluster {labels[i]} (Pitch: {X[i][0]:.1f}, MFCC3: {X[i][1]:.1f})")

test()
