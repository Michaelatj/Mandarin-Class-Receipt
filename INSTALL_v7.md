# Update v7 (menggantikan v5 dan v6; cukup extract yang ini) - dibuat dari main.zip terbarumu

Extract ke root project (folder yang berisi `app/`), Merge + Replace. Tidak ada library baru.
Tabel baru `bonus_access` dibuat otomatis saat app start (sama seperti streak_entry), tanpa migrasi manual.

## Yang baru di v7
1. Menu "HSK" diganti jadi "Bonus Courses" (ikon 🎁) di semua menu.
2. Guru bisa membuka kunci HSK 1 / 2 / 3 per murid:
   Dashboard guru -> Students -> "Bonus Courses access". Toggle per murid per level, dan tombol All / None per level.
   PENTING: semua level TERKUNCI sampai kamu buka. Murid lama tidak otomatis punya akses; klik "All" di HSK yang diinginkan kalau mau membuka untuk semua.
   Guru selalu bisa membuka semua level. Level yang terkunci: halaman kunci (403) dan data.json juga ditolak.
3. Halaman awal Bonus Courses (/bonus/): kartu HSK 1, 2, 3; yang belum dibuka tampil terkunci.
4. Menu burger di kiri atas (HP dan komputer): menu muncul sebagai drawer dari kiri. Bottom bar tidak dipakai lagi.
   Titik merah di burger muncul kalau ada notifikasi di menu. Tutup dengan tombol X, klik di luar, Esc, atau pilih menu.
   File: static/js/nav-drawer.js (dipasang dari base.html), CSS di akhir main.css.

## Sebelumnya (v5/v6)
- HSK 1-3 (HSK 3 = 500 kata), UI English, Profile di menu Quiz/Bonus Courses, kartu badge besar untuk guru,
  murid tidak bisa submit attendance manual, riwayat streak aman saat jadwal dihapus,
  migrate_streak_recover.py (jalankan tanpa --apply dulu untuk preview).

Setelah deploy: hard-refresh (Ctrl+Shift+R).
