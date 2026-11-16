<#
  Ironhold for Windows 10/11 - installs one variant (wallpapers, accent color, dark mode, cursor scheme)
  for the current user only. No admin rights, no system files touched.

  Usage (from this folder):   powershell -ExecutionPolicy Bypass -File .\install.ps1
  Remove:                     powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall
#>
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'

$Here      = Split-Path -Parent $MyInvocation.MyCommand.Path
$Name      = '@@THEME_NAME@@'
$Dest      = Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Themes\$Name"
$ThemeFile = Join-Path $Dest "$Name.theme"
$SchemeKey = 'HKCU:\Control Panel\Cursors\Schemes'
$AppsKey   = 'HKCU:\AppEvents\Schemes\Apps'
$SoundId   = $Name -replace '[^A-Za-z0-9]', ''

function Get-SoundMap { Get-Content (Join-Path $Here 'sound-map.txt') | ForEach-Object { ,($_.Split('=', 2)) } }

if ($Uninstall) {
    Remove-ItemProperty -Path $SchemeKey -Name $Name -ErrorAction SilentlyContinue
    # Drop our sound scheme and point every event back at the Windows default sound
    foreach ($pair in Get-SoundMap) {
        $ev = Join-Path $AppsKey $pair[0]
        Remove-Item (Join-Path $ev $SoundId) -ErrorAction SilentlyContinue
        $def = (Get-ItemProperty -Path (Join-Path $ev '.Default') -ErrorAction SilentlyContinue).'(default)'
        if (Test-Path (Join-Path $ev '.Current')) { Set-Item -Path (Join-Path $ev '.Current') -Value "$def" }
    }
    Remove-Item "HKCU:\AppEvents\Schemes\Names\$SoundId" -ErrorAction SilentlyContinue
    Set-ItemProperty -Path 'HKCU:\AppEvents\Schemes' -Name '(default)' -Value '.Default'
    if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
    Write-Host "$Name removed. Pick another theme in Settings > Personalization > Themes."
    exit 0
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
foreach ($dir in 'Cursors', 'Wallpapers', 'Icons', 'Sounds') {
    Copy-Item -Recurse -Force (Join-Path $Here $dir) $Dest
}

# Fill absolute paths into the .theme template
$theme = Get-Content -Raw -Encoding UTF8 (Join-Path $Here "$Name.theme.in")
$theme = $theme.Replace('@@DIR@@', $Dest)
Set-Content -Path $ThemeFile -Value $theme -Encoding Unicode

# Register the cursor scheme so it shows up in Mouse Properties > Pointers
$roles = 'Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE',
         'SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person'
$map = @{}
foreach ($line in (Get-Content (Join-Path $Here 'cursor-map.txt'))) {
    $k, $v = $line.Split('=', 2); $map[$k] = Join-Path $Dest "Cursors\$v"
}
if (-not (Test-Path $SchemeKey)) { New-Item -Path $SchemeKey -Force | Out-Null }
Set-ItemProperty -Path $SchemeKey -Name $Name -Value (($roles | ForEach-Object { $map[$_] }) -join ',')

# Register the sound scheme so it shows up in Sound > Sounds > Sound Scheme
$names = "HKCU:\AppEvents\Schemes\Names\$SoundId"
New-Item -Path $names -Force | Out-Null
Set-Item -Path $names -Value $Name
foreach ($pair in Get-SoundMap) {
    $key = Join-Path (Join-Path $AppsKey $pair[0]) $SoundId
    New-Item -Path $key -Force | Out-Null
    Set-Item -Path $key -Value (Join-Path $Dest "Sounds\$($pair[1])")
}

Write-Host "Installed to $Dest - applying theme..."
Start-Process $ThemeFile
