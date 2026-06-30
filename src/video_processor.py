import os
import random
import ffmpeg
import requests

def download_video(url: str, output_dir: str) -> str:
    """Télécharge une vidéo via l'API publique Cobalt (contournement ULTIME des blocages Cloud)."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    try:
        video_id = url.split('/')[-1].split('?')[0]
        out_path = os.path.join(output_dir, f"{video_id}.mp4")
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Origin": "https://cobalt.tools",
            "Referer": "https://cobalt.tools/"
        }
        data = {
            "url": url,
            "vCodec": "h264" # Format idéal pour TikTok/FFmpeg
        }
        
        # On utilise UNIQUEMENT l'instance officielle (Cloudflare) car Oracle bloque les DNS exotiques
        api_url = "https://api.cobalt.tools/"
        
        try:
            # 1. Demande à l'API de récupérer la vidéo
            r = requests.post(api_url, headers=headers, json=data, timeout=15)
            r.raise_for_status()
            res = r.json()
        except Exception as e:
            print(f"Échec critique sur {api_url}: {e} | Réponse: {r.text if 'r' in locals() else 'Aucune'}")
            return ""
            
        # 2. Cobalt nous renvoie le lien direct MP4
        download_url = res.get("url")
        if not download_url:
            print("Erreur : Cobalt n'a pas renvoyé de lien.")
            return ""
            
        # 3. On télécharge le fichier
        r_vid = requests.get(download_url, stream=True, timeout=30)
        r_vid.raise_for_status()
        
        with open(out_path, 'wb') as f:
            for chunk in r_vid.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return out_path
        
    except Exception as e:
        print(f"Erreur globale sur le téléchargement Cobalt : {e}")
        return ""

def process_video(input_path: str, output_path: str) -> bool:
    """
    Applique des filtres discrets via FFmpeg pour contourner la détection :
    - Rotation très légère
    - Crop (recadrage) pour masquer les bords et les filigranes
    - Ajout de bruit/lignes très léger
    - Suppression des métadonnées
    """
    try:
        # Rotation aléatoire entre -1.5 et 1.5 degrés
        rotation_deg = random.uniform(-1.5, 1.5)
        angle_rad = rotation_deg * (3.14159 / 180.0)
        
        stream = ffmpeg.input(input_path)
        video = stream.video
        audio = stream.audio
        
        # 1. Rotation subtile
        video = ffmpeg.filter(video, 'rotate', a=angle_rad)
        
        # 2. Crop pour enlever les filigranes (souvent sur les bords) et les bords noirs de la rotation
        # On coupe 8% de chaque côté
        video = ffmpeg.filter(video, 'crop', w='iw*0.84', h='ih*0.84', x='iw*0.08', y='ih*0.08')
        
        # 3. Bruit léger / variations luma (quasi-imperceptible)
        video = ffmpeg.filter(video, 'noise', alls=1, allf='t+u')
        
        # Assemblage et encodage, -map_metadata -1 pour supprimer les métadonnées
        out = ffmpeg.output(
            video, 
            audio, 
            output_path, 
            map_metadata='-1', 
            vcodec='libx264', 
            crf=23, 
            preset='fast',
            acodec='aac'
        )
        
        out.overwrite_output().run(capture_stdout=True, capture_stderr=True)
        return True
    except ffmpeg.Error as e:
        print("Erreur FFmpeg :")
        if e.stderr:
            print(e.stderr.decode('utf-8', errors='ignore'))
        return False
