from inaSpeechSegmenter import Segmenter

def test_ina():
    print("Loading inaSpeechSegmenter...")
    seg = Segmenter(vad_engine='smn', detect_gender=True)
    
    audio_path = r"c:\Users\david\.gemini\antigravity-ide\scratch\tiktok_trend_predictor\downloads\GmREV8x3dik_vocals.wav"
    print("Processing audio...")
    segmentation = seg(audio_path)
    print("Results:")
    for label, start, end in segmentation:
        print(f"[{start:.2f}s - {end:.2f}s]: {label}")

test_ina()
