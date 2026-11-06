<#
.SYNOPSIS
  Merapikan isi sebuah folder ke subfolder per jenis file (dan/atau bulan). Aman: simulasi dulu, tidak menghapus file, bisa di-undo.

.EXAMPLE
  # 1) SIMULASI (default, tidak ada file yang dipindah):
  .\Rapikan-Folder.ps1 -Path "C:\Users\Nama\Downloads"

  # 2) Jalankan sungguhan setelah daftar rencana terlihat benar:
  .\Rapikan-Folder.ps1 -Path "C:\Users\Nama\Downloads" -Apply

  # 3) Per jenis lalu per bulan (Gambar\2026-11\foto.jpg), termasuk isi subfolder:
  .\Rapikan-Folder.ps1 -Path "D:\Kantor" -By TypeDate -Recurse -Apply

  # 4) Kosongkan drive C: pindahkan folder pribadi (Downloads, Documents, Pictures, Videos, Music) ke drive D, per jenis:
  .\Rapikan-Folder.ps1 -Pribadi -Tujuan "D:\Arsip" -Recurse
  .\Rapikan-Folder.ps1 -Pribadi -Tujuan "D:\Arsip" -Recurse -Apply

  # 5) Batalkan: kembalikan semua file ke tempat asal memakai file log:
  .\Rapikan-Folder.ps1 -Undo "C:\Users\Nama\Downloads\_RapikanLog_20261106-140000.csv"
#>
[CmdletBinding()]
param(
    [string[]]$Path,
    [string]$Tujuan,
    [switch]$Pribadi,
    [ValidateSet('Type', 'Date', 'TypeDate')][string]$By = 'Type',
    [switch]$Apply,
    [switch]$Recurse,
    [string]$Undo
)

$ErrorActionPreference = 'Stop'
$sep = [IO.Path]::DirectorySeparatorChar

function Same([string]$a, [string]$b) { return [string]::Equals($a, $b, [StringComparison]::OrdinalIgnoreCase) }
function Under([string]$p, [string]$parent) {
    if ([string]::IsNullOrEmpty($parent)) { return $false }
    $parent = $parent.TrimEnd($sep)
    return (Same $p $parent) -or $p.StartsWith($parent + $sep, [StringComparison]::OrdinalIgnoreCase)
}

# ---------- MODE UNDO ----------
if ($Undo) {
    if (-not (Test-Path -LiteralPath $Undo -PathType Leaf)) { throw "File log tidak ditemukan: $Undo" }
    $rows = @(Import-Csv -LiteralPath $Undo)
    [array]::Reverse($rows)
    $ok = 0; $skip = 0; $dirs = @{}
    foreach ($r in $rows) {
        if ((Test-Path -LiteralPath $r.To -PathType Leaf) -and -not (Test-Path -LiteralPath $r.From)) {
            $fromDir = Split-Path -Parent $r.From
            if (-not (Test-Path -LiteralPath $fromDir)) { New-Item -ItemType Directory -Path $fromDir | Out-Null }
            Move-Item -LiteralPath $r.To -Destination $r.From -ErrorAction Stop
            $dirs[(Split-Path -Parent $r.To)] = $true
            $ok++
        } else { $skip++ }
    }
    # hanya folder KOSONG yang dibersihkan (file tidak pernah dihapus)
    foreach ($d in ($dirs.Keys | Sort-Object Length -Descending)) {
        if ((Test-Path -LiteralPath $d) -and -not (Get-ChildItem -LiteralPath $d -Force)) { Remove-Item -LiteralPath $d }
    }
    Write-Host "Undo selesai: $ok file dikembalikan, $skip dilewati (sudah berubah/pindah)."
    return
}

# ---------- VALIDASI FOLDER ----------
$sources = @()
if ($Pribadi) {
    $sources += [Environment]::GetFolderPath('MyDocuments')
    $sources += [Environment]::GetFolderPath('MyPictures')
    $sources += [Environment]::GetFolderPath('MyVideos')
    $sources += [Environment]::GetFolderPath('MyMusic')
    $sources += (Join-Path $env:USERPROFILE 'Downloads')
}
foreach ($pp in @($Path)) {   # -File menyatukan daftar "a","b" jadi satu teks: pecah di koma bila bukan folder utuh
    if (-not $pp) { continue }
    if (Test-Path -LiteralPath $pp -PathType Container) { $sources += $pp } else { $sources += ($pp -split ',' | ForEach-Object { $_.Trim().Trim('"') }) }
}
$sources = @($sources | Where-Object { $_ } | Select-Object -Unique)
if ($sources.Count -eq 0) { throw 'Isi -Path dengan folder yang mau dirapikan, atau pakai -Pribadi. Contoh: -Path "C:\Users\Nama\Downloads"' }

# Tolak folder sistem/berbahaya
$blocked = @($env:windir, $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData)
$roots = @()
foreach ($sp in $sources) {
    if (-not (Test-Path -LiteralPath $sp -PathType Container)) {
        if ($Pribadi -and -not $Path) { Write-Warning "Folder tidak ada, dilewati: $sp"; continue }
        throw "Folder tidak ditemukan: $sp"
    }
    $r = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $sp).ProviderPath)
    if ($r.Length -gt 1) { $r = $r.TrimEnd($sep) }
    $pr = [IO.Path]::GetPathRoot($r)
    if ($r.TrimEnd($sep) -eq $pr.TrimEnd($sep)) { throw "Ditolak: jangan rapikan akar drive ($r)." }
    foreach ($b in $blocked) { if (Under $r $b) { throw "Ditolak: folder sistem/program ($r)." } }
    if ($env:USERPROFILE -and (Same $r $env:USERPROFILE.TrimEnd($sep))) { throw "Ditolak: pilih subfolder (Downloads, Documents, dst), bukan folder profil utama." }
    if ($env:USERPROFILE -and (Under $r (Join-Path $env:USERPROFILE 'AppData'))) { throw "Ditolak: AppData dipakai aplikasi ($r)." }
    $roots += $r
}
if ($roots.Count -eq 0) { throw "Tidak ada folder sumber yang valid." }
$root = $roots[0]   # tempat log bila tanpa -Tujuan

# Folder tujuan (opsional): pindah ke drive/folder lain
$destBase = $null
if ($Tujuan) {
    $destBase = [IO.Path]::GetFullPath($Tujuan).TrimEnd($sep)
    foreach ($r in $roots) {
        if ((Under $destBase $r) -or (Under $r $destBase)) { throw "Ditolak: -Tujuan tidak boleh berada di dalam folder sumber (atau sebaliknya): $r" }
    }
    foreach ($b in $blocked) { if (Under $destBase $b) { throw "Ditolak: tujuan tidak boleh folder sistem ($destBase)." } }
    $root = $destBase   # log disimpan di tujuan
}

# ---------- PETA JENIS FILE ----------
$map = [ordered]@{
    'Gambar'       = 'jpg jpeg png gif bmp webp heic heif tif tiff svg ico raw cr2 nef'
    'Dokumen'      = 'pdf doc docx rtf odt txt md epub'
    'Spreadsheet'  = 'xls xlsx xlsm csv ods tsv'
    'Presentasi'   = 'ppt pptx pps ppsx odp key'
    'Video'        = 'mp4 mkv avi mov wmv flv webm m4v mpg mpeg 3gp'
    'Audio'        = 'mp3 wav flac aac ogg m4a wma opus mid midi'
    'Arsip'        = 'zip rar 7z tar gz bz2 xz iso'
    'Aplikasi'     = 'exe msi apk dmg msix'
    'Kode'         = 'py js ts html htm css json xml lua cs cpp c h java ps1 bat sh sql yml yaml'
}
$extToCat = @{}
foreach ($k in $map.Keys) { foreach ($e in ($map[$k] -split ' ')) { $extToCat[$e] = $k } }
$skipExt = @('lnk', 'crdownload', 'part', 'tmp', 'partial', 'download')   # shortcut & unduhan yang belum selesai
$skipName = @('desktop.ini', 'thumbs.db', '.ds_store')

# ---------- SUSUN RENCANA ----------
$plan = New-Object System.Collections.ArrayList
$taken = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$skipped = 0; $cloud = 0; $totalBytes = [int64]0
foreach ($src in $roots) {
    $base = $src
    if ($destBase) { $base = $destBase }
    $files = @(Get-ChildItem -LiteralPath $src -File -Recurse:$Recurse -ErrorAction SilentlyContinue)
    foreach ($f in $files) {
        if (-not $seen.Add($f.FullName)) { continue }
        $ext = $f.Extension.TrimStart('.').ToLowerInvariant()
        $attr = [int]$f.Attributes
        if (($attr -band 0x1000) -ne 0 -or ($attr -band 0x400000) -ne 0 -or ($attr -band 0x40000) -ne 0) { $cloud++; continue }   # file OneDrive yang hanya online
        if (($f.Attributes -band ([IO.FileAttributes]::Hidden -bor [IO.FileAttributes]::System)) -ne 0 -or
            $skipName -contains $f.Name.ToLowerInvariant() -or $skipExt -contains $ext -or
            $f.Name -like '_RapikanLog_*.csv' -or $f.Name -like 'Rapikan-Folder*.ps1') { $skipped++; continue }

        $cat = 'Lainnya'
        if ($extToCat.ContainsKey($ext)) { $cat = $extToCat[$ext] }
        $parts = @()
        if ($By -eq 'Type' -or $By -eq 'TypeDate') { $parts += $cat }
        if ($By -eq 'Date' -or $By -eq 'TypeDate') { $parts += $f.LastWriteTime.ToString('yyyy-MM') }
        $destDir = $base
        foreach ($p in $parts) { $destDir = Join-Path $destDir $p }

        $dest = Join-Path $destDir $f.Name
        if (Same $dest $f.FullName) { $skipped++; continue }        # sudah rapi di tempatnya
        # nama kembar: tambahkan " (2)", " (3)", ...
        $n = 2
        $bn = [IO.Path]::GetFileNameWithoutExtension($f.Name); $x = $f.Extension
        while ((Test-Path -LiteralPath $dest) -or $taken.Contains($dest)) {
            $dest = Join-Path $destDir ("{0} ({1}){2}" -f $bn, $n, $x); $n++
        }
        [void]$taken.Add($dest)
        $totalBytes += $f.Length
        [void]$plan.Add([pscustomobject]@{ Kategori = $(if ($parts.Count) { $parts -join $sep } else { '.' }); From = $f.FullName; To = $dest })
    }
}

# Cek ruang kosong di drive tujuan
if ($destBase -and $plan.Count -gt 0) {
    $tr = [IO.Path]::GetPathRoot($destBase)
    if ($tr -and $tr -notlike '\\*') {
        try {
            $free = (New-Object IO.DriveInfo($tr)).AvailableFreeSpace
            if ($totalBytes -gt ($free - 1GB)) { throw ("Ruang di {0} tidak cukup: butuh {1:N1} GB, tersedia {2:N1} GB." -f $tr, ($totalBytes/1GB), ($free/1GB)) }
        } catch [System.ArgumentException] { }
    }
}

if ($plan.Count -eq 0) { Write-Host "Tidak ada file yang perlu dirapikan ($skipped dilewati)."; return }

Write-Host ""
if ($destBase) { Write-Host "Sumber : $($roots -join ', ')"; Write-Host "Tujuan : $destBase" } else { Write-Host "Folder : $root" }
if ($destBase) { Write-Host ("Ukuran : {0:N2} GB" -f ($totalBytes/1GB)) }
if ($cloud) { Write-Host "Dilewati $cloud file OneDrive yang hanya online (tidak diunduh)." }
Write-Host "Mode   : $By$(if ($Recurse) { ' + subfolder' })"
Write-Host "Rencana: $($plan.Count) file akan dipindah, $skipped dilewati."
$plan | Group-Object Kategori | Sort-Object Count -Descending | ForEach-Object { Write-Host ("  {0,-22} {1,5} file" -f $_.Name, $_.Count) }

if (-not $Apply) {
    Write-Host ""
    Write-Host "CONTOH rencana (15 pertama):"
    $plan | Select-Object -First 15 | ForEach-Object { Write-Host ("  {0}`n    -> {1}" -f $_.From, $_.To) }
    Write-Host ""
    Write-Host "SIMULASI: belum ada file yang dipindah. Jika sudah benar, jalankan lagi dengan -Apply."
    return
}

# ---------- JALANKAN + LOG ----------
if (-not (Test-Path -LiteralPath $root)) { New-Item -ItemType Directory -Path $root | Out-Null }
$log = Join-Path $root ("_RapikanLog_{0}.csv" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$done = New-Object System.Collections.ArrayList
$failed = 0
try {
    foreach ($it in $plan) {
        try {
            $dir = Split-Path -Parent $it.To
            if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
            Move-Item -LiteralPath $it.From -Destination $it.To -ErrorAction Stop
            [void]$done.Add([pscustomobject]@{ From = $it.From; To = $it.To })
        } catch { $failed++; Write-Warning "Gagal (dilewati): $($it.From) - $($_.Exception.Message)" }
    }
} finally {
    if ($done.Count -gt 0) { $done | Export-Csv -LiteralPath $log -NoTypeInformation -Encoding UTF8 }
}
Write-Host ""
Write-Host "Selesai: $($done.Count) file dipindah, $failed gagal."
if ($done.Count -gt 0) {
    Write-Host "Log untuk membatalkan: $log"
    Write-Host "Batalkan dengan:  .\Rapikan-Folder.ps1 -Undo `"$log`""
}
