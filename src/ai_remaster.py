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
        
    print(f"✍️ [Whisper] Transcription de l'audio (modèle 'tiny' int8 + VAD)...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    # L'activation de vad_filter (Voice Activity Detection) empêche Whisper d'halluciner sur les bruits
    segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=True, condition_on_previous_text=False)
    
    results = []
    for segment in segments:
        results.append({
            'text': segment.text.strip(),
            'start': segment.start,
            'end': segment.end
        })
        
    del model
    return results

def describe_video_visually(video_path: str) -> list:
    """
    Utilise Gemini Vision pour décrire la vidéo par segments de 15 secondes.
    Retourne une liste de dicts: [{'start': 0, 'end': 15, 'text': '...'}, ...]
    """
    import cv2
    import PIL.Image
    
    if not api_key or not client:
        return [{'start': 0.0, 'end': 15.0, 'text': "Une vidéo très amusante."}]
        
    print(f"👁️ [Gemini Vision] Analyse visuelle de la vidéo par segments de 15s...")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0: fps = 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    if duration <= 0:
        cap.release()
        return []

    interval = 15.0
    num_segments = int(duration // interval) + (1 if duration % interval > 0 else 0)
    
    segments = []
    
    for i in range(num_segments):
        start_time = i * interval
        end_time = min((i + 1) * interval, duration)
        
        frames_to_extract = [
            int((start_time + (end_time - start_time) * 0.25) * fps),
            int((start_time + (end_time - start_time) * 0.50) * fps),
            int((start_time + (end_time - start_time) * 0.75) * fps)
        ]
        
        images = []
        for frame_idx in frames_to_extract:
            if frame_idx >= total_frames: continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                images.append(PIL.Image.fromarray(frame_rgb))
                
        if not images:
            continue
            
        prompt = "Describe in a funny and humorous way what is happening in this 15-second video segment (1 very short sentence). CRITICAL: NEVER include introductory phrases like 'Sure, here is a description' or 'In this video'. Output ONLY the raw comedy background voice-over text."
        
        fallback_models = [
            'gemini-3.5-flash', 
            'gemini-3.5-flash-lite',
            'gemini-3.6-flash',
            'gemini-3-flash',
            'gemini-3.1-flash-lite',
            'gemini-2.5-flash',
            'gemini-2.5-flash-lite'
        ]
        
        success = False
        for model_name in fallback_models:
            try:
                print(f"👁️ [Gemini Vision] Requête segment {start_time:.1f}s - {end_time:.1f}s avec le modèle {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt] + images
                )
                
                # Nettoyage des hallucinations d'intro typiques des LLMs
                raw_text = response.text.strip()
                import re
                clean_text = re.sub(r'^(?i)(sure[, ]*here is a description|here is a description|in this video[,:]*|here\'s a description)[\s:]*', '', raw_text).strip()
                
                segments.append({
                    'start': start_time,
                    'end': end_time,
                    'text': clean_text
                })
                success = True
                break # Succès, on sort de la boucle de fallback
            except Exception as e:
                print(f"⚠️ [Gemini Vision] Erreur avec {model_name} : {e}")
                import time
                time.sleep(1) # Petite pause avant d'essayer le modèle suivant
                
        if not success:
            print(f"❌ [Gemini Vision] Échec final pour le segment {i}. Tous les modèles ont été tentés.")
            
    cap.release()
    return segments

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
def analyze_video_genders(audio_path: str, segments: list) -> dict:
    """
    Analyse dynamique de genre (100% hors-ligne) via Clustering 27D:
    Utilise 13 MFCCs + 13 Delta MFCCs + Pitch pour séparer
    les voix lourdement modifiées sans aucune API avec une précision redoutable.
    """
    genders = {}
    if not segments: return genders
    
    try:
        import librosa
        import numpy as np
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        
        # Extraire les features (27 dimensions) pour chaque segment
        features = []
        valid_indices = []
        
        print(f"🎵 [Gender] Analyse acoustique experte (27D MFCC+Pitch) de {len(segments)} segments...")
        
        for i, seg in enumerate(segments):
            start_s = seg['start']
            end_s = seg['end']
            
            # Échantillonnage à 16000Hz pour des MFCC stables
            y, sr = librosa.load(audio_path, sr=16000, offset=start_s, duration=(end_s - start_s))
            if len(y) == 0:
                features.append(np.zeros(27))
                continue
                
            # 1. Pitch (F0)
            f0, voiced_flag, _ = librosa.pyin(y, fmin=50, fmax=400, sr=sr)
            valid_f0 = f0[voiced_flag]
            pitch = np.median(valid_f0) if len(valid_f0) > 0 else 0
            
            # 2. MFCC et Delta MFCC
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc_delta = librosa.feature.delta(mfcc)
            
            mfcc_mean = np.mean(mfcc, axis=1)
            mfcc_delta_mean = np.mean(mfcc_delta, axis=1)
            
            # 3. Concaténation (27D)
            vec = np.concatenate([mfcc_mean, mfcc_delta_mean, [pitch]])
            features.append(vec)
            
            if pitch > 0:
                valid_indices.append(i)
                
        # --- Etape de Clustering ---
        if not valid_indices:
            return {i: "male" for i in range(len(segments))}
            
        X_valid = [features[i] for i in valid_indices]
        
        pitches = [x[-1] for x in X_valid]
        if len(X_valid) < 2 or np.std(pitches) < 15:
            # S'il n'y a qu'une voix ou pas de variance
            mean_pitch = np.mean(pitches)
            default_gender = "female" if mean_pitch > 200 else "male"
            print(f"🎵 [Gender] Mono-locuteur détecté -> {default_gender.upper()}")
            for i in range(len(segments)):
                genders[i] = default_gender if features[i][-1] > 0 else "male"
            return genders
            
        # Clustering K-Means
        X_array = np.array(X_valid)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_array)
        
        kmeans = KMeans(n_clusters=2, random_state=42, n_init=20).fit(X_scaled)
        
        # Identifier le cluster Femme vs Homme
        # On regarde le Pitch (dernier élément du vecteur 27D)
        centers_orig = scaler.inverse_transform(kmeans.cluster_centers_)
        pitch_cluster_0 = centers_orig[0][-1]
        pitch_cluster_1 = centers_orig[1][-1]
        
        # La voix la plus aiguë est la femme
        female_cluster_idx = 0 if pitch_cluster_0 > pitch_cluster_1 else 1
        
        print(f"🎵 [Gender] Cluster 0 - Pitch Moyen: {pitch_cluster_0:.1f}Hz")
        print(f"🎵 [Gender] Cluster 1 - Pitch Moyen: {pitch_cluster_1:.1f}Hz")
        print(f"🎵 [Gender] Cluster {female_cluster_idx} assigné à FEMME.")
        
        # Assigner les genres
        for i, vec in enumerate(features):
            if vec[-1] == 0:
                genders[i] = "male"
            else:
                scaled_feat = scaler.transform([vec])
                cluster = kmeans.predict(scaled_feat)[0]
                g = "female" if cluster == female_cluster_idx else "male"
                genders[i] = g
                print(f"🎵 [Gender] Segment {i} -> {g.upper()}")
                
        return genders
        
    except Exception as e:
        print(f"⚠️ [Gender] Erreur Clustering 27D: {e}")
        return {i: "male" for i in range(len(segments))}

async def generate_synced_tts(segments, output_audio_path: str, voice: str = "en-US-ChristopherNeural", source_audio_path: str = None):
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
    
    # 1. Analyse dynamique des genres pour toute la vidéo d'un coup
    segment_genders = {}
    if source_audio_path:
        segment_genders = analyze_video_genders(source_audio_path, segments)
    
    # Piste vide de la durée totale de la vidéo
    total_duration_ms = int(segments[-1]['end'] * 1000) + 2000
    final_audio = AudioSegment.silent(duration=total_duration_ms)
    
    for i, seg in enumerate(segments):
        clean_text = re.sub(r'[^\w\s.,!?\']', '', seg['text']).strip()
        if len(clean_text) < 2: continue
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
            tmp_path = tmp_audio.name
            
        current_voice = voice
        if source_audio_path and i in segment_genders:
            gender = segment_genders[i]
            if gender == "female":
                if "Christopher" in voice or "Guy" in voice or "Eric" in voice:
                    current_voice = "en-US-JennyNeural"
                elif "Henri" in voice or "Claude" in voice:
                    current_voice = "fr-FR-VivienneNeural"
                
        cmd = ["edge-tts", "--voice", current_voice, "--text", clean_text, "--write-media", tmp_path]
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
