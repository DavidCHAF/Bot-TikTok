import os
import asyncio
import subprocess
from faster_whisper import WhisperModel
from google import genai

# Configuration de Gemini
api_key = os.getenv("GEMINI_API_KEY")
client = None
if not api_key:
    print("❌ [Gemini] ERREUR CRITIQUE : La variable d'environnement GEMINI_API_KEY est introuvable !")
    print("❌ [Gemini] Assurez-vous d'avoir tape : export GEMINI_API_KEY=\"VotreCle\"")
else:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"❌ [Gemini] Erreur d'initialisation du client : {e}")

async def separate_audio_local(input_video_path: str, output_dir: str):
    """
    Sépare la voix de la musique via Demucs en local (faible conso RAM).
    """
    import ffmpeg
    import shutil
    
    basename = os.path.splitext(os.path.basename(input_video_path))[0]
    audio_wav = os.path.join(output_dir, f"{basename}_full.wav")
    
    # Extraction audio localement avant envoi
    try:
        ffmpeg.input(input_video_path).output(audio_wav, acodec='pcm_s16le', ac=2, ar=44100).overwrite_output().run(quiet=True)
    except ffmpeg.Error as e:
        print(f"❌ [FFmpeg] Erreur extraction audio: {e.stderr.decode()}")
        return None, None

    print(f"🎵 [Demucs] Séparation de l'audio en local (modèle mdx_extra_q)...")
    demucs_out_dir = os.path.join(output_dir, "demucs_out")
    os.makedirs(demucs_out_dir, exist_ok=True)
    
    try:
        # Exécution de demucs en local avec un modèle léger
        cmd = [
            "demucs",
            "-n", "mdx_extra_q",
            "-d", "cpu", # Force CPU pour utiliser moins de RAM/VRAM
            "--two-stems", "vocals",
            "-o", demucs_out_dir,
            audio_wav
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            print(f"❌ [Demucs] Erreur locale: {stderr.decode()}")
            raise Exception("Erreur d'exécution de Demucs local")
            
        print(f"✅ [Demucs] Succès de la séparation !")
        
        model_out_dir = os.path.join(demucs_out_dir, "mdx_extra_q", f"{basename}_full")
        vocals_generated = os.path.join(model_out_dir, "vocals.wav")
        no_vocals_generated = os.path.join(model_out_dir, "no_vocals.wav")
        
        final_vocals = os.path.join(output_dir, f"{basename}_vocals.wav")
        final_no_vocals = os.path.join(output_dir, f"{basename}_no_vocals.wav")
        
        if os.path.exists(vocals_generated) and os.path.exists(no_vocals_generated):
            shutil.move(vocals_generated, final_vocals)
            shutil.move(no_vocals_generated, final_no_vocals)
            shutil.rmtree(demucs_out_dir, ignore_errors=True)
            return final_vocals, final_no_vocals
        else:
            raise Exception("Fichiers de sortie introuvables.")
            
    except Exception as e:
        print(f"⚠️ [Demucs] Echec de l'exécution locale ({e}).")
        print("⚠️ [Fallback] Utilisation de l'audio original comme bande-son.")
        return audio_wav, audio_wav

def transcribe_audio_with_timestamps(audio_path: str):
    """
    Transcrit l'audio extrait avec faster-whisper (CPU optimisé) et renvoie les timestamps.
    """
    if not os.path.exists(audio_path):
        return []
        
    print(f"✍️ [Whisper] Transcription de l'audio (modèle 'tiny' int8)...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    results = []
    for segment in segments:
        results.append({
            'text': segment.text.strip(),
            'start': segment.start,
            'end': segment.end
        })
        
    del model
    return results

def describe_video_visually(video_path: str) -> str:
    """
    Utilise Gemini Vision pour décrire chronologiquement la vidéo.
    """
    import cv2
    import PIL.Image
    
    if not api_key or not client:
        return "Une vidéo très captivante."
        
    print(f"👁️ [Gemini Vision] Analyse visuelle de la vidéo en cours...")
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    frames_to_extract = [int(total_frames * i / 4) for i in range(1, 4)]
    images = []
    
    for frame_idx in frames_to_extract:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = PIL.Image.fromarray(frame_rgb)
            images.append(pil_img)
    cap.release()
    
    prompt = "Décris très brièvement ce qu'il se passe dans cette vidéo (1 ou 2 phrases simples). Ne fais aucune introduction, sois direct pour faire une voix-off passive."
    
    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=[prompt] + images
        )
        return response.text.strip()
    except Exception as e:
        print(f"❌ [Gemini Vision] Erreur API: {e}")
        return ""

async def generate_tts(text: str, output_audio_path: str, output_vtt_path: str, voice: str = "fr-FR-HenriNeural"):
    """
    Génère la voix TTS et les sous-titres parfaitement synchronisés (.vtt) via edge-tts.
    """
    # Nettoyage des caracteres bizarres qui font planter edge-tts
    import re
    clean_text = re.sub(r'[^\w\s.,!?\']', '', text).strip()
    
    if len(clean_text) < 2:
        print(f"❌ [Edge-TTS] Texte vide ou invalide apres nettoyage. Annulation TTS.")
        return False
        
    print(f"🗣️ [Edge-TTS] Génération de la nouvelle voix et des sous-titres...")
    cmd = [
        "edge-tts",
        "--voice", voice,
        "--text", clean_text,
        "--write-media", output_audio_path,
        "--write-subtitles", output_vtt_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        print(f"❌ [Edge-TTS] Erreur: {stderr.decode()}")
        return False
        
    return True

async def generate_synced_tts(segments, output_audio_path: str, voice: str = "en-US-ChristopherNeural"):
    """
    Génère un audio TTS où chaque phrase est générée individuellement et recalée
    exactement sur son timestamp d'origine. Si le TTS est trop long, il est accéléré.
    """
    from pydub import AudioSegment
    import tempfile
    import ffmpeg
    import re
    
    print(f"🗣️ [Edge-TTS] Génération synchronisée segment par segment...")
    
    if not segments: return False
    
    # Piste vide de la durée totale de la vidéo
    total_duration_ms = int(segments[-1]['end'] * 1000) + 2000
    final_audio = AudioSegment.silent(duration=total_duration_ms)
    
    for i, seg in enumerate(segments):
        clean_text = re.sub(r'[^\w\s.,!?\']', '', seg['text']).strip()
        if len(clean_text) < 2: continue
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
            tmp_path = tmp_audio.name
            
        cmd = ["edge-tts", "--voice", voice, "--text", clean_text, "--write-media", tmp_path]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        
        if process.returncode == 0 and os.path.exists(tmp_path):
            chunk = AudioSegment.from_file(tmp_path)
            orig_duration_ms = int((seg['end'] - seg['start']) * 1000)
            tts_duration_ms = len(chunk)
            
            # Si le TTS déborde du temps original (plus de 100ms de marge)
            if tts_duration_ms > orig_duration_ms + 100:
                speed_factor = tts_duration_ms / orig_duration_ms
                speed_factor = min(2.0, max(0.5, speed_factor)) # Limite ffmpeg
                
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_fast:
                    fast_path = tmp_fast.name
                    
                try:
                    ffmpeg.input(tmp_path).filter('atempo', speed_factor).output(fast_path).overwrite_output().run(quiet=True)
                    chunk = AudioSegment.from_file(fast_path)
                except Exception as e:
                    print(f"⚠️ [FFmpeg] Erreur atempo: {e}")
                finally:
                    if os.path.exists(fast_path): os.remove(fast_path)
                    
            final_audio = final_audio.overlay(chunk, position=int(seg['start'] * 1000))
            
        if os.path.exists(tmp_path): os.remove(tmp_path)
        
    final_audio.export(output_audio_path, format="mp3")
    return True
