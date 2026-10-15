"""
Bot Telegram Pencari Foto Pinterest (TANPA API resmi Pinterest)
================================================================
Cara kerja: bot melakukan web scraping ke halaman pencarian Pinterest
memakai endpoint internal Pinterest (resource BaseSearchResource),
jadi tidak perlu mendaftar / membayar API key Pinterest.

Perintah bot:
  /start  atau /help   -> panduan
  /pinterest <kata>    -> kirim maksimal 5 foto hasil pencarian
  (atau langsung kirim teks apa saja)

Cara jalankan:
  1. pip install -r requirements.txt
  2. Isi BOT_TOKEN (lihat di bawah) atau set environment variable BOT_TOKEN
  3. python pinterest_bot.py
"""

import os
import re
import json
import time
import urllib.parse

import requests
import telebot
from telebot.types import InputMediaPhoto

# ============================ KONFIGURASI ============================
# Ganti dengan token dari @BotFather, atau set env var BOT_TOKEN
BOT_TOKEN = os.getenv("BOT_TOKEN", "ISI_TOKEN_BOT_KAMU_DI_SINI")

MAX_FOTO = 5                     # maksimal foto yang dikirim
BASE = "https://id.pinterest.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
# =====================================================================

bot = telebot.TeleBot(BOT_TOKEN)


def cari_foto_pinterest(query: str, limit: int = MAX_FOTO) -> list:
    """
    Scrape hasil pencarian Pinterest.
    Return: list of dict {"url": ..., "judul": ..., "link": ...}
    """
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    })

    source_url = f"/search/pins/?q={urllib.parse.quote(query)}"

    # Langkah 1: buka halaman pencarian -> dapat cookie csrftoken + appVersion
    html = s.get(BASE + source_url, timeout=20).text
    csrf = s.cookies.get("csrftoken", "")
    m = re.search(r'"appVersion":\s*"([^"]+)"', html)
    appver = m.group(1) if m else ""

    # Langkah 2: panggil endpoint pencarian internal Pinterest (JSON)
    data = {
        "options": {
            "query": query,
            "scope": "pins",
            "no_fetch_context_on_resource": False,
        },
        "context": {},
    }
    s.headers.update({
        "Accept": "application/json, text/javascript, */*, q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrf,
        "X-Pinterest-AppState": "active",
        "X-Pinterest-AppVersion": appver,
        "X-Pinterest-PWS-Handler": "www/search/[typeahead].js",
        "X-Pinterest-Source-Url": source_url,
        "Referer": BASE + source_url,
    })
    resp = s.get(
        BASE + "/resource/BaseSearchResource/get/",
        params={
            "source_url": source_url,
            "data": json.dumps(data, separators=(",", ":")),
            "_": str(int(time.time() * 1000)),
        },
        timeout=20,
    )
    resp.raise_for_status()
    hasil = resp.json()["resource_response"]["data"]["results"]

    foto = []
    for it in hasil:
        images = it.get("images") or {}
        # Prioritas ukuran: 736x (cukup tajam, tidak terlalu besar),
        # lalu 474x, terakhir resolusi asli (orig).
        gambar = None
        for kunci in ("736x", "474x", "orig"):
            if kunci in images and images[kunci].get("url"):
                gambar = images[kunci]["url"]
                break
        if not gambar:
            continue

        judul = (it.get("title") or it.get("grid_title")
                 or it.get("seo_description") or "").strip()
        link = f"https://www.pinterest.com/pin/{it.get('id')}/"
        foto.append({"url": gambar, "judul": judul, "link": link})
        if len(foto) >= limit:
            break

    return foto


def kirim_hasil(message, query: str):
    """Cari foto lalu kirim ke pengguna sebagai album (maks 5)."""
    tunggu = bot.reply_to(message, f"🔎 Mencari foto: <b>{query}</b> ...",
                          parse_mode="HTML")

    try:
        foto = cari_foto_pinterest(query)
    except Exception as e:
        bot.edit_message_text(
            f"❌ Gagal mengambil data dari Pinterest.\nDetail: {e}",
            tunggu.chat.id, tunggu.message_id)
        return

    if not foto:
        bot.edit_message_text(
            "😕 Tidak ada foto ditemukan. Coba kata kunci lain.",
            tunggu.chat.id, tunggu.message_id)
        return

    bot.delete_message(tunggu.chat.id, tunggu.message_id)

    try:
        if len(foto) == 1:
            # 1 foto -> kirim biasa (album butuh minimal 2 item)
            f = foto[0]
            bot.send_photo(
                message.chat.id, f["url"],
                caption=(f"🔍 <b>{query}</b>\n📝 {f['judul']}\n"
                         f"🔗 <a href='{f['link']}'>Lihat di Pinterest</a>"),
                parse_mode="HTML")
        else:
            # 2-5 foto -> kirim sebagai album
            album = []
            for i, f in enumerate(foto):
                caption = None
                if i == 0:
                    caption = f"🔍 Hasil pencarian: <b>{query}</b>"
                if f["judul"]:
                    caption = ((caption + "\n📝 " + f["judul"]) if caption
                               else f["judul"])[:1024]
                album.append(InputMediaPhoto(f["url"], caption=caption,
                                             parse_mode="HTML"))
            bot.send_media_group(message.chat.id, album)
    except Exception as e:
        # Cadangan: kirim link saja bila Telegram gagal memuat gambar
        teks = f"🔍 Hasil pencarian: <b>{query}</b>\n\n"
        for i, f in enumerate(foto, 1):
            teks += f"{i}. <a href='{f['url']}'>Foto {i}</a>\n"
        teks += "\n<i>(Gambar tidak bisa dimuat, silakan buka link)</i>"
        bot.send_message(message.chat.id, teks, parse_mode="HTML",
                         disable_web_page_preview=True)


# ============================ HANDLER BOT ============================

@bot.message_handler(commands=["start", "help"])
def help_handler(message):
    bot.reply_to(
        message,
        "👋 Halo! Aku bot pencari foto <b>Pinterest</b>.\n\n"
        "Cara pakai:\n"
        "• Ketik <code>/pinterest judul pencarian</code>\n"
        "• Contoh: <code>/pinterest kucing lucu</code>\n"
        "• Atau langsung kirim teks kata kuncinya saja\n\n"
        f"Aku akan mengirim maksimal {MAX_FOTO} foto. 📸",
        parse_mode="HTML")


@bot.message_handler(commands=["pinterest", "cari"])
def pinterest_handler(message):
    # Ambil kata kunci setelah perintah
    parts = message.text.split(maxsplit=1)
    query = parts[1].strip() if len(parts) > 1 else ""
    if not query:
        bot.reply_to(
            message,
            "⚠️ Tulis kata kuncinya ya.\n"
            "Contoh: <code>/pinterest wallpaper aesthetic</code>",
            parse_mode="HTML")
        return
    kirim_hasil(message, query)


@bot.message_handler(func=lambda m: bool(m.text) and not m.text.startswith("/"))
def teks_handler(message):
    # Teks biasa langsung dianggap sebagai kata kunci pencarian
    kirim_hasil(message, message.text.strip())


# ============================ JALANKAN BOT ============================

if __name__ == "__main__":
    if BOT_TOKEN.startswith("ISI_TOKEN"):
        raise SystemExit(
            "❗ BOT_TOKEN belum diisi.\n"
            "   Edit file ini atau jalankan dengan:\n"
            "   Linux/Mac : BOT_TOKEN=1234:abcd python pinterest_bot.py\n"
            "   Windows   : set BOT_TOKEN=1234:abcd && python pinterest_bot.py")

    print("✅ Bot Pinterest berjalan... (Ctrl+C untuk berhenti)")
    bot.infinity_polling(skip_pending=True, timeout=20)
