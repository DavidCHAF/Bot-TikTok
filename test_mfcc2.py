import librosa
import numpy as np
import parselmouth
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

def test_mfcc2():
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    
    snd = parselmouth.Sound(audio_path)
    pitch = snd.to_pitch(pitch_floor=50.0, pitch_ceiling=300.0)
    pitch_values = pitch.selected_array['frequency']
    
    def get_features(start_s, end_s):
        y, sr = librosa.load(audio_path, sr=None, offset=start_s, duration=(end_s - start_s))
        if len(y) == 0: return np.zeros(20)
        
        # We need to know which frames are voiced
        # Let's just use librosa's spectral centroid and MFCC, but take median
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        # Drop the first MFCC (energy) which depends on volume
        mfcc = mfcc[1:, :]
        
        # Take the median across time frames to ignore silence/outliers
        mfcc_median = np.median(mfcc, axis=1)
        
        # Let's also get the median pitch from praat
        start_frame = int(start_s / pitch.dx)
        end_frame = int(end_s / pitch.dx)
        seg_pitch = pitch_values[start_frame:end_frame]
        valid_pitch = seg_pitch[seg_pitch > 0]
        p = np.median(valid_pitch) if len(valid_pitch) > 0 else 0
        
        # Combine MFCC and Pitch!
        features = np.append(mfcc_median, p)
        return features

    segments = [
        {"start": 0.0, "end": 0.9, "label": "Female 1"},
        {"start": 0.9, "end": 1.4, "label": "Deep Male 1"},
        {"start": 1.4, "end": 2.1, "label": "Female 2"},
        {"start": 2.1, "end": 2.6, "label": "Deep Male 2"},
    ]
    
    features = []
    for s in segments:
        features.append(get_features(s["start"], s["end"]))
    
    X = np.array(features)
    # Standardize features so MFCC and Pitch have equal weight
    X = StandardScaler().fit_transform(X)
    
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10).fit(X)
    labels = kmeans.labels_
    
    for i, s in enumerate(segments):
        print(f"{s['label']}: Cluster {labels[i]} (Pitch: {features[i][-1]:.1f}Hz)")

test_mfcc2()
