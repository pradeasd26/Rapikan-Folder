"""
Rapikan AI v3 (Windows) - tulis perintah seperti chat biasa.

Contoh:
  rapikan folder downloads
  tolong rapikan dokumen saya ke drive E
  rapikan folder Documents\\Uji per tahun
  rapikan downloads dan kelompokkan juga per topik
  rapikan downloads kecuali Proyek dan Kuliah
  batalkan  |  riwayat  |  bantuan  |  keluar

Hasil: file dikelompokkan per JENIS, contoh
  D:\\Rapi\\PDF\\...   D:\\Rapi\\Word\\...   D:\\Rapi\\Gambar\\...
Opsi "per topik"  -> di dalam folder jenis dibuat subfolder topik (dibantu AI)
Opsi "per tahun"  -> di dalam folder jenis dibuat subfolder tahun
File kembar (isi sama) -> D:\\Rapi\\_Duplikat\\<jenis>\\

Persiapan:  pip install requests   (opsional: pip install pypdf)
            ollama pull qwen2.5:7b
"""
import csv, hashlib, json, os, re, shutil, string, sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import requests

MODEL = "qwen2.5:7b"
OLLAMA = "http://localhost:11434/api/generate"
FOLDER_TUJUAN = "Rapi"
LOG_DIR = Path.home() / "rapikan_logs"
CACHE = LOG_DIR / "cache_topik.json"
BATCH = 25
SKIP_EXT = {".exe", ".dll", ".sys", ".lnk", ".ini", ".msi", ".bat", ".tmp"}
SKIP_DIR = {"node_modules", ".git", "__pycache__", "appdata", "$recycle.bin"}
LOG_DIR.mkdir(exist_ok=True)

TIPE = {
    "PDF": {".pdf"},
    "Word": {".doc", ".docx", ".odt", ".rtf"},
    "Excel": {".xls", ".xlsx", ".xlsm", ".ods", ".csv"},
    "PowerPoint": {".ppt", ".pptx", ".odp"},
    "Gambar": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".svg"},
    "Video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"},
    "Teks": {".txt", ".md", ".log"},
    "Arsip": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Kode": {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".ps1", ".json", ".sql"},
}
KATA_FOLDER = {
    "dokumen": "Documents", "documents": "Documents",
    "download": "Downloads", "unduhan": "Downloads",
    "desktop": "Desktop", "gambar": "Pictures", "foto": "Pictures",
    "video": "Videos", "musik": "Music",
}


# ---------- jenis file ----------
def tipe_file(f):
    ext = f.suffix.lower()
    for nama, daftar in TIPE.items():
        if ext in daftar:
            return nama
    return f"File_{ext[1:].upper()}" if ext else "Tanpa_Ekstensi"


# ---------- memahami chat ----------
def ollama_json(prompt):
    r = requests.post(OLLAMA, json={"model": MODEL, "prompt": prompt, "format": "json",
                      "stream": False, "options": {"temperature": 0}}, timeout=300)
    return json.loads(r.json()["response"])


def pahami_dasar(teks):
    """Cara cadangan tanpa model."""
    low = teks.lower()
    kecuali = []
    m = re.search(r"kecuali (.+)", teks, re.I)
    if m:
        kecuali = [x.strip() for x in re.split(r",|\bdan\b", m.group(1)) if x.strip()]
    d = re.search(r"drive\s+([a-z])\b", low)
    return {
        "folder": next((k for k in KATA_FOLDER if k in low), None),
        "per_tahun": "per tahun" in low or "tiap tahun" in low,
        "topik": "topik" in low or "isi" in low,
        "kecuali": kecuali,
        "drive": d.group(1).upper() if d else None,
    }


def pahami(teks):
    low = teks.lower().strip()
    if re.search(r"\b(undo|batalkan|batal|kembalikan)\b", low):
        return {"aksi": "undo"}
    if "riwayat" in low:
        return {"aksi": "riwayat"}
    if low in {"keluar", "exit", "quit", "selesai"}:
        return {"aksi": "keluar"}
    if low in {"bantuan", "help", "?"}:
        return {"aksi": "bantuan"}
    hasil = pahami_dasar(teks)
    try:
        prompt = (
            "Terjemahkan chat pengguna menjadi JSON perintah merapikan file. "
            'Skema: {"folder": string atau null, "per_tahun": bool, "topik": bool, '
            '"kecuali": [string], "drive": huruf drive tujuan atau null}. '
            "folder = nama/path folder yang mau dirapikan (mis. Downloads, Documents, "
            "atau path lengkap). per_tahun = true jika diminta dikelompokkan per tahun. "
            "topik = true jika diminta dikelompokkan per topik/isi. kecuali = folder yang "
            "tidak boleh disentuh. Balas HANYA JSON.\nChat: " + teks
        )
        j = ollama_json(prompt)
        for k in ("folder", "per_tahun", "topik", "kecuali", "drive"):
            if j.get(k) not in (None, "", [], False):
                hasil[k] = j[k]
    except Exception as e:
        print("  (model gagal memahami, memakai cara cadangan:", e, ")")
    hasil["aksi"] = "rapikan"
    return hasil


def cari_folder(teks):
    if not teks:
        return None
    teks = str(teks).strip('" ')
    p = Path(teks)
    kandidat = [p, Path.home() / teks, Path.home() / "Documents" / teks,
                Path.home() / "Downloads" / teks, Path.home() / "Desktop" / teks]
    for k in kandidat:
        if k.is_absolute() and k.is_dir():
            return k
    for k in kandidat:
        if k.is_dir():
            return k.resolve()
    low = teks.lower()
    for kata, nama in KATA_FOLDER.items():
        if kata in low:
            return Path.home() / nama
    return None


# ---------- drive ----------
def drive_tersedia(paksa=None):
    hasil = []
    for h in string.ascii_uppercase:
        if h == "C" or (paksa and h != paksa):
            continue
        root = f"{h}:\\"
        if os.path.exists(root):
            try:
                hasil.append((root, shutil.disk_usage(root).free))
            except OSError:
                pass
    return sorted(hasil, key=lambda x: -x[1])


# ---------- pemindaian ----------
def kumpulkan(folder, kecuali):
    skip = SKIP_DIR | {str(k).lower() for k in kecuali}
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
    unik_list, dup = [], []
    for ukuran, grup in per_ukuran.items():
        if len(grup) == 1 or ukuran == 0:
            unik_list += grup
            continue
        lihat = set()
        for f in grup:
            try:
                k = hash_file(f)
            except OSError:
                unik_list.append(f)
                continue
            if k in lihat:
                dup.append(f)
            else:
                lihat.add(k)
                unik_list.append(f)
    return unik_list, dup


# ---------- topik (opsional, dibantu AI) ----------
def cuplikan(f):
    ext = f.suffix.lower()
    try:
        if ext in {".txt", ".md", ".csv", ".log"}:
            return f.read_text(encoding="utf-8", errors="ignore")[:200].replace("\n", " ")
        if ext == ".pdf":
            from pypdf import PdfReader
            return (PdfReader(str(f)).pages[0].extract_text() or "")[:200].replace("\n", " ")
    except Exception:
        pass
    return ""


def bersihkan(nama):
    nama = "".join(c for c in str(nama) if c not in '<>:"/\\|?*').strip()
    return nama or "Umum"


def topik_ai(files):
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    peta = {f: cache[f.name] for f in files if f.name in cache}
    perlu = [f for f in files if f not in peta]
    dipakai = sorted(set(cache.values()))
    print(f"  topik: {len(peta)} dari cache, {len(perlu)} ditanyakan ke model")
    for i in range(0, len(perlu), BATCH):
        grup = perlu[i:i + BATCH]
        daftar = [{"nama": f.name, "isi": cuplikan(f)} for f in grup]
        prompt = (
            "Beri tiap file SATU nama topik folder singkat bahasa Indonesia "
            "(1-2 kata, mis. Keuangan, Kepegawaian, Akademik, Kerjasama, Pribadi, Umum). "
            "Gunakan ulang topik yang sudah ada jika cocok: "
            f"{dipakai}. Balas HANYA JSON {{\"nama_file\": \"Topik\"}}.\n"
            + json.dumps(daftar, ensure_ascii=False)
        )
        try:
            hasil = ollama_json(prompt)
        except Exception as e:
            print("  Gagal membaca jawaban model:", e)
            hasil = {}
        for f in grup:
            t = bersihkan(hasil.get(f.name, "Umum"))
            peta[f] = t
            cache[f.name] = t
            if t not in dipakai:
                dipakai.append(t)
        print(f"  topik {min(i + BATCH, len(perlu))}/{len(perlu)}")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return peta


# ---------- rencana & eksekusi ----------
def rencana(unik_list, dup, per_tahun, topik, paksa_drive):
    drives = [[d, int(s * 0.95)] for d, s in drive_tersedia(paksa_drive)]
    if not drives:
        sys.exit("Drive tujuan tidak ditemukan (D:, E:, ... atau drive yang Anda sebut).")
    peta_topik = topik_ai(unik_list) if topik and unik_list else {}
    item = [(f, False) for f in unik_list] + [(f, True) for f in dup]
    langkah = []
    for f, is_dup in item:
        try:
            st = f.stat()
        except OSError:
            continue
        sub = Path("_Duplikat") / tipe_file(f) if is_dup else Path(tipe_file(f))
        if not is_dup and topik:
            sub = sub / peta_topik.get(f, "Umum")
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
    awal, n = path, 1
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
    with open(LOG_DIR / f"laporan_{stamp}.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["dari", "ke"])
        w.writerows([[c["dari"], c["ke"]] for c in catatan])
    print(f"\nSelesai. {len(catatan)} file dipindah.\nLog: {log}")


def undo():
    logs = sorted(LOG_DIR.glob("log_*.json"))
    if not logs:
        return print("Belum ada yang bisa dikembalikan.")
    log, ok = logs[-1], 0
    for c in json.loads(log.read_text(encoding="utf-8")):
        try:
            Path(c["dari"]).parent.mkdir(parents=True, exist_ok=True)
            pindah_aman(Path(c["ke"]), unik(Path(c["dari"])))
            ok += 1
        except Exception as e:
            print("Gagal mengembalikan:", c["ke"], e)
    log.rename(log.with_suffix(".undone"))
    print(f"{ok} file dikembalikan ({log.name}).")


def riwayat():
    logs = sorted(LOG_DIR.glob("log_*.json"))
    if not logs:
        return print("Belum ada riwayat.")
    for l in logs:
        print(f"{l.name}  ({len(json.loads(l.read_text(encoding='utf-8')))} file)")


def tampilkan_pratinjau(langkah):
    print("\n--- PRATINJAU (belum ada yang dipindah) ---")
    hitung = Counter(str(t.parent.relative_to(t.parents[-1])) for _, t in langkah)
    for tujuan, n in sorted(hitung.items()):
        print(f"  {n:4d} file -> {tujuan}")
    print()
    for asal, tujuan in langkah[:10]:
        print(f"  {asal.name}  ->  {tujuan.parent}")
    if len(langkah) > 10:
        print(f"  ... dan {len(langkah) - 10} file lainnya")


def rapikan(perintah):
    folder = cari_folder(perintah.get("folder"))
    while folder is None:
        jawab = input("Folder mana yang mau dirapikan? (nama atau path): ").strip()
        if not jawab:
            return
        folder = cari_folder(jawab)
        if folder is None:
            print("Folder tidak ditemukan, coba lagi (kosongkan untuk batal).")
    paksa = None
    if perintah.get("drive"):
        m = re.search(r"[A-Za-z]", str(perintah["drive"]))
        paksa = m.group(0).upper() if m else None
        if paksa == "C":
            paksa = None
    print(f"Folder: {folder}" + (f" | drive tujuan: {paksa}:" if paksa else ""))
    files = kumpulkan(folder, perintah.get("kecuali") or [])
    print(f"{len(files)} file ditemukan. Memeriksa duplikat...")
    unik_list, dup = pisah_duplikat(files)
    print(f"  {len(dup)} file kembar.")
    langkah = rencana(unik_list, dup, bool(perintah.get("per_tahun")),
                      bool(perintah.get("topik")), paksa)
    if not langkah:
        return print("Tidak ada file yang perlu dipindah.")
    tampilkan_pratinjau(langkah)
    if input(f"\nPindahkan {len(langkah)} file? (y/n): ").strip().lower() in ("y", "ya"):
        jalankan(langkah)
    else:
        print("Dibatalkan, tidak ada file yang dipindah.")


def main():
    print(__doc__.split("Hasil:")[0])
    while True:
        teks = input("\nKamu: ").strip()
        if not teks:
            continue
        p = pahami(teks)
        aksi = p.get("aksi")
        if aksi == "keluar":
            break
        elif aksi == "undo":
            undo()
        elif aksi == "riwayat":
            riwayat()
        elif aksi == "bantuan":
            print(__doc__)
        else:
            rapikan(p)


if __name__ == "__main__":
    main()
