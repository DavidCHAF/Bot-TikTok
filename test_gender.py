import librosa
import numpy as np

def test_gender(audio_path, start_s, end_s):
    y, sr = librosa.load(audio_path, sr=None, offset=start_s, duration=(end_s - start_s))
    if len(y) == 0:
        return
    
    f0, voiced_flag, _ = librosa.pyin(y, fmin=50, fmax=300, sr=sr)
    valid_f0 = f0[voiced_flag]
    base_f0 = np.percentile(valid_f0, 25) if len(valid_f0) > 0 else 0
    median_f0 = np.median(valid_f0) if len(valid_f0) > 0 else 0
    
    print(f"Segment {start_s}-{end_s}s: 25th={base_f0:.1f}Hz, Median={median_f0:.1f}Hz")

audio = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
test_gender(audio, 0.0, 0.9)  # Female
test_gender(audio, 0.9, 1.4)  # Deep Male
test_gender(audio, 1.4, 2.1)  # Female
test_gender(audio, 2.1, 2.6)  # Deep Male
