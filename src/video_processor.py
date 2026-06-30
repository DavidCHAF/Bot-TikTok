import os
import random
import ffmpeg
import requests

def download_video(url: str, output_dir: str) -> str:
    """Télécharge une vidéo via le proxy d'Invidious (Masque l'IP Oracle complètement)."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    try:
        video_id = url.split('/')[-1].split('?')[0]
        out_path = os.path.join(output_dir, f"{video_id}.mp4")
        
        # Liste de serveurs Invidious ultra-stables
        instances = [
            "https://vid.puffyan.us",
            "https://invidious.jing.rocks",
            "https://inv.tux.pizza"
        ]
        
        success = False
        for instance in instances:
            # On tente la qualité 720p (itag=22), si elle n'existe pas, on passe en 360p (itag=18)
            for itag in [22, 18]:
                # Le paramètre local=true force le serveur Invidious à télécharger la vidéo à notre place
                download_url = f"{instance}/latest_version?id={video_id}&itag={itag}&local=true"
                try:
                    r_vid = requests.get(download_url, stream=True, timeout=20)
                    if r_vid.status_code == 200 and 'video' in r_vid.headers.get('Content-Type', ''):
                        with open(out_path, 'wb') as f:
                            for chunk in r_vid.iter_content(chunk_size=8192):
                                f.write(chunk)
                        success = True
                        break # On a trouvé une vidéo valide, on arrête de chercher des itags
                except Exception as e:
                    print(f"Échec {instance} (itag {itag}) : {e}")
                    continue
            if success:
                break # On arrête de chercher d'autres serveurs
                
        if not success:
            print("Erreur : Tous les serveurs Invidious ont échoué ou bloqué l'accès.")
            return ""
            
        return out_path
        
    except Exception as e:
        print(f"Erreur globale Invidious : {e}")
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
