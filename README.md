# Rapikan-Folder

Skrip PowerShell untuk merapikan isi sebuah folder (misalnya `Downloads`) ke subfolder per jenis file dan/atau per bulan.
Berjalan **offline**, tanpa instalasi tambahan, dan **tidak memakai AI**, sehingga hasilnya dapat diprediksi.

- **Simulasi dulu.** Secara bawaan skrip hanya menampilkan rencana. Tidak ada file yang dipindah sebelum Anda menambahkan `-Apply`.
- **Tidak menghapus file.** Hanya memindahkan. Nama kembar diberi akhiran ` (2)`, ` (3)`, dan seterusnya.
- **Bisa dibatalkan.** Setiap eksekusi menulis file log CSV, dan `-Undo` mengembalikan semuanya ke tempat asal.
- **Ada pengaman.** Menolak akar drive, `C:\Windows`, `Program Files`, `ProgramData`, dan folder profil utama.

## Persyaratan

- Windows 10/11 dengan Windows PowerShell 5.1 (sudah bawaan), atau PowerShell 7 di Windows/macOS/Linux.

## Cara pakai

1. Simpan `Rapikan-Folder.ps1` di sebuah folder, misalnya `C:\Rapikan\`.
2. Buka PowerShell di folder itu (tahan **Shift** + klik kanan di area kosong › *Open PowerShell window here*).
3. **Simulasi** (tidak memindahkan apa pun):

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Rapikan-Folder.ps1 -Path "C:\Users\NAMA\Downloads"
   ```

4. Jika daftar rencananya sudah benar, jalankan **sungguhan** dengan menambahkan `-Apply`:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Rapikan-Folder.ps1 -Path "C:\Users\NAMA\Downloads" -Apply
   ```

5. Untuk **membatalkan**, pakai perintah yang tercetak di akhir proses (berisi nama file log):

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Rapikan-Folder.ps1 -Undo "C:\Users\NAMA\Downloads\_RapikanLog_20261106-140000.csv"
   ```

> Disarankan mencoba pertama kali pada **salinan** folder, bukan folder asli.

## Memindahkan ke drive lain (kosongkan drive C)

Folder pribadi (Documents, Pictures, Videos, Music, Downloads) dipindah ke drive lain dan otomatis dikelompokkan per jenis:

```powershell
# simulasi dulu
powershell -ExecutionPolicy Bypass -File .\Rapikan-Folder.ps1 -Pribadi -Tujuan "D:\Arsip" -Recurse
# sungguhan
powershell -ExecutionPolicy Bypass -File .\Rapikan-Folder.ps1 -Pribadi -Tujuan "D:\Arsip" -Recurse -Apply
```

Hasil: `D:\Arsip\Gambar\foto.jpg`, `D:\Arsip\Dokumen\laporan.pdf`, dst. Log `-Undo` disimpan di folder tujuan. Skrip mengecek ruang kosong di drive tujuan, menolak `AppData` dan folder sistem, dan melewati file OneDrive yang hanya online. Struktur subfolder asal diratakan per jenis (bisa dikembalikan dengan `-Undo`). Untuk folder tertentu saja: `-Path "C:\Users\NAMA\Videos" -Tujuan "D:\Arsip"`.

## Rapikan-AI.ps1: agen AI lokal yang membaca isi dokumen

Beda dengan `Rapikan-Folder.ps1` (berdasarkan ekstensi), skrip ini **membaca isi** dokumen dengan model bahasa kecil yang berjalan di komputer Anda (Ollama), lalu memilahnya per topik: `Surat`, `SK dan Peraturan`, `Laporan`, `Undangan dan Acara`, `Keuangan dan Anggaran`, `Formulir dan Label`, `Daftar dan Rekap`, `Pribadi`, dan seterusnya (tiap kategori punya keterangan di dalam skrip). Gratis dan offline setelah model diunduh sekali.

**Persiapan (sekali saja):**

1. Pasang Ollama dari https://ollama.com/download.
2. Unduh model kecil. PC 8 GB RAM (i3/i7 generasi 8-9): `ollama pull qwen2.5:1.5b` (sekitar 1 GB). PC lebih lega: `ollama pull qwen2.5:3b`, lalu tambahkan `-Model qwen2.5:3b` saat menjalankan.

**Pemakaian** (selalu simulasi dulu):

```powershell
powershell -ExecutionPolicy Bypass -File .\Rapikan-AI.ps1 -Path "$env:USERPROFILE\Documents\Kantor"
powershell -ExecutionPolicy Bypass -File .\Rapikan-AI.ps1 -Path "$env:USERPROFILE\Documents\Kantor" -Apply
```

- AI hanya dijalankan sekali per file: hasil simulasi tersimpan di `_RapikanAI_Rencana.csv` dan dipakai ulang oleh `-Apply`. Bila dihentikan di tengah (Ctrl+C), analisis dilanjutkan dari file berikutnya.
- `-Tujuan "D:\Arsip"` memindahkan ke drive lain. `-UsulNama` mengganti nama file dengan judul dari AI (periksa dulu di simulasi). `-Kategori "Surat=surat masuk/keluar|Keuangan=anggaran, kwitansi|Lainnya=sisanya"` memakai kategori sendiri; keterangan setelah tanda `=` membantu model kecil memilih dengan tepat (pisahkan kategori dengan `|`). Mengganti kategori otomatis memicu analisis ulang. `-Recurse` ikut subfolder.
- `-TanpaAI` memilah dengan kata kunci saja, tanpa Ollama: sangat ringan untuk PC lemah.
- `-Undo "log.csv"` mengembalikan semuanya (format log sama dengan `Rapikan-Folder.ps1`).
- Aman: AI hanya boleh memilih dari daftar kategori, jadi isi dokumen tidak bisa memerintahkan apa pun. Tidak ada file yang dihapus.

**Format yang dibaca isinya:** txt, md, csv, docx, xlsx, pptx, odt/ods/odp. PDF dibaca isinya hanya bila `pdftotext` terpasang; selain itu, juga untuk .doc/.xls/.ppt lama, hanya nama file yang dipakai. Dokumen hasil scan (gambar) tidak terbaca isinya.

## Opsi

| Opsi | Fungsi |
| --- | --- |
| `-Path "folder"` | Folder yang dirapikan (wajib, kecuali saat `-Undo`). |
| `-Tujuan "folder"` | Pindahkan hasilnya ke folder/drive lain (dikelompokkan di sana). |
| `-Pribadi` | Pilih otomatis Documents, Pictures, Videos, Music, Downloads milik Anda. |
| `-By Type` | *(bawaan)* Subfolder per jenis: `Gambar`, `Dokumen`, `Video`, dan seterusnya. |
| `-By Date` | Subfolder per bulan modifikasi, mis. `2026-11`. |
| `-By TypeDate` | Gabungan: `Gambar\2026-11\foto.jpg`. |
| `-Recurse` | Ikut merapikan isi subfolder (bawaan: hanya file di tingkat atas). |
| `-Apply` | Benar-benar memindahkan file. Tanpa ini hanya simulasi. |
| `-Undo "log.csv"` | Mengembalikan file ke tempat asal sesuai file log. |

## Pengelompokan jenis file

| Folder | Ekstensi |
| --- | --- |
| Gambar | jpg, jpeg, png, gif, bmp, webp, heic, heif, tif, tiff, svg, ico, raw, cr2, nef |
| Dokumen | pdf, doc, docx, rtf, odt, txt, md, epub |
| Spreadsheet | xls, xlsx, xlsm, csv, ods, tsv |
| Presentasi | ppt, pptx, pps, ppsx, odp, key |
| Video | mp4, mkv, avi, mov, wmv, flv, webm, m4v, mpg, mpeg, 3gp |
| Audio | mp3, wav, flac, aac, ogg, m4a, wma, opus, mid, midi |
| Arsip | zip, rar, 7z, tar, gz, bz2, xz, iso |
| Aplikasi | exe, msi, apk, dmg, msix |
| Kode | py, js, ts, html, htm, css, json, xml, lua, cs, cpp, c, h, java, ps1, bat, sh, sql, yml, yaml |
| Lainnya | semua ekstensi di luar daftar di atas, dan file tanpa ekstensi |

Daftar ini ada di bagian `$map` pada skrip. Ubah sesuai kebutuhan.

## Yang dilewati

File tersembunyi/sistem, `desktop.ini`, `thumbs.db`, pintasan (`.lnk`), unduhan yang belum selesai (`.crdownload`, `.part`, `.tmp`), file log skrip ini, dan file yang sudah berada di folder tujuannya. Subfolder yang kosong setelah pemindahan **tidak** dihapus.

## Pemecahan masalah

- **"running scripts is disabled on this system"**: jalankan dengan `powershell -ExecutionPolicy Bypass -File ...` seperti pada contoh, atau sekali saja `Unblock-File .\Rapikan-Folder.ps1`.
- **"Ditolak: ..."**: folder yang dipilih termasuk daftar terlarang. Pilih subfolder, bukan akar drive atau folder sistem.
- **"Gagal (dilewati): ..."**: file sedang dipakai aplikasi lain. Tutup aplikasinya lalu jalankan ulang. File yang sudah rapi tidak diproses lagi.
- Setelah `-Apply`, jangan menghapus file log `_RapikanLog_*.csv` sebelum Anda yakin tidak perlu membatalkan.

## Batasan

- Diuji pada PowerShell 7 dengan folder contoh (simulasi, eksekusi, jalan ulang, undo, mode tanggal, penolakan folder terlarang). Simulasi dasar sudah dicoba di Windows PowerShell 5.1; fitur `-Tujuan`/`-Pribadi` diuji di PowerShell 7.
- Undo melewati file yang sudah dipindah atau diubah setelah proses berjalan, dan melaporkan jumlahnya.
- Tanggal yang dipakai adalah waktu modifikasi terakhir file, bukan tanggal pembuatan.

## Lisensi

[MIT](LICENSE)
Versi Python: `rapikan_v3.py` (perintah bahasa chat)
Rapikan file di Windows hanya dengan mengetik kalimat biasa. Ollama (AI lokal, gratis) membantu memahami perintah, sedangkan pemindahan file dilakukan oleh skrip Python dengan pratinjau dan konfirmasi terlebih dahulu.
Fitur
Perintah seperti chat: `rapikan folder downloads per tahun ke drive E`
File dikelompokkan per jenis: `PDF`, `Word`, `Excel`, `Gambar`, `Video`, `Arsip`, dan seterusnya
Opsi per tahun dan per topik (topik dibantu AI, isi PDF ikut dibaca bila `pypdf` terpasang)
Deteksi file kembar (isi sama) lalu dipindah ke `_Duplikat`
Pratinjau sebelum memindahkan, dan konfirmasi `y/n`
Batalkan (`batalkan`) mengembalikan pemindahan terakhir, dengan riwayat dan laporan CSV
Pemindahan aman: salin, verifikasi ukuran, baru hapus file asal
Menolak merapikan akar drive (`C:\`, `D:\`) dan melewati file sementara `~$`
Persyaratan
Windows dengan minimal satu drive lain selain C: (D:, E:, dan seterusnya)
Python 3
Ollama dan model `qwen2.5:7b`
Git (untuk mengambil repo)
Pemasangan
```powershell
git clone https://github.com/pradeasd26/Rapikan-Folder
cd Rapikan-Folder
pip install requests pypdf
ollama pull qwen2.5:7b
```
Cara pakai
Jalankan di PowerShell:
```powershell
python rapikan_v3.py
```
Setelah muncul prompt `Kamu:`, ketik perintah, contohnya:
Perintah	Hasil
`rapikan folder downloads`	Merapikan folder Downloads
`rapikan folder D:\Scan ke drive E`	Merapikan `D:\Scan`, hasil ke drive E
`rapikan downloads per tahun`	Tambah subfolder tahun
`rapikan downloads per topik`	Tambah subfolder topik (AI)
`rapikan downloads kecuali Proyek dan Kuliah`	Melewati folder tertentu
`batalkan`	Mengembalikan pemindahan terakhir
`riwayat`	Melihat daftar log
`keluar`	Menutup skrip
Contoh hasil:
```
E:\Rapi\PDF\...
E:\Rapi\Word\...
E:\Rapi\Gambar\...
E:\Rapi\_Duplikat\PDF\...
```
Keamanan dan catatan
Skrip memindahkan file, bukan menyalin. Cobalah dulu pada folder kecil.
Sebelum menekan `y`, periksa baris `Folder:` dan jumlah file di pratinjau.
Jangan merapikan folder program atau sistem, karena aplikasi bisa berhenti bekerja.
Pastikan Ollama sedang berjalan sebelum memakai skrip.
Log, laporan CSV, dan cache disimpan di `C:\Users\NamaAnda\rapikan_logs`.
Perintah `git` dan `python` diketik di PowerShell (`PS C:\...>`), sedangkan kalimat perapian diketik di dalam skrip (prompt `Kamu:`).