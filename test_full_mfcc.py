import librosa
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy.spatial.distance import cosine

def test_full_mfcc():
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    
    # We will test on all segments from the VTT
    segments = [
        {"start": 0.0, "end": 0.9, "label": "Female (Am I going to heaven?)"},
        {"start": 0.9, "end": 1.4, "label": "Male (No.)"},
        {"start": 1.4, "end": 2.1, "label": "Female (Then am I going to hell?)"},
        {"start": 2.1, "end": 2.6, "label": "Male (No!)"},
        {"start": 2.6, "end": 3.8, "label": "Male (You die before your time!)"},
        {"start": 3.8, "end": 4.6, "label": "Female (So what do I do?)"},
        {"start": 4.6, "end": 6.6, "label": "Male (You have 24 hours to do four good deeds.)"},
        {"start": 6.6, "end": 7.6, "label": "Male (Or you'll go to hell.)"},
    ]
    
    features = []
    
    for seg in segments:
        start_s = seg['start']
        end_s = seg['end']
        
        y, sr = librosa.load(audio_path, sr=16000, offset=start_s, duration=(end_s - start_s))
        if len(y) == 0:
            continue
            
        # Extract 13 MFCCs
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        # We can also compute the delta MFCCs to capture temporal dynamics!
        mfcc_delta = librosa.feature.delta(mfcc)
        
        # Mean across time for both
        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_delta_mean = np.mean(mfcc_delta, axis=1)
        
        # Pitch (median F0)
        f0, voiced_flag, _ = librosa.pyin(y, fmin=50, fmax=400, sr=sr)
        valid_f0 = f0[voiced_flag]
        pitch = np.median(valid_f0) if len(valid_f0) > 0 else 0
        
        # Feature vector: 13 MFCCs + 13 Delta MFCCs + Pitch
        vec = np.concatenate([mfcc_mean, mfcc_delta_mean, [pitch]])
        features.append(vec)
        
    X = np.array(features)
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Cluster
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=20).fit(X_scaled)
    labels = kmeans.labels_
    
    centers_orig = scaler.inverse_transform(kmeans.cluster_centers_)
    print(f"Cluster 0 - Pitch: {centers_orig[0][-1]:.2f}Hz")
    print(f"Cluster 1 - Pitch: {centers_orig[1][-1]:.2f}Hz")
    
    female_idx = 0 if centers_orig[0][-1] > centers_orig[1][-1] else 1
    print(f"Female cluster identified by PITCH as: {female_idx}")
    
    for i, seg in enumerate(segments):
        print(f"Cluster {labels[i]} : {seg['label']}")

test_full_mfcc()
