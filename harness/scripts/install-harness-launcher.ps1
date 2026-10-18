param(
  [string]$HarnessPath
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $HarnessPath) {
  $HarnessPath = (Resolve-Path (Join-Path $here "..")).Path
}
$launcher = Join-Path $HarnessPath "scripts\start-harness.ps1"
if (-not (Test-Path -LiteralPath $launcher)) {
  throw "找不到启动脚本：$launcher"
}
$launcher = (Resolve-Path -LiteralPath $launcher).Path
$HarnessPath = (Resolve-Path -LiteralPath $HarnessPath).Path

$protocolKey = "HKCU:\Software\Classes\apollo-harness"
New-Item -Path $protocolKey -Force | Out-Null
New-ItemProperty -Path $protocolKey -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
Set-Item -Path $protocolKey -Value "Apollo_Harness local launcher"

$iconKey = Join-Path $protocolKey "DefaultIcon"
New-Item -Path $iconKey -Force | Out-Null
Set-Item -Path $iconKey -Value "powershell.exe,0"

$commandKey = Join-Path $protocolKey "shell\open\command"
New-Item -Path $commandKey -Force | Out-Null
$command = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '" "%1"'
Set-Item -Path $commandKey -Value $command

$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "启动 Apollo_Harness.lnk"
$shortcut = $ws.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '"'
$shortcut.WorkingDirectory = $HarnessPath
$shortcut.Description = "启动本地 Apollo_Harness 并打开实验台"
$shortcut.Save()

Write-Host "已注册 apollo-harness:// 协议"
Write-Host "启动脚本：$launcher"
Write-Host "桌面快捷方式：$shortcutPath"
Write-Host "现在可以回到课程网页点击“启动并打开本地 Harness”。"
