# Bot Telegram: Foto Pinterest + Lagu YouTube (MP3)

Bot Telegram serbaguna:
1. **Cari foto Pinterest** — mengirim **maksimal 5 foto** ke chat,
   **tanpa API resmi Pinterest** (memakai teknik web scraping).
2. **Cari & download lagu dari YouTube** — tampilkan 5 hasil pencarian,
   user pilih lewat tombol, lagu dikirim sebagai **MP3**.

## Fitur

- 🔎 Cari foto Pinterest berdasarkan kata kunci
- 📸 Kirim hasil sebagai album berisi maksimal 5 foto
- 🎵 Cari lagu YouTube: `/lagu <judul>` → 5 hasil dengan tombol pilihan
- ⬇️ Download lagu → convert otomatis ke **MP3 192kbps** lalu kirim
- ⏱ Lagu di atas 10 menit otomatis difilter (hindari kompilasi/playlist)
- 🔁 Bisa lewat perintah atau langsung kirim teks (default = Pinterest)
- 🚫 Tidak butuh API key Pinterest/YouTube, login, maupun kartu kredit
- 🤖 Siap deploy Railway (facilities ffmpeg + deno via `nixpacks.toml`)

## 1. Buat bot di Telegram

1. Buka Telegram, chat ke **@BotFather**
2. Kirim perintah `/newbot`
3. Ikuti petunjuk (nama bot, username bot)
4. Salin **token** yang diberikan, misalnya:
   `123456789:AAExampleTokenDariBotFather`

## 2. Instalasi

Syarat: Python 3.8 ke atas.

```bash
pip install -r requirements.txt
```

## 3. Isi token bot

Pilih salah satu cara:

**Cara A — edit file**

Buka `pinterest_bot.py`, ganti isi variabel:

```python
BOT_TOKEN = os.getenv("BOT_TOKEN", "123456789:AAExampleTokenDariBotFather")
```

**Cara B — environment variable (lebih aman)**

Linux / Mac:

```bash
export BOT_TOKEN="123456789:AAExampleTokenDariBotFather"
```

Windows (CMD):

```cmd
set BOT_TOKEN=123456789:AAExampleTokenDariBotFather
```

Windows (PowerShell):

```powershell
$env:BOT_TOKEN="123456789:AAExampleTokenDariBotFather"
```

## 4. Jalankan bot

```bash
python pinterest_bot.py
```

Jika muncul `✅ Bot Pinterest berjalan...`, buka Telegram dan chat bot kamu.

## 5. Cara pakai di Telegram

| Perintah | Keterangan |
|---|---|
| `/start` atau `/help` | Panduan singkat |
| `/pinterest kucing lucu` | Cari foto "kucing lucu", kirim maks 5 foto |
| `/lagu sepuluh ribu` | Cari lagu di YouTube, pilih 1 dari 5 hasil, kirim MP3 |
| Langsung ketik `wallpaper aesthetic` | Sama seperti `/pinterest` |

## Catatan penting

- **ffmpeg**: dibutuhkan untuk konversi MP3. Di Railway sudah otomatis
  terinstall via `nixpacks.toml`. Untuk jalan di komputer sendiri,
  cukup `pip install imageio-ffmpeg` (sudah ada di requirements) —
  atau install ffmpeg ke PATH secara manual.
- Karena ini **bukan API resmi**, Pinterest/YouTube bisa mengubah strukturnya
  sewaktu-waktu. Jika bot tiba-tiba error, besar kemungkinan endpoint/
  header perlu disesuaikan lagi.
- Jangan melakukan pencarian terlalu cepat berturut-turut (spam) agar
  tidak kena rate limit.
- Foto & lagu hasil pencarian tetap milik pemilik aslinya. Download lagu
  dari YouTube hanya untuk keperluan pribadi — patuhi ketentuan YouTube
  dan hukum hak cipta yang berlaku.

## Deploy ke Railway (bot online 24 jam)

Bot ini sudah siap deploy ke [Railway](https://railway.com) — file
`Procfile`, `railway.json`, dan `.python-version` sudah disertakan di repo.

1. Buka https://railway.com → login pakai akun **GitHub** kamu.
2. Klik **New Project** → **Deploy from GitHub repo**.
3. Pilih repo **`kiroadver/telegram-pinterest-bot`**
   (beri izin akses repo ke Railway jika diminta).
4. Buka service yang terbuat → tab **Variables** → tambahkan:
   - `BOT_TOKEN` = token bot dari @BotFather
5. Railway akan rebuild & restart otomatis.
6. Buka tab **Deployments** → **View Logs**, pastikan muncul
   `✅ Bot Pinterest berjalan...`
7. Tes kirim pesan ke bot di Telegram. 🎉

**Catatan Railway:**

- Bot ini *polling* (bukan web server), jadi **tidak perlu**
  public domain / port.
- Railway adalah layanan berbayar — akun baru biasanya dapat kredit
  trial. Cek harga terbaru di https://railway.com/pricing
- Kalau ada perubahan file di GitHub, cukup push → Railway redeploy
  otomatis.

## Cara kerja (singkat)

1. Bot membuka halaman `id.pinterest.com/search/pins/?q=...` untuk mengambil
   cookie `csrftoken` dan `appVersion`.
2. Bot memanggil endpoint pencarian internal Pinterest
   (`/resource/BaseSearchResource/get/`) yang juga dipakai situs Pinterest
   sendiri, sehingga hasilnya berupa JSON berisi URL gambar.
3. Bot memilih sampai 5 gambar (ukuran `736x`, cukup tajam namun ringan)
   lalu mengirimkannya via `send_media_group` (album) atau `send_photo`
   bila hanya 1 hasil.
4. Untuk lagu, bot memakai `yt-dlp` mencari 5 video YouTube, mengambil
   audio terbaik (`bestaudio`), lalu mengonversinya ke MP3 memakai
   `ffmpeg` sebelum dikirim via `send_audio`.
