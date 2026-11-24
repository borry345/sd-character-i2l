# Rerun See-through with different seeds until a tag layer has enough pixels.
# Usage: tools\seed_search.ps1 -Src miku_chibi_sprite.png -OutRoot seethrough_test\miku_seed -Tag headwear -MinPx 8000 -Seeds 0,1,2,3
param(
  [Parameter(Mandatory)][string]$Src,
  [Parameter(Mandatory)][string]$OutRoot,
  [string]$Tag = 'headwear',
  [int]$MinPx = 8000,
  [int[]]$Seeds = @(0, 1, 2, 3, 4, 5, 6, 7),
  [string[]]$Extra = @('--no_group_offload', '--tblr_split'),
  [int]$HeadGrow = 0
)
$root = if ($env:I2L_ROOT) { $env:I2L_ROOT } else { Split-Path $PSScriptRoot -Parent }  # i2l folder (tools/..)
$py = @("$root\env\Scripts\python.exe", "$root\env\python.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1  # venv / conda
$name = [IO.Path]::GetFileNameWithoutExtension($Src)
$results = @()
foreach ($s in $Seeds) {
  $out = "${OutRoot}$s"
  if (-not (Test-Path "$out\$name\$Tag.png")) {
    & "$root\tools\run_seethrough.ps1" -Src $Src -OutDir $out -Extra ($Extra + @('--seed', "$s")) -HeadGrow $HeadGrow | Select-Object -First 1
  }
  $px = & $py -c "import numpy as np,sys;from PIL import Image;print(int((np.array(Image.open(sys.argv[1]).convert('RGBA'))[...,3]>15).sum()))" "$out\$name\$Tag.png"
  $line = "seed=$s $Tag=${px}px  -> $out"
  $line
  $results += $line
  if ([int]$px -ge $MinPx) { "FOUND seed=$s"; break }
}
$results | Out-File -Encoding utf8 "${OutRoot}_search.txt"
