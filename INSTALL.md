# Memasang halaman HSK 1

1. Salin isi folder ini ke root project (timpa file yang sama). 7 file baru, 5 file lama diubah sedikit:
   - Baru: app/routes/hsk.py, app/data/hsk1.json, app/templates/hsk/{index,theme,locked}.html, app/static/js/hsk.js, app/static/css/hsk.css
   - Diubah: app/__init__.py (daftarkan blueprint), app/services/i18n.py (label menu "HSK 1"), app/templates/partials/quiz_shell_nav.html, app/templates/student/dashboard.html, app/templates/teacher/dashboard.html (tautan menu)
2. Tidak ada migrasi database dan tidak ada library baru.
3. Jalankan seperti biasa, lalu buka /hsk1/.

Akses: harus login. Guru selalu boleh. Murid boleh jika sudah terdaftar di kelas (guru sudah mengatur fee, atau ada absensi, kwitansi, atau undangan jadwal). Akun yang baru daftar dan belum terhubung ke kelas melihat halaman "minta gurumu menambahkanmu".
Tanda "hafal" tersimpan di browser tiap murid (localStorage), bukan di database.
