# Memasang halaman HSK 1 + HSK 2

Zip ini menggantikan paket HSK 1 sebelumnya. Aman dipasang di atas project, baik yang sudah memasang paket lama maupun belum.

1. Extract zip ini langsung ke root project (folder yang berisi `app/`). Pilih "Merge/Gabungkan folder" dan "Replace" file yang sama.
2. Tidak ada migrasi database dan tidak ada library baru. Jalankan seperti biasa.
3. Buka `/hsk1/` atau `/hsk2/`. Menu "HSK" muncul di sidebar guru dan murid.
4. Kalau di-deploy (Vercel dll), commit dan push file barunya.

File baru: app/routes/hsk.py, app/data/hsk1.json, app/data/hsk2.json, app/templates/hsk/{index,theme,locked}.html, app/static/js/hsk.js, app/static/css/hsk.css
File lama yang diubah sedikit: app/__init__.py (daftarkan blueprint), app/services/i18n.py (label menu "HSK"), app/templates/partials/quiz_shell_nav.html, app/templates/student/dashboard.html, app/templates/teacher/dashboard.html (tautan menu)

Akses: harus login. Guru selalu boleh. Murid boleh jika sudah terdaftar di kelas (guru sudah mengatur fee, atau ada absensi, kwitansi, atau undangan jadwal).
Tanda "hafal" tersimpan di browser tiap murid (per level), bukan di database.
Perubahan dari paket pertama: halaman HSK 2, pilihan level HSK 1/HSK 2, dan tombol "Kembali" di halaman tema kini benar-benar kembali ke daftar tema (sebelumnya ke dashboard).
