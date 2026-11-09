"""
Perapi file berbasis Ollama (Windows) - Versi 2.

Contoh perintah:
  rapikan dokumen
  rapikan downloads per tahun
  rapikan downloads kecuali Proyek, Kuliah
  undo        -> kembalikan pemindahan terakhir
  riwayat     -> lihat daftar log
  keluar

Fitur baru:
  1. Deteksi file duplikat (hash SHA-256) -> dipindah ke folder _Duplikat
     (tanpa memakai model, jadi hemat waktu)
  2. Pengecualian folder lewat kata "kecuali ..."
  3. Subfolder per tahun lewat kata "per tahun"
  4. Pemindahan aman: salin -> verifikasi ukuran -> hapus asal
  5. Log berstempel waktu + undo bertingkat (bisa undo berkali-kali)
  6. Laporan CSV setiap selesai merapikan
  7. Kategori disimpan (cache) agar file bernama sama tidak ditanyakan ulang

Persiapan:  pip install requests   dan   ollama pull qwen2.5:7b
"""
import csv, hashlib, json, os, re, shutil, string, sys, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import requests

MODEL = "qwen2.5:7b"
OLLAMA = "http://localhost:11434/api/generate"
FOLDER_TUJUAN = "Rapi"
LOG_DIR = Path.home() / "rapikan_logs"
CACHE = LOG_DIR / "cache_kategori.json"
BATCH = 25
SKIP_EXT = {".exe", ".dll", ".sys", ".lnk", ".ini", ".msi", ".bat", ".tmp"}
SKIP_DIR = {"node_modules", ".git", "__pycache__", "AppData", "$RECYCLE.BIN"}
KATA_KUNCI = {
    "dokumen": "Documents", "documents": "Documents",
    "download": "Downloads", "unduhan": "Downloads",
    "desktop": "Desktop", "gambar": "Pictures", "foto": "Pictures",
    "video": "Videos", "musik": "Music",
}
LOG_DIR.mkdir(exist_ok=True)


# ---------- util ----------
def drive_tersedia():
    hasil = []
    for h in string.ascii_uppercase:
        root = f"{h}:\\"
        if h != "C" and os.path.exists(root):
            try:
                hasil.append((root, shutil.disk_usage(root).free))
            except OSError:
                pass
    return sorted(hasil, key=lambda x: -x[1])


def baca_opsi(prompt):
    p = prompt.lower()
    per_tahun = "per tahun" in p
    kecuali = set()
    m = re.search(r"kecuali (.+)", prompt, re.I)
    if m:
        kecuali = {x.strip().lower() for x in m.group(1).split(",") if x.strip()}
    folder = None
    for kata, nama in KATA_KUNCI.items():
        if kata in p:
            folder = Path.home() / nama
            break
    if folder is None:
        jalur = input("Folder mana yang dirapikan? (path lengkap): ").strip('" ')
        folder = Path(jalur)
    return folder, per_tahun, kecuali


def kumpulkan(folder, kecuali):
    skip = {s.lower() for s in SKIP_DIR} | kecuali
    hasil = []
    for dirpath, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d.lower() not in skip]
        for n in names:
            f = Path(dirpath) / n
            if f.suffix.lower() not in SKIP_EXT:
                hasil.append(f)
    return hasil


def hash_file(f):
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for blok in iter(lambda: fh.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def pisah_duplikat(files):
    per_ukuran = defaultdict(list)
    for f in files:
        try:
            per_ukuran[f.stat().st_size].append(f)
        except OSError:
            pass
    unik_list, duplikat = [], []
    for ukuran, grup in per_ukuran.items():
        if len(grup) == 1 or ukuran == 0:
            unik_list += grup
            continue
        terlihat = {}
        for f in grup:
            try:
                k = hash_file(f)
            except OSError:
                unik_list.append(f)
                continue
            if k in terlihat:
                duplikat.append(f)
            else:
                terlihat[k] = f
                unik_list.append(f)
    return unik_list, duplikat


def cuplikan(f):
    if f.suffix.lower() in {".txt", ".md", ".csv", ".log"}:
        try:
            return f.read_text(encoding="utf-8", errors="ignore")[:150].replace("\n", " ")
        except OSError:
            return ""
    return ""


def bersihkan(nama):
    nama = "".join(c for c in str(nama) if c not in '<>:"/\\|?*').strip()
    return nama or "Lainnya"


# ---------- kategori ----------
def kategorikan(files):
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    peta, perlu = {}, []
    for f in files:
        if f.name in cache:
            peta[f] = cache[f.name]
        else:
            perlu.append(f)
    print(f"  {len(peta)} dari cache, {len(perlu)} perlu ditanyakan ke model")
    for i in range(0, len(perlu), BATCH):
        grup = perlu[i:i + BATCH]
        daftar = [{"nama": f.name, "isi": cuplikan(f)} for f in grup]
        prompt = (
            "Kelompokkan tiap file ke SATU nama kategori folder singkat bahasa "
            "Indonesia (contoh: Keuangan, Pekerjaan, Sekolah, Foto, Musik, Video, "
            "Kode, Arsip, Lainnya). Pakai nama kategori yang konsisten. "
            'Balas HANYA JSON {"nama_file": "Kategori"}.\n'
            + json.dumps(daftar, ensure_ascii=False)
        )
        try:
            r = requests.post(OLLAMA, json={"model": MODEL, "prompt": prompt,
                              "format": "json", "stream": False}, timeout=300)
            hasil = json.loads(r.json()["response"])
        except Exception as e:
            print("  Gagal membaca jawaban model:", e)
            hasil = {}
        for f in grup:
            kat = bersihkan(hasil.get(f.name, "Lainnya"))
            peta[f] = kat
            cache[f.name] = kat
        print(f"  dikategorikan {min(i + BATCH, len(perlu))}/{len(perlu)}")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return peta


# ---------- rencana & eksekusi ----------
def rencana(peta, duplikat, per_tahun):
    drives = [[d, int(s * 0.95)] for d, s in drive_tersedia()]
    if not drives:
        sys.exit("Tidak ada drive lain (D:, E:, ...) yang ditemukan.")
    item = [(f, k) for f, k in peta.items()] + [(f, "_Duplikat") for f in duplikat]
    langkah = []
    for f, kat in item:
        try:
            st = f.stat()
        except OSError:
            continue
        sub = Path(kat)
        if per_tahun:
            sub = sub / str(datetime.fromtimestamp(st.st_mtime).year)
        for d in drives:
            if d[1] >= st.st_size:
                d[1] -= st.st_size
                langkah.append((f, Path(d[0]) / FOLDER_TUJUAN / sub / f.name))
                break
        else:
            print("Ruang tidak cukup, dilewati:", f)
    return langkah


def unik(path):
    n = 1
    awal = path
    while path.exists():
        path = awal.with_name(f"{awal.stem}_{n}{awal.suffix}")
        n += 1
    return path


def pindah_aman(asal, tujuan):
    shutil.copy2(asal, tujuan)
    if tujuan.stat().st_size != asal.stat().st_size:
        tujuan.unlink()
        raise IOError("ukuran tidak cocok setelah disalin")
    asal.unlink()


def jalankan(langkah):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    catatan = []
    for asal, tujuan in langkah:
        try:
            tujuan = unik(tujuan)
            tujuan.parent.mkdir(parents=True, exist_ok=True)
            pindah_aman(asal, tujuan)
            catatan.append({"dari": str(asal), "ke": str(tujuan)})
        except Exception as e:
            print("Gagal:", asal, "->", e)
    log = LOG_DIR / f"log_{stamp}.json"
    log.write_text(json.dumps(catatan, indent=1, ensure_ascii=False), encoding="utf-8")
    laporan = LOG_DIR / f"laporan_{stamp}.csv"
    with open(laporan, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["dari", "ke"])
        w.writerows([[c["dari"], c["ke"]] for c in catatan])
    print(f"\nSelesai. {len(catatan)} file dipindah.\nLog: {log}\nLaporan: {laporan}")


def daftar_log():
    return sorted(LOG_DIR.glob("log_*.json"))


def undo():
    logs = daftar_log()
    if not logs:
        return print("Tidak ada log untuk dikembalikan.")
    log = logs[-1]
    ok = 0
    for c in json.loads(log.read_text(encoding="utf-8")):
        try:
            Path(c["dari"]).parent.mkdir(parents=True, exist_ok=True)
            pindah_aman(Path(c["ke"]), unik(Path(c["dari"])))
            ok += 1
        except Exception as e:
            print("Gagal mengembalikan:", c["ke"], e)
    log.rename(log.with_suffix(".undone"))
    print(f"{ok} file dikembalikan dari {log.name}.")


def riwayat():
    logs = daftar_log()
    if not logs:
        return print("Belum ada riwayat.")
    for l in logs:
        n = len(json.loads(l.read_text(encoding="utf-8")))
        print(f"{l.name}  ({n} file)")


def main():
    print(__doc__.split("Fitur baru")[0])
    while True:
        prompt = input("\n> ").strip()
        if prompt in ("keluar", "exit"):
            break
        if prompt == "undo":
            undo()
            continue
        if prompt == "riwayat":
            riwayat()
            continue
        folder, per_tahun, kecuali = baca_opsi(prompt)
        if not folder.exists():
            print("Folder tidak ditemukan:", folder)
            continue
        files = kumpulkan(folder, kecuali)
        print(f"{len(files)} file ditemukan. Mencari duplikat...")
        unik_list, duplikat = pisah_duplikat(files)
        print(f"  {len(duplikat)} duplikat. Meminta Ollama mengkategorikan...")
        langkah = rencana(kategorikan(unik_list), duplikat, per_tahun)
        print("\n--- PRATINJAU (belum ada yang dipindah) ---")
        for asal, tujuan in langkah[:30]:
            print(f"{asal.name}  ->  {tujuan.parent}")
        if len(langkah) > 30:
            print(f"... dan {len(langkah) - 30} file lainnya")
        if langkah and input(f"\nPindahkan {len(langkah)} file? (y/n): ").lower() == "y":
            jalankan(langkah)


if __name__ == "__main__":
    main()
