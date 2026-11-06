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

  # 4) Batalkan: kembalikan semua file ke tempat asal memakai file log:
  .\Rapikan-Folder.ps1 -Undo "C:\Users\Nama\Downloads\_RapikanLog_20261106-140000.csv"
#>
[CmdletBinding()]
param(
    [string]$Path,
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
if (-not $Path) { throw "Isi -Path dengan folder yang mau dirapikan. Contoh: -Path `"C:\Users\Nama\Downloads`"" }
if (-not (Test-Path -LiteralPath $Path -PathType Container)) { throw "Folder tidak ditemukan: $Path" }
$root = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).ProviderPath)
if ($root.Length -gt 1) { $root = $root.TrimEnd($sep) }

# Tolak folder sistem/berbahaya
$blocked = @($env:windir, $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData)
$pr = [IO.Path]::GetPathRoot($root)
if ($root.TrimEnd($sep) -eq $pr.TrimEnd($sep)) { throw "Ditolak: jangan rapikan akar drive ($root)." }
foreach ($b in $blocked) { if (Under $root $b) { throw "Ditolak: folder sistem/program ($root)." } }
if ($env:USERPROFILE -and (Same $root $env:USERPROFILE.TrimEnd($sep))) { throw "Ditolak: pilih subfolder (Downloads, Documents, dst), bukan folder profil utama." }

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
$files = @(Get-ChildItem -LiteralPath $root -File -Recurse:$Recurse -ErrorAction SilentlyContinue)
$plan = New-Object System.Collections.ArrayList
$taken = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$skipped = 0
foreach ($f in $files) {
    $ext = $f.Extension.TrimStart('.').ToLowerInvariant()
    if (($f.Attributes -band ([IO.FileAttributes]::Hidden -bor [IO.FileAttributes]::System)) -ne 0 -or
        $skipName -contains $f.Name.ToLowerInvariant() -or $skipExt -contains $ext -or
        $f.Name -like '_RapikanLog_*.csv' -or $f.Name -like 'Rapikan-Folder*.ps1') { $skipped++; continue }

    $cat = 'Lainnya'
    if ($extToCat.ContainsKey($ext)) { $cat = $extToCat[$ext] }
    $parts = @()
    if ($By -eq 'Type' -or $By -eq 'TypeDate') { $parts += $cat }
    if ($By -eq 'Date' -or $By -eq 'TypeDate') { $parts += $f.LastWriteTime.ToString('yyyy-MM') }
    $destDir = $root
    foreach ($p in $parts) { $destDir = Join-Path $destDir $p }

    $dest = Join-Path $destDir $f.Name
    if (Same $dest $f.FullName) { $skipped++; continue }        # sudah rapi di tempatnya
    # nama kembar: tambahkan " (2)", " (3)", ...
    $n = 2
    $base = [IO.Path]::GetFileNameWithoutExtension($f.Name); $x = $f.Extension
    while ((Test-Path -LiteralPath $dest) -or $taken.Contains($dest)) {
        $dest = Join-Path $destDir ("{0} ({1}){2}" -f $base, $n, $x); $n++
    }
    [void]$taken.Add($dest)
    [void]$plan.Add([pscustomobject]@{ Kategori = $(if ($parts.Count) { $parts -join $sep } else { '.' }); From = $f.FullName; To = $dest })
}

if ($plan.Count -eq 0) { Write-Host "Tidak ada file yang perlu dirapikan di $root ($skipped dilewati)."; return }

Write-Host ""
Write-Host "Folder : $root"
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
