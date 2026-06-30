import os
import random
import ffmpeg
import requests
import socket

# --- HACK ANTI-CENSURE ORACLE DNS ---
# Oracle Cloud bloque la résolution DNS des domaines .de, .ru, .sh, .rocks
# On force Python à utiliser le DNS de Google (DoH) pour trouver l'adresse IP de nos serveurs.
old_getaddrinfo = socket.getaddrinfo

def custom_dns_resolver(*args, **kwargs):
    host = args[0]
    if host in ['cobalt.q-n-d.de', 'co.wuk.sh', 'cobalt.api.zmatey.ru']:
        try:
            # On demande l'IP directement à Google
            r = requests.get(f"https://dns.google/resolve?name={host}&type=A", timeout=5)
            ip = r.json()['Answer'][0]['data']
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, args[1] if len(args)>1 else 443))]
        except Exception as e:
            pass
    return old_getaddrinfo(*args, **kwargs)

# On applique le patch réseau
socket.getaddrinfo = custom_dns_resolver
# ------------------------------------

def download_video(url: str, output_dir: str) -> str:
    """Télécharge une vidéo via l'API publique Cobalt (avec DNS anti-censure)."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    try:
        video_id = url.split('/')[-1].split('?')[0]
        out_path = os.path.join(output_dir, f"{video_id}.mp4")
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        data = {
            "url": url,
            "vCodec": "h264"
        }
        
        # Nos instances de secours fiables
        instances = [
            "https://co.wuk.sh/api/json",
            "https://cobalt.q-n-d.de/api/json"
        ]
        
        res = None
        for api_url in instances:
            try:
                # 1. Requête API (le DNS passera par Google automatiquement grâce au patch)
                r = requests.post(api_url, headers=headers, json=data, timeout=15)
                if r.status_code == 200:
                    res = r.json()
                    break
            except Exception as e:
                print(f"Échec {api_url} : {e}")
                continue
                
        if not res:
            print("Erreur : Impossible de joindre les serveurs Cobalt malgré le patch DNS.")
            return ""
            
        # 2. Téléchargement du MP4
        download_url = res.get("url")
        if not download_url:
            print("Erreur : Cobalt n'a pas renvoyé de lien MP4.")
            return ""
            
        r_vid = requests.get(download_url, stream=True, timeout=30)
        r_vid.raise_for_status()
        
        with open(out_path, 'wb') as f:
            for chunk in r_vid.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return out_path
        
    except Exception as e:
        print(f"Erreur globale Cobalt : {e}")
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
