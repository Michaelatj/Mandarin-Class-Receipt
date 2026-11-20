# Update v13 (menggantikan v5–v12; cukup pasang yang ini di atas main)
Ekstrak ke folder project (timpa), restart app. Tabel baru (quiz_story, hsk_known, hsk_activity) dibuat otomatis saat start.

## Baru di v13 (di atas v11)
- Progres Bonus Courses: tanda "mastered" murid kini tersimpan di server (ikut pindah HP). Guru melihat di kartu Students > Badge & streak: HSK 1/2/3, jumlah kata dikuasai, jumlah kartu dijawab, dan tanggal terakhir latihan.
- Soal "Listen and choose": perangkat membacakan kata/kalimat, murid memilih. Dibuat lewat New quiz (jenis soal "Listen and choose"), atau isi kolom Audio di halaman Edit questions.
- Guru: tombol "Preview badges" di halaman Students untuk memutar semua badge dan animasinya (pop-up streak dan "new badge").
- Absen offline ("Sudah hadir" dan kode roll call) kini juga memunculkan pop-up streak dan animasi naik badge.

## Baru di v13 (di atas v12)
- Setelah murid menyelesaikan kuis (akurasi 60% ke atas), layar hasil memutar perayaan sesuai badge mereka: Bronze kecil sampai Dragon heboh. Akurasi 90%+ memakai versi lebih besar. Fungsi `StreakOverlay.burst(tier, big)` bisa dipakai game Bonus Courses nanti.
