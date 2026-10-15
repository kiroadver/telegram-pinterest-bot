# Bot Telegram Pencari Foto Pinterest (Tanpa API)

Bot Telegram untuk mencari foto di Pinterest dan mengirim **maksimal 5 foto**
langsung ke chat — **tanpa API resmi Pinterest** (menggunakan teknik
web scraping pada halaman pencarian Pinterest).

## Fitur

- 🔎 Cari foto Pinterest berdasarkan kata kunci
- 📸 Kirim hasil sebagai album berisi maksimal 5 foto
- 📝 Caption berisi judul pin + keyword
- 🔁 Bisa lewat perintah `/pinterest <kata kunci>` atau langsung kirim teks
- 🚫 Tidak butuh API key Pinterest, login, maupun kartu kredit

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
| Langsung ketik `wallpaper aesthetic` | Sama, tanpa perlu perintah |

## Cara kerja (singkat)

1. Bot membuka halaman `id.pinterest.com/search/pins/?q=...` untuk mengambil
   cookie `csrftoken` dan `appVersion`.
2. Bot memanggil endpoint pencarian internal Pinterest
   (`/resource/BaseSearchResource/get/`) yang juga dipakai situs Pinterest
   sendiri, sehingga hasilnya berupa JSON berisi URL gambar.
3. Bot memilih sampai 5 gambar (ukuran `736x`, cukup tajam namun ringan)
   lalu mengirimkannya via `send_media_group` (album) atau `send_photo`
   bila hanya 1 hasil.

## Catatan penting

- Karena ini **bukan API resmi**, Pinterest bisa mengubah strukturnya
  sewaktu-waktu. Jika bot tiba-tiba error, besar kemungkinan endpoint/
  header perlu disesuaikan lagi.
- Jangan melakukan pencarian terlalu cepat berturut-turut (spam) agar
  tidak kena rate limit dari Pinterest.
- Foto hasil pencarian tetap milik pemilik aslinya — gunakan secara wajar.
