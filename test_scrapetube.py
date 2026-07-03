import scrapetube
import itertools

def test_scrape():
    print("Fetching search results...")
    videos = scrapetube.get_search("business #shorts", sort_by="upload_date", results_type="video")
    count = 0
    for video in videos:
        count += 1
        print(video.get("videoId"), video.get("title", {}).get("runs", [{}])[0].get("text"))
        if count >= 10:
            break
            
if __name__ == "__main__":
    test_scrape()
