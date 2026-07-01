$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$out = "c:\Users\WH\Desktop\gonghangbei\frontend_v3\screenshot-overview.png"
$url = "http://127.0.0.1:8003/"
$args = @("--headless", "--disable-gpu", "--no-sandbox", "--window-size=1440,900", "--screenshot=`"$out`"", "--virtual-time-budget=25000", "`"$url`"")
Start-Process -FilePath $chrome -ArgumentList $args -Wait -NoNewWindow
Write-Host "Done. File exists:"
Test-Path $out
Get-Item $out | Select-Object Length
