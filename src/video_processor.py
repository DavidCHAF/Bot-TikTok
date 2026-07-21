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
        
        try:
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
        except asyncio.CancelledError:
            print("\n[DEBUG] Processus FFmpeg annulé (CancelledError).")
            raise
        finally:
            if process.returncode is None:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
        
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

def generate_ass(vtt_path: str, ass_path: str, video_width: int, video_height: int, margin_v: int, style_type: str = "hormozi"):
    try:
        with open(vtt_path, 'r', encoding='utf-8') as f:
            vtt_lines = f.readlines()
            
        if style_type == "hormozi":
            # Font Bubblegum, jaune, bordure noire de 4px
            style_def = f"Style: Default,Bubblegum,55,&H0000FFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,20,20,{int(margin_v)},1"
        else:
            style_def = f"Style: Default,Bubblegum,30,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,20,20,20,1"
            
        ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_def}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        def convert_time(vtt_time):
            vtt_time = vtt_time.replace(',', '.')
            parts = vtt_time.split(':')
            if len(parts) == 2:
                m, s = parts
                h = '0'
            elif len(parts) == 3:
                h, m, s = parts
            else:
                return vtt_time
                
            if '.' in s:
                s, ms = s.split('.')
            else:
                ms = '000'
            return f"{int(h)}:{m}:{s}.{ms[:2]}"
            
        i = 0
        while i < len(vtt_lines):
            line = vtt_lines[i].strip()
            if '-->' in line:
                start_vtt, end_vtt = line.split(' --> ')
                start_ass = convert_time(start_vtt.strip())
                end_ass = convert_time(end_vtt.strip())
                
                text_block = []
                i += 1
                while i < len(vtt_lines) and vtt_lines[i].strip() != '':
                    text_block.append(vtt_lines[i].strip())
                    i += 1
                text_raw = '\\N'.join(text_block)
                
                if style_type == "hormozi":
                    # Effet pop-in propre : fondu très rapide + scale de 80% -> 110% -> 100% (sans rotation pendulaire)
                    text_ass = f"{{\\fad(50,50)\\fscx80\\fscy80\\t(0,80,\\fscx110\\fscy110)\\t(80,150,\\fscx100\\fscy100)}}{text_raw.upper()}"
                else:
                    text_ass = text_raw
                    
                ass_content += f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text_ass}\n"
            else:
                i += 1
                
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)
        return True
    except Exception as e:
        print(f"[Remaster] Erreur generate_ass: {e}")
        return False

async def remaster_video_full_pipeline(input_path: str, output_path: str, progress_callback=None) -> bool:
    try:
        print(f"[Remaster] Demarrage du pipeline IA Double Voix pour {input_path}...")
        work_dir = os.path.dirname(input_path)
        basename = os.path.splitext(os.path.basename(input_path))[0]
        
        # Detection OCR dynamique
        if progress_callback: await progress_callback(5)
        static_texts, dynamic_zones, dynamic_count, video_width, video_height = await asyncio.to_thread(detect_text_zones, input_path)
        
        has_subtitles = len(dynamic_zones) > 0
        
        main_script = ""
        desc_script = ""
        vocals_wav = None
        no_vocals_wav = None
        main_tts_audio = None
        main_tts_vtt = None
        desc_tts_audio = None
        desc_tts_vtt = None
        
        if has_subtitles:
            # 1. Separation Audio via Local Demucs
            if progress_callback: await progress_callback(10)
            vocals_wav, no_vocals_wav = await ai_remaster.separate_audio_local(input_path, work_dir)
            if not vocals_wav:
                return False
                
            # 2. Transcription (Whisper tiny)
            if progress_callback: await progress_callback(30)
            segments = ai_remaster.transcribe_audio_with_timestamps(vocals_wav)
            
            # 3. Description Gemini Vision (Commenté pour debug)
            if progress_callback: await progress_callback(40)
            # desc_script = ai_remaster.describe_video_visually(input_path)
            
            main_tts_audio = os.path.join(work_dir, f"{basename}_main_tts.mp3")
            main_tts_vtt = os.path.join(work_dir, f"{basename}_main_tts.vtt")
            def write_vtt(segments, filepath):
                def format_time(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    millisecs = int((seconds - int(seconds)) * 1000)
                    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecs:03d}"
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write("WEBVTT\n\n")
                    for i, seg in enumerate(segments):
                        start = format_time(seg['start'])
                        end = format_time(seg['end'])
                        f.write(f"{i+1}\n{start} --> {end}\n{seg['text']}\n\n")
            
            write_vtt(segments, main_tts_vtt)
            
            main_script = " ".join([seg['text'] for seg in segments])
            
            # Anti-hallucination Whisper: si le texte est microscopique, ou si c'est une phrase typique d'hallucination (YouTube outro)
            hallucinations = ["thank you for watching", "thanks for watching", "see you in the next video", "amara.org", "sous-titres par"]
            script_lower = main_script.lower()
            is_hallucination = any(h in script_lower for h in hallucinations)
            
            if len(main_script.strip()) < 10 or is_hallucination:
                main_script = ""
                segments = []
                
            if segments:
                # On génère l'audio TTS synchronisé segment par segment avec analyse du genre vocal
                await ai_remaster.generate_synced_tts(segments, main_tts_audio, voice="en-US-ChristopherNeural", source_audio_path=vocals_wav)
                
            # 5. Generation TTS Descriptive
            if progress_callback: await progress_callback(60)
            desc_tts_audio = os.path.join(work_dir, f"{basename}_desc_tts.mp3")
            desc_tts_vtt = os.path.join(work_dir, f"{basename}_desc_tts.vtt")
            if desc_script:
                await ai_remaster.generate_tts(desc_script, desc_tts_audio, desc_tts_vtt, voice="fr-FR-VivienneNeural")
            
        # 6. Assemblage FFmpeg Visuel
        if progress_callback: await progress_callback(70)
        print("[Remaster] Assemblage FFmpeg Visuel...")
        
        video = ffmpeg.input(input_path).video
        
        margin_v = 150
        # Floutage pour textes dynamiques (vrais sous-titres, ou watermarks récalcitrants)
        if dynamic_zones:
            for dz in dynamic_zones:
                box_x = max(0, dz['x'] - 5)
                box_y = max(0, dz['y'] - 5)
                box_w = min(video_width - box_x, dz['w'] + 10)
                box_h = min(video_height - box_y, dz['h'] + 10)
                
                start_t = dz.get('start_t', 0)
                end_t = dz.get('end_t', 999)
                
                split = video.split()
                # Effet 'verre dépoli' très doux avec gblur au lieu de boxblur
                blurred_dyn = split[1].crop(x=box_x, y=box_y, width=box_w, height=box_h).filter('gblur', sigma=30, steps=3)
                video = ffmpeg.overlay(split[0], blurred_dyn, x=box_x, y=box_y)
                
            lowest_z = max(dynamic_zones, key=lambda z: z['y'] + z['h'])
            # L'aimantation parfaite : on centre le texte verticalement dans la zone floutée
            box_center_y = lowest_z['y'] + (lowest_z['h'] / 2)
            margin_v = int(video_height - box_center_y - 25) # 25 compense environ la moitié de la taille de la police

            
        # Floutage delogo pour textes statiques (titres)
        if static_texts:
            # Fusionner uniquement les rectangles qui se touchent ou sont très proches (15px)
            # Cela crée des boîtes de flou sur-mesure au lieu d'une boîte géante.
            boxes = [{'x': st.get('blur_x', st['x']), 'y': st.get('blur_y', st['y']), 'w': st.get('blur_w', st['w']), 'h': st.get('blur_h', st['h'])} for st in static_texts]
            merged = True
            while merged:
                merged = False
                for i in range(len(boxes)):
                    for j in range(i + 1, len(boxes)):
                        b1 = boxes[i]
                        b2 = boxes[j]
                        # S'ils sont à moins de 40px l'un de l'autre
                        if (b1['x'] < b2['x'] + b2['w'] + 40 and b1['x'] + b1['w'] + 40 > b2['x'] and
                            b1['y'] < b2['y'] + b2['h'] + 40 and b1['y'] + b1['h'] + 40 > b2['y']):
                            
                            min_x = min(b1['x'], b2['x'])
                            min_y = min(b1['y'], b2['y'])
                            max_x = max(b1['x'] + b1['w'], b2['x'] + b2['w'])
                            max_y = max(b1['y'] + b1['h'], b2['y'] + b2['h'])
                            
                            boxes[i] = {'x': min_x, 'y': min_y, 'w': max_x - min_x, 'h': max_y - min_y}
                            boxes.pop(j)
                            merged = True
                            break
                    if merged:
                        break
                        
            for b in boxes:
                box_x = max(0, b['x'] - 80)
                box_y = max(0, b['y'] - 20)
                box_w = min(video_width - box_x, b['w'] + 160)
                box_h = min(video_height - box_y, b['h'] + 40)
                
                # Remplacement de delogo par un vrai boxblur robuste
                split = video.split()
                radius = int(min(box_w / 2.1, box_h / 2.1, 40))
                blurred_crop = split[1].crop(x=box_x, y=box_y, width=box_w, height=box_h).filter('boxblur', lr=radius, lp=2, cr=0)
                video = ffmpeg.overlay(split[0], blurred_crop, x=box_x, y=box_y)

        # Miroir + Zoom léger statique (sans altérer le framerate)
        video = ffmpeg.filter(video, 'hflip')
        video = ffmpeg.filter(video, 'crop', w='iw*0.95', h='ih*0.95', x='iw*0.025', y='ih*0.025')
        video = ffmpeg.filter(video, 'scale', video_width, video_height)
        
        # Redessiner les textes statiques par-dessus le flou, sauf les watermarks (@)
        font_path = os.path.abspath("fonts/Bubblegum.ttf").replace('\\', '/')
        for st in static_texts:
            if '@' not in st['text'] and st['text'] != 'DYNAMIC_SUBTITLES':
                # Cap the fontsize to avoid FFmpeg "error too large"
                fontsize = max(25, min(100, int(st['h'] * 0.9)))
                safe_text = st['text'].replace("'", "\\'").replace(":", "\\:")
                # On centre horizontalement (w-text_w)/2, et on garde la position y originale
                # x='(w-tw)/2' utilise l'expression dynamique de FFmpeg
                video = ffmpeg.drawtext(video, text=safe_text, x='(w-text_w)/2', y=st['y'], fontsize=fontsize, fontcolor='white', borderw=4, bordercolor='black', fontfile=font_path)
        
        font_dir = os.path.abspath("fonts").replace('\\', '/')
        # Sous-titres
        if main_script and main_tts_vtt and os.path.exists(main_tts_vtt):
            main_ass_path = os.path.join(work_dir, f"{basename}_main.ass")
            generate_ass(main_tts_vtt, main_ass_path, video_width, video_height, margin_v, "hormozi")
            safe_ass = os.path.abspath(main_ass_path).replace('\\', '/')
            video = ffmpeg.filter(video, 'subtitles', filename=safe_ass, fontsdir=font_dir)
            
        if desc_script and desc_tts_vtt and os.path.exists(desc_tts_vtt):
            desc_ass_path = os.path.join(work_dir, f"{basename}_desc.ass")
            generate_ass(desc_tts_vtt, desc_ass_path, video_width, video_height, 20, "classic")
            safe_ass = os.path.abspath(desc_ass_path).replace('\\', '/')
            video = ffmpeg.filter(video, 'subtitles', filename=safe_ass, fontsdir=font_dir)
            
        # Mixage Audio
        if progress_callback: await progress_callback(85)
        audio_inputs = []
        if no_vocals_wav and os.path.exists(no_vocals_wav):
            audio_inputs.append(ffmpeg.input(no_vocals_wav).audio)
        if main_script and main_tts_audio and os.path.exists(main_tts_audio):
            audio_inputs.append(ffmpeg.input(main_tts_audio).audio)
        if desc_script and desc_tts_audio and os.path.exists(desc_tts_audio):
            audio_inputs.append(ffmpeg.input(desc_tts_audio).audio)
            
        if len(audio_inputs) == 3:
            # Musique = 0.2, TTS Principal = 2.0, TTS Descriptif = 0.5
            audio_mix = ffmpeg.filter(audio_inputs, 'amix', inputs=3, weights="0.2 2.0 0.5", duration='longest')
            audio_mix = ffmpeg.filter(audio_mix, 'volume', '2.0') # Boost du volume final
        elif len(audio_inputs) == 2:
            # Musique = 0.2, TTS Principal = 2.0
            audio_mix = ffmpeg.filter(audio_inputs, 'amix', inputs=2, weights="0.2 2.0", duration='longest')
            audio_mix = ffmpeg.filter(audio_mix, 'volume', '2.0') # Boost du volume final
        elif len(audio_inputs) == 1:
            audio_mix = ffmpeg.filter(audio_inputs[0], 'volume', '2.0')
        else:
            audio_mix = ffmpeg.input(input_path).audio
        
        out = ffmpeg.output(
            video, 
            audio_mix, 
            output_path, 
            vcodec='libx264', 
            acodec='aac',
            crf=26,
            preset='fast',
            maxrate='4M',
            bufsize='8M',
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
import collections
import easyocr

def is_similar_box(b1, b2, threshold=50):
    return abs(b1[0]-b2[0]) < threshold and abs(b1[1]-b2[1]) < threshold

def detect_text_zones(video_path):
    print(f"[OCR] Analyse de la video avec EasyOCR (1 fps) : {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], [], 1080, 1920
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0: fps = 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    if total_frames == 0:
        return [], [], width, height
        
    duration = total_frames / fps
    sample_indices = [int(fps * i) for i in range(int(duration))]
    if not sample_indices:
        sample_indices = [0]
        
    reader = easyocr.Reader(['fr', 'en'], gpu=False)
    all_texts = []
    
    for idx in sample_indices:
        if idx >= total_frames: break
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret: continue
        
        results = reader.readtext(frame)
        frame_boxes = []
        for (bbox, text, prob) in results:
            if prob > 0.45 and len(text.strip()) >= 1:
                x_coords = [int(p[0]) for p in bbox]
                y_coords = [int(p[1]) for p in bbox]
                x = min(x_coords)
                y = min(y_coords)
                w = max(x_coords) - x
                h = max(y_coords) - y
                frame_boxes.append({'text': text.strip(), 'box': (x, y, w, h), 'prob': prob})
                
        # Fusionner les boites sur la meme ligne pour rattraper les lettres isolees comme le "i"
        merged = True
        while merged:
            merged = False
            for i in range(len(frame_boxes)):
                for j in range(i+1, len(frame_boxes)):
                    b1 = frame_boxes[i]['box']
                    b2 = frame_boxes[j]['box']
                    # S'ils sont sur la meme ligne (y proche) et pas trop eloignes
                    if abs(b1[1] - b2[1]) < 40:
                        min_x = min(b1[0], b2[0])
                        min_y = min(b1[1], b2[1])
                        max_x = max(b1[0] + b1[2], b2[0] + b2[2])
                        max_y = max(b1[1] + b1[3], b2[1] + b2[3])
                        
                        frame_boxes[i]['box'] = (min_x, min_y, max_x - min_x, max_y - min_y)
                        frame_boxes[i]['text'] = frame_boxes[i]['text'] + " " + frame_boxes[j]['text']
                        frame_boxes.pop(j)
                        merged = True
                        break
                if merged:
                    break
                    
        for fb in frame_boxes:
            all_texts.append({'text': fb['text'], 'box': fb['box'], 'frame': idx, 'prob': fb['prob']})
    cap.release()
    
    location_clusters = []
    for t in all_texts:
        placed = False
        for cluster in location_clusters:
            ref = cluster[0]['box']
            # Tolerance: x et y a 50px pres, w et h a 100px pres (la largeur peut varier un peu avec l'OCR)
            if abs(t['box'][0] - ref[0]) < 80 and abs(t['box'][1] - ref[1]) < 60 and abs(t['box'][2] - ref[2]) < 250:
                cluster.append(t)
                placed = True
                break
        if not placed:
            location_clusters.append([t])
            
    static_texts = []
    num_samples = len(sample_indices)
    
    for cluster in location_clusters:
        if len(cluster) >= num_samples * 0.85: # Si meme position/taille pdt 85% du temps = STATIQUE
            avg_x = int(sum(i['box'][0] for i in cluster) / len(cluster))
            avg_y = int(sum(i['box'][1] for i in cluster) / len(cluster))
            avg_w = int(sum(i['box'][2] for i in cluster) / len(cluster))
            avg_h = int(sum(i['box'][3] for i in cluster) / len(cluster))
            
            min_x = min(i['box'][0] for i in cluster)
            min_y = min(i['box'][1] for i in cluster)
            max_x = max(i['box'][0] + i['box'][2] for i in cluster)
            max_y = max(i['box'][1] + i['box'][3] for i in cluster)
            
            from collections import Counter
            actual_text = Counter(i['text'] for i in cluster).most_common(1)[0][0]
            
            static_texts.append({
                'text': actual_text,
                'x': avg_x, 'y': avg_y, 'w': avg_w, 'h': avg_h,
                'blur_x': min_x, 'blur_y': min_y, 'blur_w': max_x - min_x, 'blur_h': max_y - min_y
            })
            for i in cluster:
                i['is_static'] = True

    dynamic_boxes = []
    dynamic_texts_set = set()
    dynamic_location_groups = []
    
    for t in all_texts:
        if not t.get('is_static', False):
            text = t['text'].strip()
            if t['prob'] > 0.6 and len(text) >= 3 and any(c.isalpha() for c in text):
                placed = False
                for group in dynamic_location_groups:
                    # Regrouper par le CENTRE VERTICAL (y + h/2) pour être robuste aux sous-titres multi-lignes !
                    first_center_y = group[0]['box'][1] + (group[0]['box'][3] / 2)
                    t_center_y = t['box'][1] + (t['box'][3] / 2)
                    if abs(t_center_y - first_center_y) < 100:
                        group.append(t)
                        placed = True
                        break
                if not placed:
                    dynamic_location_groups.append([t])


            
    dynamic_zones = []
    for group in dynamic_location_groups:
        # On valide la zone SI ET SEULEMENT SI le texte est présent au moins 30% de la durée totale de la vidéo.
        # Cela permet d'ignorer totalement les popups courts (pseudos, annotations) tout en captant les sous-titres,
        # sans se faire avoir par le "bruit" de l'OCR qui créait des faux textes uniques.
        if len(group) >= num_samples * 0.30:
            xs = [t['box'][0] for t in group]
            ys = [t['box'][1] for t in group]
            ws = [t['box'][2] for t in group]
            hs = [t['box'][3] for t in group]
            
            # Puisque le groupe est maintenant très strict sur la position (80px), on peut utiliser min/max en toute sécurité
            min_x = min(xs)
            min_y = min(ys)
            max_x = max([x+w for x, w in zip(xs, ws)])
            max_y = max([y+h for y, h in zip(ys, hs)])
            
            pad_x = int(width * 0.02)
            pad_y = int(height * 0.01)
            min_x = max(0, min_x - pad_x)
            min_y = max(0, min_y - pad_y)
            max_x = min(width, max_x + pad_x)
            max_y = min(height, max_y + pad_y)
            
            dynamic_zones.append({
                'x': min_x, 'y': min_y, 'w': max_x - min_x, 'h': max_y - min_y,
                'start_t': 0,
                'end_t': 999
            })
        
    return static_texts, dynamic_zones, len(dynamic_texts_set), width, height
