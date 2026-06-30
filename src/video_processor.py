import os
import random
import ffmpeg
from pytubefix import YouTube

def download_video(url: str, output_dir: str) -> str:
    """Télécharge une vidéo depuis une URL via pytubefix (contourne les blocages Cloud)."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # pytubefix utilise automatiquement Deno (qui est installé) pour générer un PO-Token et esquiver le blocage !
    try:
        yt = YouTube(url, client='WEB')
        video_id = yt.video_id
        
        # Récupère le meilleur flux qui a l'image ET le son (parfait pour TikTok)
        stream = yt.streams.get_highest_resolution()
        
        # Télécharge la vidéo
        out_path = stream.download(output_path=output_dir, filename=f"{video_id}.mp4")
        return out_path
        
    except Exception as e:
        print(f"Erreur pytubefix sur {url} : {e}")
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
