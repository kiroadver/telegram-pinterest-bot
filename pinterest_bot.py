"""
Bot Telegram: Pencari Foto Pinterest + Download Lagu YouTube (MP3)
==================================================================
- 🔎  Cari foto Pinterest  : /pinterest <kata kunci>  (maks 5 foto, tanpa API)
- 🎵  Cari & unduh lagu    : /lagu <judul lagu>       (dari YouTube, hasil MP3)

Cara jalankan:
  1. pip install -r requirements.txt
  2. Isi BOT_TOKEN (lihat di bawah) atau set environment variable BOT_TOKEN
  3. python pinterest_bot.py
"""

import os
import re
import json
import time
import shutil
import tempfile
import html
import urllib.parse

import requests
import telebot
import yt_dlp
from telebot.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

# ============================ KONFIGURASI ============================
# Ganti dengan token dari @BotFather, atau set env var BOT_TOKEN
BOT_TOKEN = os.getenv("BOT_TOKEN", "ISI_TOKEN_BOT_KAMU_DI_SINI")

MAX_FOTO = 5              # maksimal foto Pinterest yang dikirim
MAX_DURASI_LAGU = 600     # lagu maks 10 menit (600 detik)
MAX_UKURAN_FILE = 49 * 1024 * 1024  # batas kirim file bot Telegram ~50MB
BASE = "https://id.pinterest.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
# =====================================================================

bot = telebot.TeleBot(BOT_TOKEN)


# ======================== PINTEREST ========================

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
    html_page = s.get(BASE + source_url, timeout=20).text
    csrf = s.cookies.get("csrftoken", "")
    m = re.search(r'"appVersion":\s*"([^"]+)"', html_page)
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


def kirim_hasil_pinterest(message, query: str):
    """Cari foto lalu kirim ke pengguna sebagai album (maks 5)."""
    tunggu = bot.reply_to(message, f"🔎 Mencari foto: <b>{html.escape(query)}</b> ...",
                          parse_mode="HTML")

    try:
        foto = cari_foto_pinterest(query)
    except Exception as e:
        bot.edit_message_text(
            f"❌ Gagal mengambil data dari Pinterest.\nDetail: {html.escape(str(e)[:200])}",
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
                caption=(f"🔍 <b>{html.escape(query)}</b>\n📝 {html.escape(f['judul'])}\n"
                         f"🔗 <a href='{f['link']}'>Lihat di Pinterest</a>"),
                parse_mode="HTML")
        else:
            # 2-5 foto -> kirim sebagai album
            album = []
            for i, f in enumerate(foto):
                caption = None
                if i == 0:
                    caption = f"🔍 Hasil pencarian: <b>{html.escape(query)}</b>"
                if f["judul"]:
                    caption = ((caption + "\n📝 " + html.escape(f["judul"])) if caption
                               else html.escape(f["judul"]))[:1024]
                album.append(InputMediaPhoto(f["url"], caption=caption,
                                             parse_mode="HTML"))
            bot.send_media_group(message.chat.id, album)
    except Exception:
        # Cadangan: kirim link saja bila Telegram gagal memuat gambar
        teks = f"🔍 Hasil pencarian: <b>{html.escape(query)}</b>\n\n"
        for i, f in enumerate(foto, 1):
            teks += f"{i}. <a href='{f['url']}'>Foto {i}</a>\n"
        teks += "\n<i>(Gambar tidak bisa dimuat, silakan buka link)</i>"
        bot.send_message(message.chat.id, teks, parse_mode="HTML",
                         disable_web_page_preview=True)


# ======================== YOUTUBE -> MP3 ========================

def _ffmpeg_dir() -> str | None:
    """
    Cari ffmpeg untuk konversi ke MP3:
    1. ffmpeg di PATH (Railway/nixpacks atau komputer yang sudah install)
    2. binary statis dari paket pip imageio-ffmpeg (fallback)
    """
    p = shutil.which("ffmpeg")
    if p:
        return os.path.dirname(p)
    try:
        import imageio_ffmpeg
        bin_path = imageio_ffmpeg.get_ffmpeg_exe()
        d = os.path.join(tempfile.gettempdir(), "bot_ffmpeg")
        os.makedirs(d, exist_ok=True)
        link = os.path.join(d, "ffmpeg")
        if not os.path.exists(link):
            os.symlink(bin_path, link)
        return d
    except Exception:
        return None


def cari_lagu_youtube(query: str, limit: int = 5) -> list:
    """
    Cari lagu di YouTube. Hanya ambil video dengan durasi <= MAX_DURASI_LAGU.
    Return: list of dict {"id", "title", "duration", "uploader"}
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        data = ydl.extract_info(f"ytsearch{limit + 3}:{query}", download=False)

    hasil = []
    for e in data.get("entries") or []:
        if not e:
            continue
        dur = e.get("duration") or 0
        if dur > MAX_DURASI_LAGU:
            continue  # terlalu panjang untuk dikirim sebagai lagu
        hasil.append({
            "id": e["id"],
            "title": e.get("title") or "Tanpa judul",
            "duration": dur,
            "uploader": e.get("uploader") or e.get("channel") or "-",
        })
        if len(hasil) >= limit:
            break
    return hasil


# Urutan player client untuk menghindari blokir YouTube (403/sign-in)
# terutama dari IP server/datacenter — dicoba satu per satu sampai berhasil.
_YT_CLIENT_FALLBACK = [
    ["android", "mweb"],
    ["tv_embedded", "tv"],
    ["ios"],
    ["web", "mweb"],
]


def download_mp3(video_id: str):
    """
    Download audio YouTube lalu konversi ke MP3.
    Return: (path_mp3, info, tmpdir) — tmpdir harus dibersihkan pemanggil.
    """
    tmpdir = tempfile.mkdtemp(prefix="ytmp3_")
    path = os.path.join(tmpdir, f"{video_id}.mp3")
    base_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(tmpdir, f"{video_id}.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ffmpeg_location": _ffmpeg_dir(),
        "retries": 3,
        "fragment_retries": 3,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    last_err = None
    for clients in _YT_CLIENT_FALLBACK:
        opts = dict(base_opts)
        opts["extractor_args"] = {"youtube": {"player_client": clients}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://youtu.be/{video_id}",
                                        download=True)
            if os.path.exists(path):
                return path, info, tmpdir
        except Exception as e:
            last_err = e
            continue

    raise ValueError(
        f"YouTube menolak permintaan download. {str(last_err)[:150]}")


def kirim_hasil_lagu(message, query: str):
    """Cari lagu di YouTube, tampilkan 5 hasil + tombol pilihan."""
    tunggu = bot.reply_to(
        message,
        f"🔎 Mencari lagu: <b>{html.escape(query)}</b> di YouTube...",
        parse_mode="HTML")

    try:
        hasil = cari_lagu_youtube(query)
    except Exception as e:
        bot.edit_message_text(
            f"❌ Gagal mencari lagu di YouTube.\nDetail: {html.escape(str(e)[:200])}",
            tunggu.chat.id, tunggu.message_id)
        return

    if not hasil:
        bot.edit_message_text(
            "😕 Lagu tidak ditemukan. Coba kata kunci lain.",
            tunggu.chat.id, tunggu.message_id)
        return

    teks = f"🎵 <b>Hasil pencarian: {html.escape(query)}</b>\n\n"
    tombol = []
    for i, lagu in enumerate(hasil, 1):
        dur = lagu["duration"]
        menit = f"{int(dur // 60)}:{int(dur % 60):02d}"
        teks += (f"{i}. <b>{html.escape(lagu['title'][:80])}</b>\n"
                 f"    🎤 {html.escape(lagu['uploader'][:40])} · ⏱ {menit}\n\n")
        tombol.append(InlineKeyboardButton(f"⬇️ {i}", callback_data=f"mp3:{lagu['id']}"))

    teks += "Klik nomor di bawah untuk download MP3 👇"
    kb = InlineKeyboardMarkup(row_width=5)
    kb.add(*tombol)
    bot.edit_message_text(teks, tunggu.chat.id, tunggu.message_id,
                          reply_markup=kb, parse_mode="HTML")


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("mp3:"))
def mp3_callback(call):
    """User memilih salah satu hasil pencarian lagu -> download & kirim MP3."""
    video_id = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id, "⏳ Sedang diproses...")
    bot.edit_message_text(
        "⏳ Sedang mendownload & convert ke MP3...\n"
        "(untuk lagu 3-4 menit biasanya 15-30 detik)",
        call.message.chat.id, call.message.message_id)

    tmpdir = None
    try:
        path, info, tmpdir = download_mp3(video_id)

        ukuran = os.path.getsize(path)
        if ukuran > MAX_UKURAN_FILE:
            raise ValueError("File terlalu besar (melebihi batas 50MB Telegram).")

        judul = info.get("title") or "lagu"
        artis = info.get("uploader") or info.get("channel") or None
        durasi = int(info.get("duration") or 0) or None

        with open(path, "rb") as f:
            bot.send_audio(
                call.message.chat.id, f,
                title=judul[:100],
                performer=(artis or "")[:100] or None,
                duration=durasi,
                caption=f"🎵 {html.escape(judul)}",
                parse_mode="HTML",
                timeout=180)

        bot.edit_message_text(
            f"✅ <b>Lagu terkirim!</b>\n🎵 {html.escape(judul[:80])}\n"
            f"🎤 {html.escape((artis or '-')[:60])}",
            call.message.chat.id, call.message.message_id,
            parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(
            f"❌ Gagal mendownload lagu.\n"
            f"Detail: {html.escape(str(e)[:250])}\n\nCoba pilih hasil lain / cari ulang.",
            call.message.chat.id, call.message.message_id)
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ============================ HANDLER BOT ============================

@bot.message_handler(commands=["start", "help"])
def help_handler(message):
    bot.reply_to(
        message,
        "👋 Halo! Aku bot serbaguna:\n\n"
        "🖼 <b>Cari foto Pinterest</b>\n"
        "• <code>/pinterest judul pencarian</code>\n"
        "• Contoh: <code>/pinterest kucing lucu</code>\n"
        f"• Dikirim sebagai album, maks {MAX_FOTO} foto\n\n"
        "🎵 <b>Cari & download lagu (MP3)</b>\n"
        "• <code>/lagu judul lagu</code>\n"
        "• Contoh: <code>/lagu sepuluh ribu</code>\n"
        "• Pilih dari 5 hasil, dikirim sebagai MP3\n\n"
        "💡 Teks biasa (tanpa /lagu atau /pinterest) dicari di Pinterest.",
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
    kirim_hasil_pinterest(message, query)


@bot.message_handler(commands=["lagu", "music", "ytmp3"])
def lagu_handler(message):
    parts = message.text.split(maxsplit=1)
    query = parts[1].strip() if len(parts) > 1 else ""
    if not query:
        bot.reply_to(
            message,
            "⚠️ Tulis judul lagunya ya.\n"
            "Contoh: <code>/lagu dirimu yang dulu</code>",
            parse_mode="HTML")
        return
    kirim_hasil_lagu(message, query)


@bot.message_handler(func=lambda m: bool(m.text) and not m.text.startswith("/"))
def teks_handler(message):
    # Teks biasa langsung dianggap sebagai kata kunci pencarian Pinterest
    kirim_hasil_pinterest(message, message.text.strip())


# ============================ JALANKAN BOT ============================

if __name__ == "__main__":
    if BOT_TOKEN.startswith("ISI_TOKEN"):
        raise SystemExit(
            "❗ BOT_TOKEN belum diisi.\n"
            "   Edit file ini atau jalankan dengan:\n"
            "   Linux/Mac : BOT_TOKEN=1234:abcd python pinterest_bot.py\n"
            "   Windows   : set BOT_TOKEN=1234:abcd && python pinterest_bot.py")

    print("✅ Bot berjalan... (Ctrl+C untuk berhenti)")
    bot.infinity_polling(skip_pending=True, timeout=20)
