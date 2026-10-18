param(
  [string]$LaunchUri = ""
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $env:LOCALAPPDATA "ApolloHarness"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$launcherLog = Join-Path $logDir "launcher.log"
$healthUrl = "http://127.0.0.1:8765/health"

function Write-LauncherLog([string]$Message) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] " + $Message
  Add-Content -LiteralPath $launcherLog -Value $line -Encoding UTF8
}

try {
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  $candidates = @()
  if ($env:APOLLO_HARNESS_HOME) { $candidates += $env:APOLLO_HARNESS_HOME }
  $candidates += (Resolve-Path (Join-Path $scriptDir "..")).Path
  $candidates += (Join-Path $env:USERPROFILE "apollo-planning-course\harness")
  $candidates += (Join-Path $env:USERPROFILE "Documents\apollo-planning-course\harness")
  $candidates += "C:\apollo-planning-course\harness"

  $harness = $null
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path (Join-Path $candidate "apollo_claw\__main__.py"))) {
      $harness = (Resolve-Path $candidate).Path
      break
    }
  }
  if (-not $harness) {
    throw "找不到 Apollo_Harness 目录。请设置 APOLLO_HARNESS_HOME 环境变量。"
  }

  if (-not $env:APOLLO_CLAW_SKILLS_DIR -and (Test-Path (Join-Path $harness "skills"))) {
    $env:APOLLO_CLAW_SKILLS_DIR = (Join-Path $harness "skills")
    Write-LauncherLog "使用包内技能目录: $env:APOLLO_CLAW_SKILLS_DIR"
  }

  $query = ""
  if ($LaunchUri) {
    try { $query = ([System.Uri]$LaunchUri).Query } catch { Write-LauncherLog "无法解析 URI: $LaunchUri" }
  }
  $panelUrl = "http://127.0.0.1:8765/" + $query

  $alive = $false
  try {
    $health = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 2 -UseBasicParsing
    $alive = ($health.StatusCode -eq 200)
  } catch { }

  if (-not $alive) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $python) {
      throw "找不到 Python。请先安装 Python 3.9+ 并加入 PATH。"
    }

    $stdout = Join-Path $logDir "harness.stdout.log"
    $stderr = Join-Path $logDir "harness.stderr.log"
    Write-LauncherLog "启动 Harness: $($python.Source) -m apollo_claw serve --port 8765 (cwd=$harness)"
    $process = Start-Process -FilePath $python.Source -ArgumentList @("-m", "apollo_claw", "serve", "--port", "8765") -WorkingDirectory $harness -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr

    for ($i = 0; $i -lt 40; $i++) {
      Start-Sleep -Milliseconds 500
      try {
        $health = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 2 -UseBasicParsing
        if ($health.StatusCode -eq 200) { $alive = $true; break }
      } catch { }
    }
    if (-not $alive) {
      throw "Harness 启动超时。请查看 $stderr"
    }
  }

  Write-LauncherLog "打开 $panelUrl"
  Start-Process $panelUrl
} catch {
  Write-LauncherLog ("ERROR: " + $_.Exception.Message)
  try {
    Add-Type -AssemblyName PresentationFramework
    $message = "Apollo_Harness 启动失败：" + [Environment]::NewLine + [Environment]::NewLine + $_.Exception.Message + [Environment]::NewLine + [Environment]::NewLine + "日志：" + [Environment]::NewLine + $launcherLog
    [System.Windows.MessageBox]::Show($message, "Apollo_Harness", "OK", "Error") | Out-Null
  } catch { }
}
