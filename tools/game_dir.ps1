# The game's install folder ("...\game", holding CoQ_Data). Machine-specific, so it isn't in the repo:
# local\paths.json {"game_dir": "..."} (git-ignored), else $env:QUD_GAME_DIR, else the usual Steam folder.
$local = Join-Path (Split-Path -Parent $PSScriptRoot) "local\paths.json"
if (Test-Path $local) {
    $dir = (Get-Content $local -Raw | ConvertFrom-Json).game_dir
    if ($dir) { return $dir }
}
if ($env:QUD_GAME_DIR) { return $env:QUD_GAME_DIR }
return "C:\Program Files (x86)\Steam\steamapps\common\Caves of Qud"
