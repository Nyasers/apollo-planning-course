param(
  [switch]$NoStart,
  [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$harnessPath = (Resolve-Path (Join-Path $here "..")).Path
$launcherInstaller = Join-Path $harnessPath "scripts\install-harness-launcher.ps1"
$logDir = Join-Path $env:LOCALAPPDATA "ApolloHarness"
$logFile = Join-Path $logDir "oneclick-install.log"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Step([string]$message) {
  Write-Host $message -ForegroundColor Cyan
  Add-Content -LiteralPath $logFile -Value ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] " + $message) -Encoding UTF8
}

function Find-Python {
  foreach ($candidate in @("python", "py")) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $command) { continue }
    try {
      $versionArgs = if ($candidate -eq "py") { @("-3", "--version") } else { @("--version") }
      $versionText = & $command.Source @versionArgs 2>&1 | Out-String
      if ($versionText -match "Python\s+(\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 9)) {
          return @{ Version = $versionText.Trim() }
        }
      }
    } catch { }
  }
  return $null
}

try {
  Write-Step "Apollo Claw Harness 一键配置开始"
  Write-Step "Harness 目录: $harnessPath"
  $python = Find-Python
  if (-not $python) {
    throw "未找到 Python 3.9+。请先安装 Python 3.9 或更高版本，并勾选 Add Python to PATH。"
  }
  Write-Step "Python: $($python.Version)"
  if ($CheckOnly) {
    if (-not (Test-Path -LiteralPath $launcherInstaller)) {
      throw "Missing launcher installer: $launcherInstaller"
    }
    Write-Step "Preflight checks passed"
    Write-Host ""
    Write-Host "Check-only mode completed. No files or settings were changed." -ForegroundColor Green
    return
  }
  $envDir = Join-Path $HOME ".apollo-claw"
  New-Item -ItemType Directory -Force -Path $envDir | Out-Null
  $envFile = Join-Path $envDir ".env"
  if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath (Join-Path $harnessPath ".env.example") -Destination $envFile
    Write-Step "已创建本地配置: $envFile"
  } else {
    Write-Step "保留已有本地配置: $envFile"
  }
  if (-not (Test-Path -LiteralPath $launcherInstaller)) {
    throw "缺少启动器安装脚本: $launcherInstaller"
  }
  Write-Step "正在安装本地启动器并创建桌面快捷方式"
  & $launcherInstaller -HarnessPath $harnessPath
  Write-Step "启动器安装完成"
  Write-Step "一键配置完成"
  Write-Host ""
  Write-Host "下一步：" -ForegroundColor Green
  Write-Host "1. 回到首次使用向导，点击启动并打开 Harness" -ForegroundColor Yellow
  Write-Host "2. 在 Harness 中保存并测试 DeepSeek Key" -ForegroundColor Yellow
  Write-Host "3. 检查环境并启动 Apollo 仿真" -ForegroundColor Yellow
  Write-Host "4. 地址：https://apc.nyase.ru/lab/start.html" -ForegroundColor Yellow
} catch {
  Add-Content -LiteralPath $logFile -Value ("ERROR: " + $_.Exception.Message) -Encoding UTF8
  Write-Host ""
  Write-Host "一键配置失败：" -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor Red
  Write-Host "日志：$logFile" -ForegroundColor Yellow
  exit 1
}
