import os
import asyncio
import subprocess
from faster_whisper import WhisperModel
import google.generativeai as genai

# Configuration de Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

async def separate_audio(input_video_path: str, output_dir: str):
    """
    Lance Demucs pour séparer la voix de la musique.
    Crée un dossier htdemucs_ft/ dans output_dir.
    """
    cmd = [
        "demucs",
        "-n", "htdemucs_ft",
        "--two-stems", "vocals",
        input_video_path,
        "-o", output_dir
    ]
    
    print(f"🎵 [Demucs] Séparation audio en cours pour {os.path.basename(input_video_path)}...")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise Exception(f"Erreur Demucs: {stderr.decode()}")
        
    basename = os.path.splitext(os.path.basename(input_video_path))[0]
    vocals_path = os.path.join(output_dir, "htdemucs_ft", basename, "vocals.wav")
    no_vocals_path = os.path.join(output_dir, "htdemucs_ft", basename, "no_vocals.wav")
    
    return vocals_path, no_vocals_path

def transcribe_audio(audio_path: str) -> str:
    """
    Transcrit l'audio extrait avec faster-whisper (CPU optimisé).
    """
    if not os.path.exists(audio_path):
        return ""
        
    print(f"✍️ [Whisper] Transcription de l'audio...")
    # Mode CPU avec int8 pour économiser la RAM de la VM Oracle
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    full_text = []
    for segment in segments:
        full_text.append(segment.text)
        
    # Libération explicite de la mémoire
    del model
    
    return " ".join(full_text)

def paraphrase_text(transcript: str) -> str:
    """
    Réécrit le texte via Google Gemini API pour le rendre 100% original.
    """
    if not transcript or len(transcript.strip()) < 10:
        print("⚠️ [Gemini] Texte trop court pour être paraphrasé.")
        return ""
        
    print(f"🧠 [Gemini] Paraphrase sémantique en cours...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""Tu es un expert en création de contenu viral sur TikTok.
Voici le script exact d'une vidéo virale. Réécris ce script pour dire la même chose avec la même intensité et le même aspect captivant, mais en changeant complètement le vocabulaire et la structure des phrases pour que ce soit un script 100% original.
Ne rajoute aucune introduction ou conclusion, juste le script pur à lire à haute voix.

Texte original:
{transcript}
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ [Gemini] Erreur API: {e}")
        return transcript # Fallback on original text if API fails

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
