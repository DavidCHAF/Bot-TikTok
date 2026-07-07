import os
import random
import asyncio
import re
import time
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
        # On force le codec H264 (avc1) car le format AV1 (401) par défaut fige le décodage FFmpeg sur une petite VM
        'format': 'bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best',
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

async def get_video_duration(input_path: str) -> float:
    try:
        # On capture stderr pour voir s'il y a une erreur ffprobe
        probe = await asyncio.to_thread(ffmpeg.probe, input_path)
        return float(probe['format']['duration'])
    except ffmpeg.Error as e:
        print(f"Erreur ffprobe: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)}")
        return 0.0
    except Exception as e:
        print(f"Erreur ffprobe inattendue: {e}")
        return 0.0

async def process_video(input_path: str, output_path: str, progress_callback=None) -> bool:
    """
    Applique des filtres discrets via FFmpeg pour contourner la détection.
    """
    try:
        print(f"🔧 [DEBUG] Démarrage FFmpeg : {input_path} -> {output_path}")
        duration = await get_video_duration(input_path)
        
        # Rotation aléatoire entre -1.5 et 1.5 degrés
        rotation_deg = random.uniform(-1.5, 1.5)
        angle_rad = rotation_deg * (3.14159 / 180.0)
        
        stream = ffmpeg.input(input_path)
        video = stream.video
        audio = stream.audio
        
        # 1. Rotation subtile
        video = ffmpeg.filter(video, 'rotate', a=angle_rad)
        
        # 2. Crop pour enlever les filigranes (souvent sur les bords) et les bords noirs de la rotation
        video = ffmpeg.filter(video, 'crop', w='floor(iw*0.84/2)*2', h='floor(ih*0.84/2)*2', x='floor(iw*0.08/2)*2', y='floor(ih*0.08/2)*2')
        
        # 3. Bruit léger (Optimisé pour petit CPU)
        video = ffmpeg.filter(video, 'noise', c0s=1, c0f='t+u')
        
        # Assemblage et encodage
        out = ffmpeg.output(
            video, 
            audio, 
            output_path, 
            map_metadata='-1', 
            vcodec='libx264', 
            crf=23, 
            preset='ultrafast',
            threads=1,
            acodec='aac'
        ).overwrite_output().global_args('-nostdin')
        
        args = out.compile()
        
        print(f"🔧 [DEBUG] Lancement async de FFmpeg. Durée totale: {duration}s")
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        time_regex = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")
        last_update_time = time.time()
        
        full_stderr = []
        
        while True:
            line = await process.stderr.readline()
            if not line:
                break
                
            line_str = line.decode('utf-8', errors='ignore')
            full_stderr.append(line_str)
            
            if duration > 0 and progress_callback:
                match = time_regex.search(line_str)
                if match:
                    h, m, s = match.groups()
                    current_time_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    percent = min(100, int((current_time_sec / duration) * 100))
                    
                    if time.time() - last_update_time >= 5.0:
                        try:
                            await progress_callback(percent)
                        except Exception as e:
                            pass # Ignorer les erreurs Telegram limit
                        last_update_time = time.time()
                        
        await process.wait()
        
        if process.returncode == 0:
            if progress_callback:
                try:
                    await progress_callback(100)
                except:
                    pass
            print(f"🔧 [DEBUG] FFmpeg a terminé avec succès.")
            return True
        else:
            stderr_out = "".join(full_stderr)
            print(f"❌ Erreur FFmpeg (Code {process.returncode}):\n{stderr_out}")
            return False
            
    except Exception as e:
        print(f"🔧 [DEBUG] Exception inattendue dans process_video : {e}")
        return False
