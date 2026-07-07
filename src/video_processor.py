import os
import random
import yt_dlp
import ffmpeg

def download_video(url: str, output_dir: str) -> str:
    """Télécharge une vidéo via yt-dlp avec un VRAI fichier cookies.txt."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    cookie_path = os.path.join(project_root, 'cookies.txt')
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/b',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'quiet': False,
        'verbose': True,
        'cookiefile': cookie_path,
        'socket_timeout': 15,
        'retries': 3
    }
    
    try:
        print(f"🔧 [DEBUG] Lancement yt-dlp pour {url}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("🔧 [DEBUG] YoutubeDL instance créée. Extraction info...")
            info_dict = ydl.extract_info(url, download=True)
            print("🔧 [DEBUG] Extraction terminée.")
            video_id = info_dict.get('id', 'video')
            ext = info_dict.get('ext', 'mp4')
            return os.path.join(output_dir, f"{video_id}.{ext}")
    except Exception as e:
        print(f"Erreur yt-dlp avec cookies sur {url} : {e}")
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
        # On coupe 8% de chaque côté. On force les dimensions paires avec floor(X/2)*2 pour libx264
        video = ffmpeg.filter(video, 'crop', w='floor(iw*0.84/2)*2', h='floor(ih*0.84/2)*2', x='floor(iw*0.08/2)*2', y='floor(ih*0.08/2)*2')
        
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
            preset='ultrafast', # Soulage la RAM et le CPU
            threads=1, # Évite que FFmpeg n'explose la RAM sur un petit serveur
            acodec='aac'
        )
        
        out.overwrite_output().run(capture_stdout=True, capture_stderr=True)
        return True
    except ffmpeg.Error as e:
        print("Erreur FFmpeg :")
        if e.stderr:
            print(e.stderr.decode('utf-8', errors='ignore'))
        return False
