# Lists methods in Assembly-CSharp.dll whose IL loads a string matching -Pattern (ldstr).
# Static read with the game's Mono.Cecil; no game code runs.
param(
    [Parameter(Mandatory=$true)][string]$Pattern,
    [string]$GameDir = ""
)
if (-not $GameDir) { $GameDir = & (Join-Path $PSScriptRoot "game_dir.ps1") }

$managed = Join-Path $GameDir "CoQ_Data\Managed"
Add-Type -Path (Join-Path $managed "Trivial.Mono.Cecil.dll")
$module = [Trivial.Mono.Cecil.ModuleDefinition]::ReadModule((Join-Path $managed "Assembly-CSharp.dll"))
function Visit($t) {
    foreach ($m in $t.Methods) {
        if (-not $m.HasBody) { continue }
        foreach ($i in $m.Body.Instructions) {
            if ($i.OpCode.Name -eq "ldstr" -and $i.Operand -match $Pattern) {
                '{0}::{1}  "{2}"' -f $t.FullName, $m.Name, $i.Operand
            }
        }
    }
    foreach ($n in $t.NestedTypes) { Visit $n }
}
foreach ($t in $module.Types) { Visit $t }
