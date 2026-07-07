import os
import asyncio
import csv
import time
import glob
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

from src.scraper_youtube import scrape_youtube_shorts, get_youtube_stats
from src.analyzer import get_top_trends
from src.video_processor import download_video, process_video

# Token via environment variable
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "🛠 **Liste des commandes du Bot :**\n\n"
        "🔹 `/yt_t1 <niche> [langue-region]` : Sourcing initial. (ex: `/yt_t1 #business fr` ou `/yt_t1 #business en-US` ou `en-GB`)\n"
        "🔹 `/yt_t2 <niche>` : Analyse manuelle T2. Force le calcul et le téléchargement.\n"
        "🔹 `/status` : Affiche le tableau de bord de tous tes lancements en cours.\n"
        "🔹 `/clear <niche>|all` : Annule un ou tous les lancements en cours (ex: `/clear #business` ou `/clear all`).\n"
        "🔹 `/help` : Affiche ce message d'aide."
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "👋 Bienvenue sur le Bot Faceless Trend Predictor!\n\n"
        "Tape /help pour voir toutes les commandes disponibles."
    )

async def yt_t1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run real T1 sourcing for YouTube Shorts."""
    args = context.args
    niche = args[0] if len(args) > 0 else "général"
    lang = args[1] if len(args) > 1 else "en-US"
    chat_id = update.effective_chat.id
    
    lang_text = f" (Langue: {lang})" if lang else " (Monde entier)"
    await context.bot.send_message(chat_id=chat_id, text=f"🔍 Début du sourcing YouTube T1 pour '{niche}'{lang_text}... Patientez.")
    
    try:
        # On limite à 150 vidéos (au lieu de 500) pour ne pas exploser le quota API
        videos = await asyncio.to_thread(scrape_youtube_shorts, niche, 150, lang)
        
        if not videos:
            await context.bot.send_message(chat_id=chat_id, text="❌ Aucune vidéo trouvée ou erreur API.")
            return
            
        csv_filename = f"sourcing_yt_{niche}.csv"
        current_time = time.time()
        for v in videos:
            v['t1_timestamp'] = current_time
            
        with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=["id", "url", "title", "description", "views", "likes", "comments", "shares", "create_time", "t1_timestamp"])
            writer.writeheader()
            writer.writerows(videos)
            
        summary = "\n".join([f"- {v['title'][:30]}... ({v['views']} vues)" for v in videos[:3]])
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Sourcing YouTube T1 terminé pour '{niche}'. {len(videos)} vidéos récupérées.\n\n"
                 f"Top 3 actuels :\n{summary}\n\n"
                 "⏳ Compte à rebours de 3 heures (10800s) lancé en arrière-plan !"
        )
        
        with open(csv_filename, 'rb') as doc:
            await context.bot.send_document(chat_id=chat_id, document=doc, filename=csv_filename, caption="Voici l'export CSV complet T1.")
        
        # Programmation du T2 automatique dans 3 heures (10800 secondes)
        context.job_queue.run_once(auto_t2_job, 10800, data={'chat_id': chat_id, 'niche': niche})
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Erreur lors du scraping : {e}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all active timers based on existing CSV files."""
    csv_files = glob.glob("sourcing_yt_*.csv")
    if not csv_files:
        await update.message.reply_text("📭 Aucun lancement T1 en cours actuellement.")
        return
        
    msg = "📊 **Tableau de bord des lancements en cours :**\n\n"
    
    current_time = time.time()
    for file in csv_files:
        niche = file.replace("sourcing_yt_", "").replace(".csv", "")
        try:
            with open(file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                first_row = next(reader)
                t1_time = float(first_row.get('t1_timestamp', 0))
                
            elapsed = current_time - t1_time
            remaining = 10800 - elapsed
            
            if remaining > 0:
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                msg += f"⏳ `{niche}` : Reste {hours}h {minutes}m avant T2.\n"
            else:
                msg += f"✅ `{niche}` : Délai écoulé ! Le T2 est prêt ou déjà lancé.\n"
        except Exception:
            msg += f"⚠️ `{niche}` : Fichier illisible.\n"
            
    await update.message.reply_text(msg)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear ongoing T1 sourcing tasks."""
    args = context.args
    if not args:
        await update.message.reply_text("❌ Précise ce que tu veux effacer : `/clear all` ou `/clear <niche>`.")
        return
        
    target = args[0]
    chat_id = update.effective_chat.id
    
    if target.lower() == "all":
        files = glob.glob("sourcing_yt_*.csv")
        if not files:
            await context.bot.send_message(chat_id=chat_id, text="📭 Aucun lancement en cours à effacer.")
            return
        for file in files:
            try:
                os.remove(file)
            except Exception:
                pass
        await context.bot.send_message(chat_id=chat_id, text=f"🗑️ Tous les lancements en cours ({len(files)}) ont été annulés et effacés.")
    else:
        file = f"sourcing_yt_{target}.csv"
        if os.path.exists(file):
            try:
                os.remove(file)
                await context.bot.send_message(chat_id=chat_id, text=f"🗑️ Le lancement en cours pour '{target}' a été annulé et effacé.")
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Erreur lors de la suppression : {e}")
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Aucun lancement en cours trouvé pour '{target}'.")

async def execute_t2_logic(context: ContextTypes.DEFAULT_TYPE, chat_id: int, niche: str) -> None:
    """Core logic for T2 analysis."""
    csv_filename = f"sourcing_yt_{niche}.csv"
    
    if not os.path.exists(csv_filename):
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Fichier {csv_filename} introuvable. Lancez /yt_t1 d'abord.")
        return
        
    await context.bot.send_message(chat_id=chat_id, text=f"🔍 Lancement de l'analyse T2 (Vélocité) pour '{niche}'...")
    
    try:
        # 1. Lire T1
        data_t1 = []
        with open(csv_filename, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                data_t1.append(row)
                
        if not data_t1:
            await context.bot.send_message(chat_id=chat_id, text="❌ Le fichier CSV est vide.")
            return
            
        t1_timestamp = float(data_t1[0].get('t1_timestamp', time.time() - 10800))
        delta_t_hours = (time.time() - t1_timestamp) / 3600.0
        if delta_t_hours <= 0:
            delta_t_hours = 0.01
            
        # 2. Récupérer T2
        video_ids = [item['id'] for item in data_t1]
        data_t2 = await asyncio.to_thread(get_youtube_stats, video_ids)
        
        # 3. Analyser
        top_trends = get_top_trends(data_t1, data_t2, delta_t_hours=delta_t_hours)
        
        if not top_trends:
            await context.bot.send_message(chat_id=chat_id, text="❌ Aucune vidéo n'a passé les critères stricts de vélocité.")
            return
            
        trends_to_process = top_trends[:10]
            
        msg = f"🏆 Analyse T2 terminée ! (Delta: {delta_t_hours:.2f}h)\n\n"
        msg += f"🔥 {len(trends_to_process)} vidéos ont explosé les compteurs :\n\n"
        for i, t in enumerate(trends_to_process):
            msg += f"Top {i+1}: {t['title'][:20]}...\n"
            msg += f"Vues: {t['views_t1']} -> {t['views_t2']} (+{t['delta_v']})\n"
            msg += f"Vélocité horaire: {t['v_h']:.0f} vues/h\n"
            msg += f"Croissance relative: {t['c_r']:.1f}%\n"
            msg += f"Score Pondéré: {t['score']:.1f}\n\n"
            
        await context.bot.send_message(chat_id=chat_id, text=msg)
        await context.bot.send_message(chat_id=chat_id, text=f"📥 Lancement du téléchargement et FFmpeg pour {len(trends_to_process)} vidéos...")
        
        # 4. Traitement Vidéo
        output_dir = "downloads"
        for i, trend in enumerate(trends_to_process):
            vid_url = trend['url']
            try:
                await context.bot.send_message(chat_id=chat_id, text=f"⏳ Téléchargement du Top {i+1}...")
                input_video = await asyncio.to_thread(download_video, vid_url, output_dir)
                
                if not input_video:
                    await context.bot.send_message(chat_id=chat_id, text=f"❌ Échec du téléchargement yt-dlp pour le Top {i+1} ({vid_url}).")
                    continue
                
                output_video = os.path.join(output_dir, f"processed_top{i+1}_{trend['id']}.mp4")
                
                progress_msg = await context.bot.send_message(chat_id=chat_id, text=f"🎨 Traitement FFmpeg du Top {i+1}... [░░░░░░░░░░] 0%")
                last_sent_text = [f"🎨 Traitement FFmpeg du Top {i+1}... [░░░░░░░░░░] 0%"]
                
                async def update_progress(percent: int):
                    bar_length = 10
                    filled = int(percent / 10)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    text = f"🎨 Traitement FFmpeg du Top {i+1}... [{bar}] {percent}%"
                    if last_sent_text[0] != text:
                        try:
                            await progress_msg.edit_text(text)
                            last_sent_text[0] = text
                        except Exception:
                            pass
                
                success = await process_video(input_video, output_video, update_progress)
                
                if success and os.path.exists(output_video):
                    print(f"🔧 [DEBUG] Envoi de la vidéo traitée vers Telegram...")
                    
                    try:
                        probe = await asyncio.to_thread(ffmpeg.probe, output_video)
                        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                        if video_stream:
                            res_w = video_stream['width']
                            res_h = video_stream['height']
                            await context.bot.send_message(chat_id=chat_id, text=f"✅ Résolution finale générée : {res_w}x{res_h} (9:16)")
                    except Exception as e:
                        pass
                        
                    with open(output_video, 'rb') as video_file:
                        desc = trend.get('description', '')
                        if len(desc) > 700:
                            desc = desc[:700] + "..."
                        
                        final_caption = f"🎬 Voici ton Top {i+1} ({trend['c_r']:.1f}% croissance)\n\n📝 Description originale:\n{desc}"
                        
                        await context.bot.send_video(
                            chat_id=chat_id, 
                            video=video_file, 
                            caption=final_caption,
                            read_timeout=120,
                            write_timeout=120,
                            connect_timeout=120
                        )
                    print(f"🔧 [DEBUG] Vidéo envoyée avec succès.")
                else:
                    print(f"🔧 [DEBUG] Echec success={success} ou fichier non existant.")
                    await context.bot.send_message(chat_id=chat_id, text=f"❌ Echec du traitement FFmpeg pour le Top {i+1}.")
                    
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Erreur vidéo Top {i+1}: {e}")

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Erreur critique lors de T2 : {e}")

async def auto_t2_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for the JobQueue to run T2 automatically after 3 hours."""
    job = context.job
    chat_id = job.data['chat_id']
    niche = job.data['niche']
    
    # Si le fichier CSV n'existe plus (ex: supprimé via /clear), on annule silencieusement
    csv_filename = f"sourcing_yt_{niche}.csv"
    if not os.path.exists(csv_filename):
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Valider (Lancer T2)", callback_data=f"t2_yes|{niche}"),
            InlineKeyboardButton("❌ Non (Annuler)", callback_data=f"t2_no|{niche}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"⏰ 3 heures se sont écoulées pour '{niche}' !\nLe T2 est prêt. Veux-tu lancer l'analyse et télécharger les vidéos maintenant ?",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline button clicks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = query.message.chat_id
    
    if data.startswith("t2_yes|"):
        niche = data.split("|")[1]
        await query.edit_message_text(text=f"✅ Lancement T2 confirmé pour '{niche}'.")
        await execute_t2_logic(context, chat_id, niche)
        
    elif data.startswith("t2_no|"):
        niche = data.split("|")[1]
        await query.edit_message_text(text=f"❌ Analyse annulée pour '{niche}'. Le fichier de suivi a été supprimé.")
        file = f"sourcing_yt_{niche}.csv"
        if os.path.exists(file):
            try:
                os.remove(file)
            except Exception:
                pass

async def yt_t2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manual command to run T2."""
    args = context.args
    niche = args[0] if args else "général"
    await execute_t2_logic(context, update.effective_chat.id, niche)

def main() -> None:
    """Run the bot."""
    if TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("⚠️ Attention: Token Telegram non configuré (utilisez TELEGRAM_BOT_TOKEN).")
        
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("yt_t1", yt_t1))
    application.add_handler(CommandHandler("yt_t2", yt_t2))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("🤖 Bot démarré. En attente de messages...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
