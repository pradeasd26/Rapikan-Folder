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
