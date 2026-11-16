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

# Apply every part directly through the Win32 APIs. Opening the .theme file alone is not reliable
# (it silently does nothing when launched from WSL, scripts, or with Spotlight wallpaper active).
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class IronholdNative {
  [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern bool SystemParametersInfo(uint action, uint param, string vparam, uint flags);
  [DllImport("user32.dll", SetLastError = true, EntryPoint = "SystemParametersInfoW")]
  public static extern bool SystemParametersInfoPtr(uint action, uint param, IntPtr vparam, uint flags);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)]
  public static extern IntPtr SendMessageTimeout(IntPtr hwnd, uint msg, UIntPtr w, string l, uint flags, uint timeout, out UIntPtr result);
}
"@
$SPIF = 3  # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
function Send-SettingChange([string]$area) {
    $r = [UIntPtr]::Zero
    [void][IronholdNative]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, $area, 2, 3000, [ref]$r)
}

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
    # Back to the built-in Windows cursors if ours are active
    $cur = 'HKCU:\Control Panel\Cursors'
    if ((Get-Item $cur).GetValue('') -eq $Name) {
        foreach ($role in 'Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE',
                          'SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person') {
            Set-ItemProperty $cur -Name $role -Value ''
        }
        Set-Item $cur -Value 'Windows Default'
        Set-ItemProperty $cur -Name 'Scheme Source' -Value 2 -Type DWord
        [void][IronholdNative]::SystemParametersInfoPtr(0x57, 0, [IntPtr]::Zero, $SPIF)
    }
    if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
    Write-Host "$Name removed (cursors and sounds reset). Pick another theme or wallpaper in Settings > Personalization."
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

# wallpaper (first file in the .theme)
$wall = ([regex]::Match($theme, '(?m)^Wallpaper=(.+)$')).Groups[1].Value.Trim()
Set-ItemProperty 'HKCU:\Control Panel\Desktop' -Name WallpaperStyle -Value '10'
Set-ItemProperty 'HKCU:\Control Panel\Desktop' -Name TileWallpaper -Value '0'
[void][IronholdNative]::SystemParametersInfo(0x14, 0, $wall, $SPIF)

# cursors
$cur = 'HKCU:\Control Panel\Cursors'
foreach ($role in $roles) { Set-ItemProperty $cur -Name $role -Value $map[$role] }
Set-Item $cur -Value $Name
Set-ItemProperty $cur -Name 'Scheme Source' -Value 1 -Type DWord
[void][IronholdNative]::SystemParametersInfoPtr(0x57, 0, [IntPtr]::Zero, $SPIF)

# sounds
foreach ($pair in Get-SoundMap) {
    $current = Join-Path (Join-Path $AppsKey $pair[0]) '.Current'
    New-Item -Path $current -Force | Out-Null
    Set-Item -Path $current -Value (Join-Path $Dest "Sounds\$($pair[1])")
}
Set-Item 'HKCU:\AppEvents\Schemes' -Value $SoundId

# dark mode + accent color (from the .theme's ColorizationColor=0XAARRGGBB)
$pers = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
Set-ItemProperty $pers -Name AppsUseLightTheme -Value 0 -Type DWord
Set-ItemProperty $pers -Name SystemUsesLightTheme -Value 0 -Type DWord
$m = [regex]::Match($theme, 'ColorizationColor=0X([0-9A-F]{2})([0-9A-F]{2})([0-9A-F]{2})([0-9A-F]{2})')
if ($m.Success) {
    $r, $g, $b = (2..4 | ForEach-Object { [Convert]::ToInt32($m.Groups[$_].Value, 16) })
    # DWORDs above 0x7FFFFFFF must be passed as their signed Int32 bit pattern
    $toDword = { param($hex) [BitConverter]::ToInt32([BitConverter]::GetBytes([Convert]::ToUInt32($hex, 16)), 0) }
    $argb = & $toDword ("FF{0:X2}{1:X2}{2:X2}" -f $r, $g, $b)
    $abgr = & $toDword ("FF{0:X2}{1:X2}{2:X2}" -f $b, $g, $r)
    # 8-entry palette, light -> dark, as Windows 11 expects (RGBA bytes)
    $palette = New-Object byte[] 32
    $shades = 1.6, 1.35, 1.15, 1.0, 0.8, 0.6, 0.42, 0.3
    for ($i = 0; $i -lt 8; $i++) {
        $k = $shades[$i]
        $palette[$i * 4]     = [byte][Math]::Min(255, [int]($r * $k))
        $palette[$i * 4 + 1] = [byte][Math]::Min(255, [int]($g * $k))
        $palette[$i * 4 + 2] = [byte][Math]::Min(255, [int]($b * $k))
    }
    $acc = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Accent'
    if (-not (Test-Path $acc)) { New-Item $acc -Force | Out-Null }
    Set-ItemProperty $acc -Name AccentPalette -Value $palette -Type Binary
    Set-ItemProperty $acc -Name AccentColorMenu -Value $abgr -Type DWord
    Set-ItemProperty $acc -Name StartColorMenu -Value $abgr -Type DWord
    $dwm = 'HKCU:\Software\Microsoft\Windows\DWM'
    Set-ItemProperty $dwm -Name AccentColor -Value $abgr -Type DWord
    Set-ItemProperty $dwm -Name ColorizationColor -Value $argb -Type DWord
    Set-ItemProperty $dwm -Name ColorizationAfterglow -Value $argb -Type DWord
}
Send-SettingChange 'ImmersiveColorSet'
Send-SettingChange 'WindowsThemeElement'

Write-Host "Applied: wallpaper, cursors, sounds, dark mode and accent color."
Write-Host "Theme file (for Settings > Personalization > Themes): $ThemeFile"
