# Còpia de seguretat del fitxer SQLite d’AtempoSports (Windows).
# Ús: .\scripts\backup_sqlite.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Db = if ($env:ATEMPO_DB_PATH) { $env:ATEMPO_DB_PATH } else { Join-Path $Root "data\atempo.db" }
$DestDir = if ($env:ATEMPO_BACKUP_DIR) { $env:ATEMPO_BACKUP_DIR } else { Join-Path $Root "data\backups" }
$Keep = if ($env:ATEMPO_BACKUP_KEEP) { [int]$env:ATEMPO_BACKUP_KEEP } else { 14 }

if (-not (Test-Path $Db)) {
    Write-Error "No trobo la base de dades: $Db"
}

New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$dest = Join-Path $DestDir "atempo_$stamp.db"
Copy-Item -Path $Db -Destination $dest -Force
Write-Host "Backup: $dest"

$old = Get-ChildItem -Path $DestDir -Filter "atempo_*.db" | Sort-Object LastWriteTime -Descending
if ($old.Count -gt $Keep) {
    $old | Select-Object -Skip $Keep | Remove-Item -Force
}
