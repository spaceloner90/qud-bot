# Checks the mod compiles (with the C# 5 compiler that ships with Windows, against the game's DLLs),
# then copies the source into the game's Mods folder. The game compiles mods itself at startup,
# so changes take effect on the next game start. Its own compile log is build_log.txt.
param(
    [string]$GameDir = "",
    [switch]$CheckOnly
)
if (-not $GameDir) { $GameDir = & (Join-Path $PSScriptRoot "game_dir.ps1") }


$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot
$managed = Join-Path $GameDir "CoQ_Data\Managed"
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$check = Join-Path $env:TEMP "QudBot_check.dll"

$refs = Get-ChildItem $managed -Filter *.dll | Where-Object {
    $_.Name -match '^(mscorlib|netstandard|System|System\.Core|UnityEngine|UnityEngine\.CoreModule|UnityEngine\.InputLegacyModule|UnityEngine\.IMGUIModule|UnityEngine\.TextRenderingModule|Unity\.InputSystem|Assembly-CSharp|0Harmony)\.dll$'
} | ForEach-Object { "/reference:$($_.FullName)" }

# Invisible control characters compile fine but can break at runtime (a "\b" in a path once became a
# backspace and froze the game on its loading screen), so refuse them.
foreach ($f in Get-ChildItem (Join-Path $proj "mod\*.cs")) {
    $text = [System.IO.File]::ReadAllText($f.FullName)
    $m = [regex]::Match($text, '[\x00-\x08\x0B\x0C\x0E-\x1F]')
    if ($m.Success) {
        $line = ($text.Substring(0, $m.Index) -split "`n").Count
        throw "Control character 0x$('{0:x2}' -f [int][char]$m.Value) in $($f.Name) line $line"
    }
}

& $csc /nologo /noconfig /nostdlib+ /target:library /warn:1 "/out:$check" @refs (Join-Path $proj "mod\*.cs")
if ($LASTEXITCODE -ne 0) { throw "Compile check failed" }
"Compile check passed"
if ($CheckOnly) { exit 0 }

$mods = Join-Path $env:USERPROFILE "AppData\LocalLow\Freehold Games\CavesOfQud\Mods\QudBot"
New-Item -ItemType Directory -Force $mods | Out-Null
Get-ChildItem $mods -File | Remove-Item
foreach ($cs in Get-ChildItem (Join-Path $proj "mod\*.cs")) {
    # The repo path goes into the installed copy only, so the repo itself holds no machine path.
    $text = [System.IO.File]::ReadAllText($cs.FullName).Replace("__QUDBOT_ROOT__", $proj)
    [System.IO.File]::WriteAllText((Join-Path $mods $cs.Name), $text, (New-Object System.Text.UTF8Encoding($false)))
}
Copy-Item (Join-Path $proj "mod\manifest.json") $mods
"Installed to $mods (takes effect next game start):"
Get-ChildItem $mods | ForEach-Object { "  $($_.Name)" }
