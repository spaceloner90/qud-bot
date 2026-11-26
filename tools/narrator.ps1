# Reads the voice channel (live/voice.log: only lines meant to be spoken, separate from the panel log)
# aloud, one line at a time. Speaks only while live/voice_on exists (F9 in the game, or
# python tools/voice.py on|off). If it falls behind, it skips to the newest lines so it stays current.
# Voice settings come from brain/voice.json ("speech": engine onecore|sapi, voice, rate), reread for
# every line, so they can be changed live. Keep this file ASCII: Windows PowerShell 5.1 reads BOM-less
# scripts as ANSI.
#   powershell -NoProfile -File tools/narrator.ps1
param([int]$MaxBacklog = 2)

$root = Split-Path -Parent $PSScriptRoot
$log = Join-Path $root "live\voice.log"
$flag = Join-Path $root "live\voice_on"
$cfgPath = Join-Path $root "brain\voice.json"

Add-Type -AssemblyName System.Speech
$sapi = New-Object System.Speech.Synthesis.SpeechSynthesizer

# OneCore voices (smoother than the old desktop ones) through the Windows Runtime API.
$onecore = $null
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
    $null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    $onecore = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
} catch { $onecore = $null }

function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }

function Settings {
    $s = @{ engine = "onecore"; voice = "Mark"; rate = 1.2 }
    try {
        $j = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($j.speech) {
            if ($j.speech.engine) { $s.engine = $j.speech.engine }
            if ($j.speech.voice) { $s.voice = $j.speech.voice }
            if ($j.speech.rate) { $s.rate = [double]$j.speech.rate }
        }
    } catch { }
    return $s
}

function Speak([string]$text) {
    $s = Settings
    if ($s.engine -eq "onecore" -and $onecore) {
        $v = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -like ("*" + $s.voice + "*") } | Select-Object -First 1
        if ($v) { $onecore.Voice = $v }
        $onecore.Options.SpeakingRate = [Math]::Max(0.5, [Math]::Min(3.0, $s.rate))
        $stream = Await ($onecore.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
        $reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
        $n = Await ($reader.LoadAsync([uint32]$stream.Size)) ([uint32])
        $bytes = New-Object byte[] $n
        $reader.ReadBytes($bytes)
        $ms = New-Object System.IO.MemoryStream(, $bytes)
        (New-Object System.Media.SoundPlayer($ms)).PlaySync()
    } else {
        $match = $sapi.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -like ("*" + $s.voice + "*") } | Select-Object -First 1
        if ($match) { $sapi.SelectVoice($match.VoiceInfo.Name) }
        $sapi.Rate = [int][Math]::Max(-10, [Math]::Min(10, ($s.rate - 1) * 5))
        $sapi.Speak($text)
    }
}

function Clean([string]$line) {
    $text = ($line -split "`t", 2)[-1]
    $text = $text -replace '^\* ', '' -replace '^!! ', '' -replace '\(\d+,\d+\)', '' -replace '[\u2500-\u259F]', ' '
    return ($text -replace '\s+', ' ').Trim()
}

# New text appended to a file since the last read (positions kept per file).
$positions = @{}
function NewText([string]$path) {
    if (-not (Test-Path $path)) { return "" }
    $len = (Get-Item $path).Length
    if (-not $positions.ContainsKey($path)) { $positions[$path] = $len; return "" }   # start from now
    if ($len -lt $positions[$path]) { $positions[$path] = 0 }
    if ($len -eq $positions[$path]) { return "" }
    $fs = [System.IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
    try {
        $fs.Seek($positions[$path], 'Begin') | Out-Null
        $reader = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::UTF8)
        $text = $reader.ReadToEnd()
        $positions[$path] = $fs.Position
    } finally { $fs.Close() }
    return $text
}

# The panel log is not read aloud, except the mod's run started/stopped notes: a useful signal
# (the user, 2026-11-24).
$panelLog = Join-Path $root "live\narration.log"
function RunNotes([string]$text) {
    $out = @()
    foreach ($l in ($text -split "`n")) {
        $t = ($l -split "`t", 2)[-1].Trim()
        if ($t -like "Bot: run started*") { $out += "Bot running." }
        elseif ($t -like "Bot stopped:*") { $out += ("Bot stopped. " + ($t -replace '^Bot stopped:\s*', '')) }
    }
    return $out
}

$null = NewText $log; $null = NewText $panelLog
while ($true) {
    Start-Sleep -Milliseconds 400
    $new = NewText $log
    $notes = RunNotes (NewText $panelLog)
    if (-not (Test-Path $flag)) { continue }   # muted: keep up with the files, say nothing
    $lines = @($notes) + @($new -split "`n" | Where-Object { $_.Trim() })
    if ($lines.Count -gt $MaxBacklog) { $lines = $lines[-$MaxBacklog..-1] }
    foreach ($l in $lines) {
        $t = Clean $l
        if ($t) { try { Speak $t } catch { } }
        if (-not (Test-Path $flag)) { break }
    }
}
