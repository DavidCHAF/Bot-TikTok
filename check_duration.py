import asyncio
import os
import cv2
import easyocr

def test_durations():
    video_path = "downloads/GmREV8x3dik.mp4"
    if not os.path.exists(video_path):
        print("Video not found.")
        return
        
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    sample_indices = [int(fps * i) for i in range(int(duration))]
    
    print(f"Total samples: {len(sample_indices)}")
    
    reader = easyocr.Reader(['fr', 'en'], gpu=False)
    all_texts = []
    
    for idx in sample_indices:
        if idx >= total_frames: break
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret: continue
        results = reader.readtext(frame)
        for (bbox, text, prob) in results:
            if prob > 0.6 and len(text.strip()) >= 3:
                x = min([p[0] for p in bbox])
                y = min([p[1] for p in bbox])
                w = max([p[0] for p in bbox]) - x
                h = max([p[1] for p in bbox]) - y
                all_texts.append({'text': text.strip(), 'box': (x, y, w, h), 'frame': idx})
                
    dynamic_location_groups = []
    for t in all_texts:
        placed = False
        for group in dynamic_location_groups:
            first_center_y = group[0]['box'][1] + (group[0]['box'][3] / 2)
            t_center_y = t['box'][1] + (t['box'][3] / 2)
            if abs(t_center_y - first_center_y) < 100:
                group.append(t)
                placed = True
                break
        if not placed:
            dynamic_location_groups.append([t])
            
    for i, group in enumerate(dynamic_location_groups):
        pct = len(group) / len(sample_indices)
        print(f"Group {i} : {len(group)} samples ({pct*100:.1f}%) - text sample: {group[0]['text']}")

if __name__ == "__main__":
    test_durations()
