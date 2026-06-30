import os
import random
import ffmpeg
from pytubefix import YouTube
from pytubefix.cli import on_progress

def download_video(url: str, output_dir: str) -> str:
    """Télécharge une vidéo via pytubefix (Clients TV/IOS pour esquiver les blocages)."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    try:
        # Essai 1 : Client TV (Esquive souvent la détection bot sans aucun token)
        yt = YouTube(url, client='TV')
        video_id = yt.video_id
        stream = yt.streams.get_highest_resolution()
        
        if not stream:
            raise Exception("Aucun flux trouvé avec le client TV")
            
        out_path = stream.download(output_path=output_dir, filename=f"{video_id}.mp4")
        return out_path
        
    except Exception as e1:
        print(f"Échec Pytubefix (TV) : {e1}")
        try:
            # Essai 2 : Client IOS en secours
            yt = YouTube(url, client='IOS')
            video_id = yt.video_id
            stream = yt.streams.get_highest_resolution()
            
            if not stream:
                raise Exception("Aucun flux trouvé avec le client IOS")
                
            out_path = stream.download(output_path=output_dir, filename=f"{video_id}.mp4")
            return out_path
        except Exception as e2:
            print(f"Échec Pytubefix (IOS) : {e2}")
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
