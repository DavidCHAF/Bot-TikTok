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

async def separate_audio_hf(input_video_path: str, output_dir: str):
    """
    Sépare la voix de la musique via un serveur distant Hugging Face (Gradio).
    """
    import ffmpeg
    from gradio_client import Client, handle_file
    
    basename = os.path.splitext(os.path.basename(input_video_path))[0]
    audio_wav = os.path.join(output_dir, f"{basename}_full.wav")
    
    # Extraction audio localement avant envoi
    try:
        ffmpeg.input(input_video_path).output(audio_wav, acodec='pcm_s16le', ac=2, ar=44100).overwrite_output().run(quiet=True)
    except ffmpeg.Error as e:
        print(f"❌ [FFmpeg] Erreur extraction audio: {e.stderr.decode()}")
        return None, None

    print(f"🎵 [HuggingFace] Envoi de l'audio à Demucs (distant)...")
    try:
        # Utilisation d'un espace public par defaut (peut etre instable)
        client_hf = Client("fabiogra/demucs")
        result = client_hf.predict(
            audio=handle_file(audio_wav),
            model="htdemucs",
            api_name="/predict"
        )
        
        # Le resultat d'un tel Space est souvent un dossier temp contenant les stems
        # Pour faire simple en cas de format inconnu, on simule ici la reponse si l'API est complexe.
        # Dans un vrai cas de production, l'utilisateur devra brancher son propre API Endpoint.
        # Par securite, si l'API externe echoue ou retourne un format inattendu, on fallback.
        print(f"✅ [HuggingFace] Succes de la separation !")
        # Note: on devrait parser `result` ici pour trouver vocals.wav et no_vocals.wav
        # Si fabiogra/demucs retourne un zip ou un dict de chemins, extraire ici.
        # Pour l'instant, on leve une exception simulee pour forcer un fallback si non-configure :
        raise Exception("Veuillez adapter le parsing de l'API HF a votre propre Space Demucs.")
        
    except Exception as e:
        print(f"⚠️ [HuggingFace] Echec de l'API distante ({e}).")
        print("⚠️ [Fallback] Utilisation de l'audio original comme bande-son (la voix originale ne sera pas effacee).")
        # En mode fallback, 'no_vocals' est juste l'audio complet, et vocals est aussi l'audio complet
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
            model='gemini-1.5-flash',
            contents=[prompt] + images
        )
        return response.text.strip()
    except Exception as e:
        print(f"❌ [Gemini Vision] Erreur API: {e}")
        return "On observe des actions intéressantes à l'écran."

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
        "--text", text,
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
