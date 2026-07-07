import os
import random
import asyncio
import re
import time
import yt_dlp
import ffmpeg

def download_video(url: str, output_dir: str) -> str:
    """TÃ©lÃ©charge une vidÃ©o via yt-dlp avec un VRAI fichier cookies.txt."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    cookie_path = os.path.join(project_root, 'cookies.txt')
    
    ydl_opts = {
        # On force H264 (avc1) et on limite la taille Ã  1080p vertical (hauteur <= 1920) 
        # pour Ã©viter que YouTube nous envoie du 4K AV1 impossible Ã  dÃ©coder sur un petit CPU.
        'format': 'bestvideo[height<=1920][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[height<=1920][ext=mp4]+bestaudio[ext=m4a]/best[height<=1920]/best',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'quiet': False,
        'verbose': True,
        'cookiefile': cookie_path,
        'socket_timeout': 15,
        'retries': 3
    }
    
    try:
        print(f"ðŸ”§ [DEBUG] Lancement yt-dlp pour {url}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("ðŸ”§ [DEBUG] YoutubeDL instance crÃ©Ã©e. Extraction info...")
            info_dict = ydl.extract_info(url, download=True)
            print("ðŸ”§ [DEBUG] Extraction terminÃ©e.")
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
    Applique des filtres discrets via FFmpeg pour contourner la dÃ©tection.
    """
    try:
        print(f"ðŸ”§ [DEBUG] DÃ©marrage FFmpeg : {input_path} -> {output_path}")
        duration = await get_video_duration(input_path)
        
        # Rotation alÃ©atoire trÃ¨s lÃ©gÃ¨re (-1 Ã  1 degrÃ© max)
        rotation_deg = random.uniform(-1.0, 1.0)
        stream = ffmpeg.input(input_path)
        video = stream.video
        audio = stream.audio
        
        # 0. Redimensionnement "Crop to Fill" pour forcer le 9:16 parfait sans Ã©crasement
        video = ffmpeg.filter(video, 'scale', w=1080, h=1920, force_original_aspect_ratio='increase')
        video = ffmpeg.filter(video, 'crop', 1080, 1920)
        
        # 1. Ajustement colorimÃ©trique imperceptible
        video = ffmpeg.filter(video, 'eq', brightness=0.01, contrast=1.01, saturation=1.02)
        
        # 2. AccÃ©lÃ©ration de 1% (Bypass redoutable)
        video = ffmpeg.filter(video, 'setpts', '0.99*PTS')
        audio = ffmpeg.filter(audio, 'atempo', '1.01')
        
        # 3. Bruit lÃ©ger sur la luminance
        video = ffmpeg.filter(video, 'noise', c0s=1, c0f='t+u')
        
        # Assemblage et encodage
        out = ffmpeg.output(
            video, 
            audio, 
            output_path, 
            map_metadata='-1', 
            vcodec='libx264', 
            crf=26, 
            preset='ultrafast',
            maxrate='4.5M',
            bufsize='9M',
            threads=1,
            acodec='aac'
        ).overwrite_output().global_args('-nostdin')
        
        args = out.compile()
        
        print(f"ðŸ”§ [DEBUG] Lancement async de FFmpeg. DurÃ©e totale: {duration}s")
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL, # EmpÃªche le deadlock du buffer stdout
            stderr=asyncio.subprocess.PIPE
        )
        
        time_regex = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")
        last_update_time = time.time()
        
        full_stderr = []
        buffer = ""
        
        while True:
            chunk = await process.stderr.read(1024)
            if not chunk:
                break
                
            chunk_str = chunk.decode('utf-8', errors='ignore')
            full_stderr.append(chunk_str)
            
            # Afficher dans le terminal brut
            print(chunk_str, end='', flush=True)
            
            buffer += chunk_str
            
            if duration > 0 and progress_callback:
                matches = list(time_regex.finditer(buffer))
                if matches:
                    last_match = matches[-1]
                    h, m, s = last_match.groups()
                    current_time_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    percent = min(100, int((current_time_sec / duration) * 100))
                    
                    if time.time() - last_update_time >= 2.0:
                        try:
                            await progress_callback(percent)
                        except Exception as e:
                            pass # Ignorer les erreurs Telegram limit
                        last_update_time = time.time()
                    
                    # On Ã©vite d'accumuler un buffer gÃ©ant en mÃ©moire, on garde juste la fin
                    buffer = buffer[-200:]
                        
        await process.wait()
        
        if process.returncode == 0:
            if progress_callback:
                try:
                    await progress_callback(100)
                except:
                    pass
            print(f"\nðŸ”§ [DEBUG] FFmpeg a terminÃ© avec succÃ¨s.")
            return True
        else:
            stderr_out = "".join(full_stderr)
            print(f"\nâŒ Erreur FFmpeg (Code {process.returncode}):\n{stderr_out}")
            return False
            
    except Exception as e:
            print(f"\n❌ Erreur FFmpeg (Code {process.returncode}):\n{stderr_out}")
            return False
import os
import random
import asyncio
import re
import time
import yt_dlp
import ffmpeg

def download_video(url: str, output_dir: str) -> str:
    """TÃ©lÃ©charge une vidÃ©o via yt-dlp avec un VRAI fichier cookies.txt."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    cookie_path = os.path.join(project_root, 'cookies.txt')
    
    ydl_opts = {
        # On force H264 (avc1) et on limite la taille Ã  1080p vertical (hauteur <= 1920) 
        # pour Ã©viter que YouTube nous envoie du 4K AV1 impossible Ã  dÃ©coder sur un petit CPU.
        'format': 'bestvideo[height<=1920][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[height<=1920][ext=mp4]+bestaudio[ext=m4a]/best[height<=1920]/best',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'quiet': False,
        'verbose': True,
        'cookiefile': cookie_path,
        'socket_timeout': 15,
        'retries': 3
    }
    
    try:
        print(f"ðŸ”§ [DEBUG] Lancement yt-dlp pour {url}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("ðŸ”§ [DEBUG] YoutubeDL instance crÃ©Ã©e. Extraction info...")
            info_dict = ydl.extract_info(url, download=True)
            print("ðŸ”§ [DEBUG] Extraction terminÃ©e.")
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
    Applique des filtres discrets via FFmpeg pour contourner la dÃ©tection.
    """
    try:
        print(f"ðŸ”§ [DEBUG] DÃ©marrage FFmpeg : {input_path} -> {output_path}")
        duration = await get_video_duration(input_path)
        
        # Rotation alÃ©atoire trÃ¨s lÃ©gÃ¨re (-1 Ã  1 degrÃ© max)
        rotation_deg = random.uniform(-1.0, 1.0)
        stream = ffmpeg.input(input_path)
        video = stream.video
        audio = stream.audio
        
        # 0. Redimensionnement "Crop to Fill" pour forcer le 9:16 parfait sans Ã©crasement
        video = ffmpeg.filter(video, 'scale', w=1080, h=1920, force_original_aspect_ratio='increase')
        video = ffmpeg.filter(video, 'crop', 1080, 1920)
        
        # 1. Ajustement colorimÃ©trique imperceptible
        video = ffmpeg.filter(video, 'eq', brightness=0.01, contrast=1.01, saturation=1.02)
        
        # 2. AccÃ©lÃ©ration de 1% (Bypass redoutable)
        video = ffmpeg.filter(video, 'setpts', '0.99*PTS')
        audio = ffmpeg.filter(audio, 'atempo', '1.01')
        
        # 3. Bruit lÃ©ger sur la luminance
        video = ffmpeg.filter(video, 'noise', c0s=1, c0f='t+u')
        
        # Assemblage et encodage
        out = ffmpeg.output(
            video, 
            audio, 
            output_path, 
            map_metadata='-1', 
            vcodec='libx264', 
            crf=26, 
            preset='ultrafast',
            maxrate='4.5M',
            bufsize='9M',
            threads=1,
            acodec='aac'
        ).overwrite_output().global_args('-nostdin')
        
        args = out.compile()
        
        print(f"ðŸ”§ [DEBUG] Lancement async de FFmpeg. DurÃ©e totale: {duration}s")
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL, # EmpÃªche le deadlock du buffer stdout
            stderr=asyncio.subprocess.PIPE
        )
        
        time_regex = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")
        last_update_time = time.time()
        
        full_stderr = []
        buffer = ""
        
        while True:
            chunk = await process.stderr.read(1024)
            if not chunk:
                break
                
            chunk_str = chunk.decode('utf-8', errors='ignore')
            full_stderr.append(chunk_str)
            
            # Afficher dans le terminal brut
            print(chunk_str, end='', flush=True)
            
            buffer += chunk_str
            
            if duration > 0 and progress_callback:
                matches = list(time_regex.finditer(buffer))
                if matches:
                    last_match = matches[-1]
                    h, m, s = last_match.groups()
                    current_time_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    percent = min(100, int((current_time_sec / duration) * 100))
                    
                    if time.time() - last_update_time >= 2.0:
                        try:
                            await progress_callback(percent)
                        except Exception as e:
                            pass # Ignorer les erreurs Telegram limit
                        last_update_time = time.time()
                    
                    # On Ã©vite d'accumuler un buffer gÃ©ant en mÃ©moire, on garde juste la fin
                    buffer = buffer[-200:]
                        
        await process.wait()
        
        if process.returncode == 0:
            if progress_callback:
                try:
                    await progress_callback(100)
                except:
                    pass
            print(f"\nðŸ”§ [DEBUG] FFmpeg a terminÃ© avec succÃ¨s.")
            return True
        else:
            stderr_out = "".join(full_stderr)
            print(f"\nâ Œ Erreur FFmpeg (Code {process.returncode}):\n{stderr_out}")
            return False
            
    except Exception as e:
        print(f"🔧 [DEBUG] Exception inattendue dans process_video : {e}")
        return False
import src.ai_remaster as ai_remaster

async def remaster_video_full_pipeline(input_path: str, output_path: str, progress_callback=None) -> bool:
    try:
        print(f"[Remaster] Demarrage du pipeline IA pour {input_path}...")
        work_dir = os.path.dirname(input_path)
        basename = os.path.splitext(os.path.basename(input_path))[0]
        
        # 1. Separation Audio (Demucs)
        if progress_callback: await progress_callback(10)
        vocals_wav, no_vocals_wav = await ai_remaster.separate_audio(input_path, work_dir)
        
        # 2. Transcription
        if progress_callback: await progress_callback(40)
        transcript = ai_remaster.transcribe_audio(vocals_wav)
        
        if not transcript or len(transcript.strip()) < 2:
            print("[Remaster] Aucun texte transcrit. Application des filtres visuels de base uniquement.")
            return await process_video(input_path, output_path, progress_callback)
        
        # 3. Paraphrase Gemini
        if progress_callback: await progress_callback(60)
        new_script = ai_remaster.paraphrase_text(transcript)
        if not new_script:
            print("[Remaster] Impossible de paraphraser. Fallback au script original.")
            new_script = transcript
            
        # 4. Generation TTS + Sous-titres
        if progress_callback: await progress_callback(70)
        tts_audio = os.path.join(work_dir, f"{basename}_tts.mp3")
        tts_vtt = os.path.join(work_dir, f"{basename}_tts.vtt")
        
        success = await ai_remaster.generate_tts(new_script, tts_audio, tts_vtt)
        if not success:
            return False
            
        # Detection OCR dynamique
        zones, video_height = await asyncio.to_thread(detect_text_zones, input_path)
        
        # 5. Montage FFmpeg (Incrustation VTT, Mixage Audio, Bande Noire)
        if progress_callback: await progress_callback(85)
        print("[Remaster] Assemblage FFmpeg final...")
        
        video = ffmpeg.input(input_path).video
        
        # Application des masques dynamiques
        if zones:
            print(f"[Remaster] {len(zones)} zones de texte detectees. Masquage...")
            for z in zones:
                video = ffmpeg.filter(video, 'drawbox', x=z['x'], y=z['y'], width=z['w'], height=z['h'], color='black@0.95', t='fill')
            
            main_z = max(zones, key=lambda z: z['w']*z['h'])
            box_center_y = main_z['y'] + (main_z['h'] / 2)
            margin_v = video_height - box_center_y - 20
            if margin_v < 10: margin_v = 10
        else:
            print("[Remaster] Aucun texte detecte. Utilisation de la zone de sous-titres par defaut.")
            video = ffmpeg.filter(video, 'drawbox', x='(iw-w)/2', y='ih*0.75', width='iw*0.85', height='ih*0.15', color='black@0.95', t='fill')
            margin_v = int(video_height * 0.17) if video_height else 120
            
        # Sous-titres VTT
        vtt_safe = tts_vtt.replace('\\', '/')
        vtt_safe = vtt_safe.replace(':', '\\:')
        video = ffmpeg.filter(video, 'subtitles', filename=vtt_safe, force_style=f'FontSize=16,PrimaryColour=&H00FFFFFF,MarginV={int(margin_v)},Alignment=2')
        
        # Mixage Audio
        audio_no_vocals = ffmpeg.input(no_vocals_wav).audio
        audio_tts = ffmpeg.input(tts_audio).audio
        audio_mix = ffmpeg.filter([audio_no_vocals, audio_tts], 'amix', inputs=2, duration='longest')
        
        out = ffmpeg.output(
            video, 
            audio_mix, 
            output_path, 
            vcodec='libx264', 
            acodec='aac',
            shortest=None
        ).overwrite_output().global_args('-nostdin')
        
        process = await asyncio.create_subprocess_exec(
            *out.compile(),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        
        if process.returncode == 0:
            if progress_callback: await progress_callback(100)
            return True
        else:
            print(f"[Remaster] Erreur FFmpeg : {stderr.decode()}")
            return False
            
    except Exception as e:
        print(f"[Remaster] Erreur critique : {e}")
        return False

import cv2
import pytesseract

def detect_text_zones(video_path):
    print(f"[OCR] Analyse de la video pour detecter le texte : {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], 1920
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    if total_frames == 0:
        return [], height
        
    sample_indices = [int(total_frames * i / 6) for i in range(1, 6)]
    boxes = []
    
    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret: continue
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        try:
            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 60:
                    text = data['text'][i].strip()
                    if len(text) > 2:
                        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                        boxes.append((x, y, w, h))
        except Exception as e:
            print(f"[OCR] Erreur Tesseract: {e}")
            break # Si Tesseract n'est pas installe, on arrete
            
    cap.release()
    
    if not boxes:
        return [], height
        
    top_boxes = [b for b in boxes if b[1] < height / 2]
    bottom_boxes = [b for b in boxes if b[1] >= height / 2]
    
    merged_zones = []
    for zone_boxes in [top_boxes, bottom_boxes]:
        if not zone_boxes: continue
        min_x = min([b[0] for b in zone_boxes])
        min_y = min([b[1] for b in zone_boxes])
        max_x = max([b[0]+b[2] for b in zone_boxes])
        max_y = max([b[1]+b[3] for b in zone_boxes])
        
        pad_x = int(width * 0.05)
        pad_y = int(height * 0.03)
        min_x = max(0, min_x - pad_x)
        min_y = max(0, min_y - pad_y)
        max_x = min(width, max_x + pad_x)
        max_y = min(height, max_y + pad_y)
        
        merged_zones.append({
            'x': min_x, 'y': min_y, 'w': max_x - min_x, 'h': max_y - min_y
        })
        
    return merged_zones, height
