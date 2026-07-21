import parselmouth
import numpy as np

def test_formants():
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    snd = parselmouth.Sound(audio_path)
    
    # Extract formants
    formant = snd.to_formant_burg(time_step=0.01, max_number_of_formants=5, maximum_formant=5500.0)
    
    def get_f3(start_s, end_s):
        f3_values = []
        t = start_s
        while t < end_s:
            try:
                val = formant.get_value_at_time(3, t)
                if not np.isnan(val): f3_values.append(val)
            except: pass
            t += 0.01
        if len(f3_values) == 0: return 0
        return np.median(f3_values)

    print("Female 1:", get_f3(0.0, 0.9))
    print("Deep Male 1:", get_f3(0.9, 1.4))
    print("Female 2:", get_f3(1.4, 2.1))
    print("Deep Male 2:", get_f3(2.1, 2.6))

test_formants()
