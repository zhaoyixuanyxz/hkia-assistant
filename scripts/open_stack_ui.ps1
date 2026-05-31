$ErrorActionPreference = 'SilentlyContinue'
$url = 'http://127.0.0.1:3000/'
$candidates = @(
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
foreach ($exe in $candidates) {
  if (Test-Path -LiteralPath $exe) {
    Start-Process -FilePath $exe -ArgumentList "--app=$url"
    exit 0
  }
}
Start-Process $url
exit 0
