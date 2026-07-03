import os
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import scrapetube
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
        "crazy xyz", "pubg", "bgmi", "free fire", "whatsapp status",
        "fact", "facts", "knowledge", "story", "kahani", "hindi", "india", "bhai"
    ]
    text_lower = text.lower()
    for kw in blacklist_keywords:
        if kw in text_lower:
            return False
            
    return True

def scrape_youtube_shorts(niche: str, max_videos: int = 500, lang: str = None) -> list:
    """
    Fonction pour scraper YouTube Shorts. 
    Utilise Scrapetube pour la recherche (0 quota Google) et l'API Google pour les stats (1 quota / 50 vidéos).
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise Exception("Clé YOUTUBE_API_KEY manquante.")

    youtube = build("youtube", "v3", developerKey=api_key)
    videos = []
    
    queries = [
        f"{niche} #shorts",
        f"{niche} tiktok",
        f"{niche} viral",
        f"{niche} trend",
        f"{niche} compilation",
        f"{niche} video"
    ]
    
    for query in queries:
        if len(videos) >= max_videos:
            break
            
        print(f"📡 Scrapetube: Recherche furtive pour '{query}'...")
        
        try:
            # results_type="video" permet de ne pas ramener de chaînes ou playlists
            search_results = scrapetube.get_search(query, sort_by="upload_date", results_type="video")
            
            batch_ids = []
            for video_item in search_results:
                if len(videos) >= max_videos:
                    break
                    
                video_id = video_item.get("videoId")
                if not video_id:
                    continue
                    
                batch_ids.append(video_id)
                
                # Quand on a ramassé 50 IDs, on demande les stats à l'API Google (Batching)
                if len(batch_ids) == 50:
                    valid_batch = process_video_batch(batch_ids, youtube, max_videos - len(videos), lang)
                    videos.extend(valid_batch)
                    batch_ids = []
                    print(f"✅ Scraping progressif: {len(videos)} Shorts validés...")
            
            # Traiter le reliquat (si on sort de la boucle avec moins de 50 IDs en attente)
            if batch_ids and len(videos) < max_videos:
                valid_batch = process_video_batch(batch_ids, youtube, max_videos - len(videos), lang)
                videos.extend(valid_batch)
                print(f"✅ Scraping progressif: {len(videos)} Shorts validés...")
                
        except Exception as e:
            print(f"⚠️ Erreur Scrapetube sur '{query}': {e}")
            
    return videos[:max_videos]

def process_video_batch(video_ids: list, youtube, needed: int, lang: str) -> list:
    """
    Interroge l'API Google pour récupérer les stats, la durée, et le pays d'un batch de 50 vidéos maximum.
    Filtre les résultats et retourne les vidéos valides.
    """
    valid_videos = []
    if not video_ids:
        return valid_videos
        
    try:
        stats_response = youtube.videos().list(
            part="statistics,snippet,contentDetails",
            id=",".join(video_ids)
        ).execute()
        
        stats_items = stats_response.get("items", [])
        
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
                pass
                
        allowed_countries = None
        if lang:
            target_lang = lang.split("-")[0] if "-" in lang else lang
            if target_lang == 'en':
                allowed_countries = ['US', 'CA', 'GB', 'AU', 'NZ', None]
            elif target_lang == 'fr':
                allowed_countries = ['FR', 'CA', 'BE', 'CH', None]
                
        for stat in stats_items:
            stats = stat.get("statistics", {})
            snippet = stat.get("snippet", {})
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            channel_title = snippet.get("channelTitle", "")
            channel_id = snippet.get("channelId", "")
            country = channel_countries.get(channel_id)
            
            # Vérification de la durée (Shorts = < 4 minutes max)
            duration = stat.get("contentDetails", {}).get("duration", "")
            if "H" in duration:
                continue
            match = re.search(r'PT(\d+)M', duration)
            if match and int(match.group(1)) >= 4:
                continue
            
            # Filtrage Pays
            if allowed_countries is not None:
                if country not in allowed_countries:
                    continue
            else:
                banned_countries = ['IN', 'ID', 'PK', 'BD', 'RU', 'VN', 'TH', 'PH', 'MY', 'BR']
                if country in banned_countries:
                    continue
            
            # Filtrage scripts/mots-clés asie
            if not is_western_content(title) or not is_western_content(description) or not is_western_content(channel_title):
                continue
                
            # Filtrage IA de langue
            if lang:
                target_lang = lang.split("-")[0] if "-" in lang else lang
                full_text = f"{title}. {description}"
                if not is_correct_language(full_text, target_lang):
                    continue
            
            valid_videos.append({
                "id": stat["id"],
                "url": f"https://www.youtube.com/shorts/{stat['id']}",
                "title": title,
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "shares": 0,
                "create_time": snippet.get("publishedAt", "")
            })
            
            if len(valid_videos) >= needed:
                break
                
    except Exception as e:
        print(f"❌ Erreur API Google (Vues/Likes): {e}")
        
    return valid_videos

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

