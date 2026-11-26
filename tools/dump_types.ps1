# Dumps types, fields, properties and method signatures from Qud's Assembly-CSharp.dll with the
# game's own copy of Mono.Cecil. Static read only: no game code runs and the install is not changed.
# Adapted from the Shogun Showdown project's dump_il.ps1 (reflection loading skipped half of Qud's types).
#
#   dump_types.ps1                          -> research\types.txt (signatures for every type)
#   dump_types.ps1 -IL -Filter 'XRLCore$'   -> research\il_<filter>.txt (signatures + IL, matching types only)
param(
    [string]$GameDir = "",
    [string]$Filter = "",
    [switch]$IL,
    [string]$OutDir = (Join-Path $PSScriptRoot "..\research")
)
if (-not $GameDir) { $GameDir = & (Join-Path $PSScriptRoot "game_dir.ps1") }


$managed = Join-Path $GameDir "CoQ_Data\Managed"
Add-Type -Path (Join-Path $managed "Trivial.Mono.Cecil.dll")
$module = [Trivial.Mono.Cecil.ModuleDefinition]::ReadModule((Join-Path $managed "Assembly-CSharp.dll"))

New-Item -ItemType Directory -Force $OutDir | Out-Null
$name = if ($IL) { "il_" + ($Filter -replace '[^A-Za-z0-9]+', '_') + ".txt" } else { "types.txt" }
$outPath = Join-Path ([System.IO.Path]::GetFullPath($OutDir)) $name
$w = New-Object System.IO.StreamWriter($outPath, $false)

function Write-Type($t) {
    if ($t.FullName -match "<") { return }
    if (-not $Filter -or $t.FullName -match $Filter) {
        $base = if ($t.BaseType) { $t.BaseType.Name } else { "" }
        $w.WriteLine("")
        $w.WriteLine("TYPE $($t.FullName) : $base")
        foreach ($f in $t.Fields) {
            if ($f.Name -match "<") { continue }
            $static = if ($f.IsStatic) { "static " } else { "" }
            $const = if ($f.HasConstant) { " = $($f.Constant)" } else { "" }
            $w.WriteLine("  F $static$($f.FieldType.Name) $($f.Name)$const")
        }
        foreach ($p in $t.Properties) { $w.WriteLine("  P $($p.PropertyType.Name) $($p.Name)") }
        foreach ($m in $t.Methods) {
            if ($m.Name -match "^<") { continue }
            $static = if ($m.IsStatic) { "static " } else { "" }
            $params = ($m.Parameters | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
            $w.WriteLine("  M $static$($m.ReturnType.Name) $($m.Name)($params)")
            if ($IL -and $m.HasBody) {
                foreach ($i in $m.Body.Instructions) {
                    $operand = ""
                    if ($null -ne $i.Operand) {
                        if ($i.Operand -is [Trivial.Mono.Cecil.Cil.Instruction]) { $operand = "IL_{0:x4}" -f $i.Operand.Offset }
                        else { $operand = $i.Operand.ToString() }
                    }
                    $w.WriteLine(("      IL_{0:x4} {1} {2}" -f $i.Offset, $i.OpCode.Name, $operand))
                }
            }
        }
    }
    foreach ($n in $t.NestedTypes) { Write-Type $n }
}

foreach ($t in $module.Types) { Write-Type $t }
$w.Close()
"Wrote $outPath, $([math]::Round((Get-Item $outPath).Length/1MB,1)) MB"
