# Arabic status report for the BR film build (node make.mjs).
# Usage, from the promo folder:  powershell -ExecutionPolicy Bypass -File tools\status.ps1
# Writes out\status-report.txt and opens it in Notepad, where Arabic displays correctly.

$ErrorActionPreference = 'SilentlyContinue'
Set-Location (Split-Path $PSScriptRoot -Parent)
$R = New-Object System.Collections.Generic.List[string]
function Say([string]$s) { $R.Add($s) }
function Mmss([double]$s) { '{0}:{1:00}' -f [math]::Floor($s / 60), [math]::Floor($s % 60) }
function Dur([string]$f) {
  $d = & ffprobe -v error -show_entries format=duration -of csv=p=0 $f 2>$null
  if ($d) { [double]$d } else { $null }
}

Say ('تقرير فيلم BR  -  الساعة ' + (Get-Date -Format 'HH:mm:ss'))
Say '----------------------------------------'

# Tools
$missing = @()
foreach ($t in 'node', 'ffmpeg', 'ffprobe') { if (-not (Get-Command $t)) { $missing += $t } }
if (-not ((Get-Command python) -or (Get-Command py))) { $missing += 'python' }
if ($missing.Count) { Say ('⚠ برامج ناقصة لازم تنزلها: ' + ($missing -join ', ')) }
else { Say '✔ البرامج كلها موجودة (Node و Python و FFmpeg)' }

# GPU
$util = $null
$gpu = nvidia-smi --query-gpu=name,utilization.gpu --format=csv,noheader,nounits 2>$null
if ($gpu) {
  $parts = ($gpu | Select-Object -First 1).Split(',')
  $util = [int]$parts[1].Trim()
  Say ('✔ كرت الشاشة: ' + $parts[0].Trim() + '  -  استخدامه هسه: ' + $util + '%')
} else { Say '⚠ ما كدرت أقرا كرت الشاشة (أمر nvidia-smi مو موجود)' }

$running = @(Get-Process node, chrome, chromium, headless_shell, ffmpeg)
if ($env:BR_STATUS_IGNORE_PROCESSES) { $running = @() }  # for testing
$total = $null
if (Test-Path out\cues.json) { $total = (Get-Content out\cues.json -Raw | ConvertFrom-Json).duration }
$final = 'release\BR_promo_1080p.mp4'
$chunks = @(Get-ChildItem out\chunks\c*.mp4 | Sort-Object Name)
$done = @($chunks | Where-Object { Dur $_.FullName })
Say ''

if ((Test-Path $final) -and -not $running.Count) {
  $f = Get-Item $final
  Say '✅ الفيديو جاهز!'
  Say ('المكان: ' + $f.FullName)
  Say ('الطول: ' + (Mmss (Dur $f.FullName)) + '  -  الحجم: ' + [math]::Round($f.Length / 1MB, 1) + ' ميغابايت')
  Start-Process explorer.exe "/select,`"$($f.FullName)`""
}
elseif ($running.Count) {
  Say '⏳ الشغل ماشي هسه.'
  if (-not $total) { Say 'المرحلة 1 من 4: حساب توقيت المشاهد (ثواني).' }
  elseif (-not (Test-Path out\mix.wav)) { Say 'المرحلة 2 من 4: تجهيز الصوت والموسيقى (حوالي دقيقة).' }
  elseif (-not $chunks.Count -or $done.Count -lt $chunks.Count) {
    Say ('المرحلة 3 من 4: رسم الفيديو. خلص ' + $done.Count + ' من ' + [math]::Max($chunks.Count, 3) + ' أجزاء.')
    foreach ($c in $chunks) {
      $d = Dur $c.FullName
      $age = [math]::Round(((Get-Date) - $c.LastWriteTime).TotalSeconds)
      if ($d) { Say ('   ' + $c.Name + ': خلص (' + [math]::Round($d) + ' ثانية من الفيلم)') }
      else { Say ('   ' + $c.Name + ': ديترسم، حجمه ' + [math]::Round($c.Length / 1MB, 1) + ' ميغابايت، آخر تحديث قبل ' + $age + ' ثانية') }
      if (-not $d -and $age -gt 180) { Say '   ⚠ هذا الجزء ما تحدث من 3 دقايق، ممكن يكون معلك.' }
    }
    $mins = [math]::Round(((Get-Date) - (Get-Item out\mix.wav).LastWriteTime).TotalMinutes)
    Say ('   صارله ديرسم ' + $mins + ' دقيقة.')
    if ($util -ne $null -and $util -lt 15) { Say '⚠ كرت الشاشة شبه عاطل، يعني الرسم ديصير على المعالج وهذا أبطأ بهواية. دزلي هذا التقرير.' }
  }
  else { Say 'المرحلة 4 من 4: دمج الأجزاء والتصدير النهائي (كم دقيقة).' }
  Say ''
  Say 'شغّل هذا الأمر مرة ثانية بعد كم دقيقة حتى تشوف التقدم.'
}
else {
  Say '❌ الشغل واقف وما خلص.'
  if (-not $total) { Say 'وقف بالمرحلة 1 (حساب التوقيت).' }
  elseif (-not (Test-Path out\mix.wav)) { Say 'وقف بالمرحلة 2 (الصوت). غالباً مكتبات Python ناقصة: pip install numpy scipy' }
  elseif ($done.Count -lt [math]::Max($chunks.Count, 1)) { Say ('وقف بالمرحلة 3 (رسم الفيديو). خلص ' + $done.Count + ' من ' + $chunks.Count + ' أجزاء.') }
  else { Say 'وقف بالمرحلة 4 (الدمج النهائي).' }
  Say 'شغّل من جديد:  node make.mjs --gpu   وإذا طلع خطأ، دزلي آخر الأسطر اللي تطلع.'
}

$out = Join-Path (Get-Location) 'out\status-report.txt'
New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
[System.IO.File]::WriteAllLines($out, $R, (New-Object System.Text.UTF8Encoding $true))
Start-Process notepad.exe $out
'Report saved and opened in Notepad: ' + $out
