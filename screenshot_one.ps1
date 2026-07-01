$ErrorActionPreference = "Stop"
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$outDir = "c:\Users\WH\Desktop\gonghangbei\frontend_v3"
$out = "$outDir\screenshot-overview.png"
$url = "http://127.0.0.1:8003/"

# 增加 virtual-time-budget 到 30s, 让所有 API 跑完
$args = @(
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--hide-scrollbars",
    "--window-size=1440,900",
    "--screenshot=`"$out`"",
    "--virtual-time-budget=30000",
    "--run-all-compositor-stages-before-draw",
    "`"$url`""
)
& $chrome $args 2>&1 | Out-Null
if (Test-Path $out) {
    Write-Host "OK: $((Get-Item $out).Length) bytes"
} else {
    Write-Host "FAIL"
}
