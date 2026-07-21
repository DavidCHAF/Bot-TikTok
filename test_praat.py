import parselmouth
import numpy as np

def test_praat():
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    
    # Load entire file into praat
    snd = parselmouth.Sound(audio_path)
    
    # Extract pitch using praat (default 75Hz to 500Hz)
    # We set pitch floor to 50Hz to catch deep voices
    pitch = snd.to_pitch(pitch_floor=50.0, pitch_ceiling=300.0)
    
    pitch_values = pitch.selected_array['frequency']
    
    def get_gender(start_s, end_s):
        # Convert seconds to frames (parselmouth uses 0.01s steps by default)
        start_frame = int(start_s / pitch.dx)
        end_frame = int(end_s / pitch.dx)
        
        segment_pitch = pitch_values[start_frame:end_frame]
        valid_pitch = segment_pitch[segment_pitch > 0]
        
        if len(valid_pitch) == 0:
            return 0
            
        # We can take the 25th percentile or median
        return np.percentile(valid_pitch, 25), np.median(valid_pitch)

    print("0.0 - 0.9s (Female):", get_gender(0.0, 0.9))
    print("0.9 - 1.4s (Deep Male):", get_gender(0.9, 1.4))
    print("1.4 - 2.1s (Female):", get_gender(1.4, 2.1))
    print("2.1 - 2.6s (Deep Male):", get_gender(2.1, 2.6))

test_praat()
