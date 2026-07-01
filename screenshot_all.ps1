$ErrorActionPreference = "Stop"
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$outDir = "c:\Users\WH\Desktop\gonghangbei\frontend_v3"
$pages = @("overview", "data", "risk", "loan", "monitor")

# 清理
Remove-Item "$outDir\screenshot-*.png" -ErrorAction SilentlyContinue

# 用 chrome devtools protocol 的简化方法: --screenshot 参数
foreach ($p in $pages) {
    $out = "$outDir\screenshot-$p.png"
    $hash = "#$p"
    $url = "http://127.0.0.1:8003/$hash"
    Write-Host "Capturing $p ($url)..."
    # Chrome --screenshot 模式不支持 hash, 用 javascript 触发
    $tempHtml = "$outDir\_$p.html"
    @"
<!doctype html><html><head><meta http-equiv="refresh" content="0;url=$url"></head><body></body></html>
"@ | Set-Content -Path $tempHtml -Encoding UTF8

    $args = @(
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--window-size=1440,900",
        "--screenshot=`"$out`"",
        "--virtual-time-budget=15000",
        "--run-all-compositor-stages-before-draw",
        "`"$url`""
    )
    & $chrome $args 2>&1 | Out-Null
    if (Test-Path $out) {
        $size = (Get-Item $out).Length
        Write-Host "  -> $out ($size bytes)" -ForegroundColor Green
    } else {
        Write-Host "  -> FAILED" -ForegroundColor Red
    }
    Remove-Item $tempHtml -ErrorAction SilentlyContinue
}

Write-Host "Done."
Get-ChildItem "$outDir\screenshot-*.png" | Select-Object Name, Length
