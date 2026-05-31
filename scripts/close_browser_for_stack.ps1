$ErrorActionPreference = 'Continue'
Write-Host '[stack] Looking for Edge/Chrome/Firefox processes whose command line mentions localhost:3000...'
$targets = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
  $base = ($_.Name -replace '\.exe$', '')
  ($base -match '^(msedge|chrome|firefox)$') -and (
    ($_.CommandLine -match 'localhost:3000') -or ($_.CommandLine -match '127\.0\.0\.1:3000')
  )
}
if (-not $targets) {
  Write-Host '[stack] No matching launcher processes found. If the page is still open, close that tab manually.'
  exit 0
}
$targets | ForEach-Object {
  try {
    Stop-Process -Id $_.ProcessId -Force
    Write-Host ("[stack] Stopped {0} (PID={1})" -f $_.Name, $_.ProcessId)
  } catch {
    Write-Host ("[stack] Skip {0} (PID={1})" -f $_.Name, $_.ProcessId)
  }
}
