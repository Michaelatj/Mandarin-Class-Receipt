# Update v6 (menggantikan v5; cukup extract v6) - dibuat dari main.zip terbarumu

Extract ke root project (folder yang berisi `app/`), pilih Merge + Replace. Tidak ada library baru.
Hanya file di zip ini yang berubah; semuanya diturunkan dari main.zip yang kamu kirim, jadi navbar Profile + badge tetap ada.

## Baru di v6
- Menu Profile (badge) sekarang tetap ada di sidebar/bottom nav saat murid membuka halaman Quiz atau HSK, dan mengarah ke tab Profile.
- Guru: di daftar Students, klik nama murid atau "Badge & streak" untuk kartu besar: badge (bisa di-tap, ada efeknya), current/best streak, attended, persen hadir, progres ke badge berikutnya, dan semua tier.
- File baru: static/js/student-badge.js. Perubahan: teacher.py, teacher/dashboard.html, main.css, quiz_shell_nav.html.

## Isi v5
1. HSK 1, 2, 3 (HSK 3 = 500 kata, 13 tema), UI English. Menu HSK ada di sidebar + bottom nav (murid & guru).
2. Murid tidak bisa lagi submit attendance manual:
   - form "Select Your Teacher / Submit Attendance" dihapus dari tab Classes
   - route /mark_attendance sekarang menjawab 410 (aman untuk halaman lama yang ter-cache)
   - hadir hanya tercatat lewat Join Meeting (online) atau tombol hadir / kode di kelas offline
   - attendance lama dengan source 'student' tidak lagi dihitung untuk streak
3. Streak aman saat jadwal dihapus:
   - sebelum hapus, riwayat disimpan; kalau gagal menyimpan, kelas TIDAK dihapus (dulu error ini diam-diam)
4. migrate_streak_recover.py: memulihkan streak dari kelas yang dihapus SEBELUM tabel riwayat ada.
   Preview:  python migrate_streak_recover.py
   Tulis:    python migrate_streak_recover.py --apply
   Untuk database live set DATABASE_URL (sama dengan di Vercel) lebih dulu.

Setelah deploy: hard-refresh (Ctrl+Shift+R).
