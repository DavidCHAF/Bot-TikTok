import os
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

def is_correct_language(text: str, target_lang: str) -> bool:
    """
    Vérifie si le texte correspond à la langue cible.
    Utilise langdetect pour filtrer strictement l'Espagnol, le Turc, l'Allemand, etc.
    """
    if not text or len(text) < 10:
        return True
        
    try:
        detected = detect(text)
        # Si on veut de l'anglais, on bloque les langues parasites courantes
        if target_lang == 'en' and detected in ['es', 'tr', 'de', 'fr', 'pt', 'it', 'nl', 'pl', 'ro']:
            return False
        # Si on veut du français, on bloque l'anglais, espagnol, etc.
        if target_lang == 'fr' and detected in ['en', 'es', 'tr', 'de', 'pt', 'it', 'nl']:
            return False
    except LangDetectException:
        pass
        
    return True

def is_western_content(text: str) -> bool:
    """
    Vérifie si le texte contient des caractères d'alphabets non-occidentaux.
    Retourne False si on détecte du Cyrillique, Arabe, Hindi, Thaï, Chinois, etc.
    Ou s'il contient des mots-clés typiques de fermes de contenu asiatiques/indiennes.
    """
    if not text:
        return True
    
    # Plages Unicode blacklistées : Cyrillique, Arabe, Devanagari, Bengali, Thaï, CJK (Asie)
    forbidden_pattern = re.compile(
        r'[\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u0980-\u09FF\u0E00-\u0E7F\u4E00-\u9FFF\u3040-\u30FF\u3130-\u318F\uAC00-\uD7AF]'
    )
    if forbidden_pattern.search(text):
        return False
        
    # Mots-clés typiques des fermes de clic indiennes/russes/asiatiques
    blacklist_keywords = [
        "wait for end", "wait for it", "respect", "sigma rule", 
        "boys attitude", "girls attitude", "komedi", "mr indian",
        "crazy xyz", "pubg", "bgmi", "free fire", "whatsapp status"
    ]
    text_lower = text.lower()
    for kw in blacklist_keywords:
        if kw in text_lower:
            return False
            
    return True

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
                if "-" in lang:
                    language, region = lang.split("-", 1)
                    search_params["relevanceLanguage"] = language
                    search_params["regionCode"] = region.upper()
                else:
                    search_params["relevanceLanguage"] = lang
                    # Si l'utilisateur demande juste de l'anglais, on force la région US par défaut
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
            
            # 3. Étape Pays de la Chaîne (Channels)
            # On récupère le pays d'origine de toutes les chaînes de ces 50 vidéos
            channel_ids = list(set([stat["snippet"]["channelId"] for stat in stats_items if "channelId" in stat["snippet"]]))
            channel_countries = {}
            if channel_ids:
                try:
                    channels_response = youtube.channels().list(
                        part="snippet",
                        id=",".join(channel_ids)
                    ).execute()
                    for ch in channels_response.get("items", []):
                        country = ch.get("snippet", {}).get("country")
                        if country:
                            channel_countries[ch["id"]] = country.upper()
                except Exception as e:
                    print(f"⚠️ Erreur récupération pays channels: {e}")
            
            # Pays à bannir (fermes de contenu majeures)
            banned_countries = ['IN', 'ID', 'PK', 'BD', 'RU', 'VN', 'TH', 'PH', 'MY', 'BR']
            
            for stat in stats_items:
                stats = stat.get("statistics", {})
                snippet = stat.get("snippet", {})
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                channel_id = snippet.get("channelId", "")
                country = channel_countries.get(channel_id)
                
                # Filtrage strict du pays de la chaîne YouTube
                if country in banned_countries:
                    continue
                
                # Filtrage : On exclut les vidéos dont le titre ou la description contient des scripts asiatiques/indiens/arabes/russes
                if not is_western_content(title) or not is_western_content(description):
                    continue
                    
                # Filtrage de langue strict (langdetect) si une langue est demandée
                if lang:
                    target_lang = lang.split("-")[0] if "-" in lang else lang
                    full_text = f"{title}. {description}"
                    if not is_correct_language(full_text, target_lang):
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

