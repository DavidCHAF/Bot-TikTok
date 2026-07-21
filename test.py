import asyncio
from src.video_processor import detect_text_zones

async def main():
    static_texts, dynamic_zones, dynamic_count, width, height = detect_text_zones("downloads/ckT2YpUrEiA.mp4")
    print(f"Video size: {width}x{height}")
    print(f"Dynamic Zones count: {len(dynamic_zones)}")
    for i, dz in enumerate(dynamic_zones):
        print(f"Zone {i}: {dz}")

if __name__ == "__main__":
    asyncio.run(main())
