$ErrorActionPreference = 'SilentlyContinue'
$deadline = (Get-Date).AddMinutes(3)
$url = 'http://127.0.0.1:3000/'
while ((Get-Date) -lt $deadline) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
    if ($null -ne $r.StatusCode -and $r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
      exit 0
    }
  } catch { }
  Start-Sleep -Seconds 2
}
exit 1
