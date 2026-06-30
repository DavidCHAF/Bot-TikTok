import os
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def is_western_content(text: str) -> bool:
    """
    Vérifie si le texte contient des caractères d'alphabets non-occidentaux.
    Retourne False si on détecte du Cyrillique, Arabe, Hindi, Thaï, Chinois, etc.
    """
    if not text:
        return True
    
    # Plages Unicode blacklistées : Cyrillique, Arabe, Devanagari, Bengali, Thaï, CJK (Asie)
    forbidden_pattern = re.compile(
        r'[\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u0980-\u09FF\u0E00-\u0E7F\u4E00-\u9FFF\u3040-\u30FF\u3130-\u318F\uAC00-\uD7AF]'
    )
    return not bool(forbidden_pattern.search(text))

def scrape_youtube_shorts(niche: str, max_videos: int = 500, lang: str = None) -> list:
    """
    Fonction pour scraper YouTube Shorts via l'API Officielle Google (YouTube Data API v3).
    Récupère jusqu'à max_videos vidéos récentes pour un hashtag donné (avec filtre de langue optionnel).
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise Exception("Clé YOUTUBE_API_KEY manquante. Veuillez la configurer dans l'environnement.")

    youtube = build("youtube", "v3", developerKey=api_key)
    
    videos = []
    next_page_token = None
    
    # On ajoute #shorts à la requête pour cibler au maximum ce format
    query = f"{niche} #shorts"
    print(f"📡 Appel de l'API YouTube pour la recherche: {query}")
    
    try:
        while len(videos) < max_videos:
            # 1. Étape Recherche (Search)
            search_params = {
                "q": query,
                "part": "id,snippet",
                "type": "video",
                "videoDuration": "short", # Filtre officiel pour les vidéos < 4 min
                "order": "date",          # Tri strict par date d'ajout
                "maxResults": 50,
                "pageToken": next_page_token
            }
            
            # Injection de la langue si spécifiée
            if lang:
                search_params["relevanceLanguage"] = lang
                # Si l'utilisateur demande de l'anglais, on force la région US pour éviter l'Inde/Asie
                if lang.lower() == 'en':
                    search_params["regionCode"] = "US"
                
            search_response = youtube.search().list(**search_params).execute()
            
            search_items = search_response.get("items", [])
            if not search_items:
                break
                
            # Extraire les IDs pour récupérer les statistiques
            video_ids = [item["id"]["videoId"] for item in search_items]
            
            # 2. Étape Statistiques (Videos)
            # On fait une requête groupée (batch) pour avoir les vues/likes des 50 vidéos d'un coup
            stats_response = youtube.videos().list(
                part="statistics,snippet",
                id=",".join(video_ids)
            ).execute()
            
            stats_items = stats_response.get("items", [])
            
            for stat in stats_items:
                stats = stat.get("statistics", {})
                snippet = stat.get("snippet", {})
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                
                # Filtrage : On exclut les vidéos dont le titre ou la description contient des scripts asiatiques/indiens/arabes/russes
                if not is_western_content(title) or not is_western_content(description):
                    continue
                
                videos.append({
                    "id": stat["id"],
                    "url": f"https://www.youtube.com/shorts/{stat['id']}",
                    "title": title,
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                    "shares": 0, # YouTube API ne donne pas les partages
                    "create_time": snippet.get("publishedAt", "") # Format ISO 8601
                })
                
                if len(videos) >= max_videos:
                    break
            
            print(f"✅ Scraping: {len(videos)} Shorts récupérés...")
            
            next_page_token = search_response.get("nextPageToken")
            if not next_page_token:
                break
                
    except HttpError as e:
        print(f"❌ Erreur API YouTube: {e}")
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        
    return videos[:max_videos]

def get_youtube_stats(video_ids: list) -> list:
    """
    Récupère uniquement les statistiques (T2) pour une liste précise d'IDs YouTube.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise Exception("Clé YOUTUBE_API_KEY manquante.")

    youtube = build("youtube", "v3", developerKey=api_key)
    videos = []
    
    # YouTube API permet des requêtes par lots de 50 IDs maximum
    batch_size = 50
    for i in range(0, len(video_ids), batch_size):
        batch_ids = video_ids[i:i+batch_size]
        
        try:
            stats_response = youtube.videos().list(
                part="statistics,snippet",
                id=",".join(batch_ids)
            ).execute()
            
            for stat in stats_response.get("items", []):
                stats = stat.get("statistics", {})
                snippet = stat.get("snippet", {})
                videos.append({
                    "id": stat["id"],
                    "url": f"https://www.youtube.com/shorts/{stat['id']}",
                    "title": snippet.get("title", ""),
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                    "shares": 0,
                    "create_time": snippet.get("publishedAt", "")
                })
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des stats: {e}")
            
    return videos

