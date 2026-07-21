import asyncio
import os
import sys
from src.video_processor import download_video, detect_text_zones

async def main():
    vid_id = "ogC55qKAISc"
    url = f"https://www.youtube.com/watch?v={vid_id}"
    
    # Download
    print(f"Downloading {url}...")
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    video_path = download_video(url, output_dir)
    
    if not video_path or not os.path.exists(video_path):
        print("Failed to download video.")
        return
        
    print(f"Video downloaded to {video_path}")
    print("Running detect_text_zones...")
    
    static_texts, dynamic_zones, dynamic_texts_count, width, height = detect_text_zones(video_path)
    
    print("\n=== RESULTS ===")
    print(f"Static Texts: {len(static_texts)}")
    print(f"Dynamic Zones: {len(dynamic_zones)}")
    print(f"Dynamic Texts Count: {dynamic_texts_count}")
    
    if dynamic_zones:
        for dz in dynamic_zones:
            print(f"Found dynamic zone: {dz}")
    else:
        print("NO DYNAMIC ZONES FOUND!")
        
if __name__ == "__main__":
    asyncio.run(main())
