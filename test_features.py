import librosa
import numpy as np

def extract_features():
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    
    segments = [
        {"start": 0.0, "end": 0.9, "label": "Female 1"},
        {"start": 0.9, "end": 1.4, "label": "Deep Male 1"},
        {"start": 1.4, "end": 2.1, "label": "Female 2"},
        {"start": 2.1, "end": 2.6, "label": "Deep Male 2"},
    ]
    
    for s in segments:
        y, sr = librosa.load(audio_path, sr=None, offset=s['start'], duration=(s['end'] - s['start']))
        if len(y) == 0: continue
        
        # Fundamental Frequency
        f0, voiced_flag, _ = librosa.pyin(y, fmin=50, fmax=300, sr=sr)
        valid_f0 = f0[voiced_flag]
        pitch = np.percentile(valid_f0, 25) if len(valid_f0) > 0 else 0
        
        # Spectral Centroid
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)
        centroid = np.median(cent)
        
        # Zero Crossing Rate
        zcr = librosa.feature.zero_crossing_rate(y)
        zcr_mean = np.mean(zcr)
        
        # Spectral Rolloff
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)
        roll = np.median(rolloff)
        
        # MFCC
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean = np.mean(mfcc, axis=1)
        
        print(f"--- {s['label']} ---")
        print(f"Pitch: {pitch:.1f} Hz")
        print(f"Centroid: {centroid:.1f} Hz")
        print(f"ZCR: {zcr_mean:.4f}")
        print(f"Rolloff: {roll:.1f} Hz")
        print(f"MFCC 1-3: {mfcc_mean[1]:.1f}, {mfcc_mean[2]:.1f}, {mfcc_mean[3]:.1f}")
        print()

extract_features()
