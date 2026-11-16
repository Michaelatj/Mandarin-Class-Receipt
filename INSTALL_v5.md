# Update v5 - dibuat dari main.zip terbarumu (aman ditimpa)

Extract ke root project (folder yang berisi `app/`), pilih Merge + Replace. Tidak ada library baru.
Hanya file di zip ini yang berubah; semuanya diturunkan dari main.zip yang kamu kirim, jadi navbar Profile + badge tetap ada.

## Isi
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
