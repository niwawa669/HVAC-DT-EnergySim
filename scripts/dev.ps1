<#
.SYNOPSIS
    本地一键启动：后端（FastAPI）+ 前端（Vite）。

.DESCRIPTION
    - 自动选择 Python 环境（优先 github_HVAC，其次 PATH 中的 python）
    - Windows 下自动设置 PYTHONIOENCODING=utf-8（算法层打印 emoji，GBK 控制台会崩）
    - 等后端端口就绪后再启动前端，避免首屏请求打空
    - Ctrl+C 退出时一并结束两个子进程

.EXAMPLE
    .\scripts\dev.ps1
    .\scripts\dev.ps1 -BackendOnly
    .\scripts\dev.ps1 -ApiPort 8001 -WebPort 5174
#>
[CmdletBinding()]
param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173,
    [string]$Python = "",
    [switch]$BackendOnly,
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$Root   = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root 'src\apiserver'
$WebDir = Join-Path $Root 'src\main'
$LogDir = Join-Path $Root 'data\logs'

function Write-Step($m) { Write-Host "[dev] $m" -ForegroundColor Cyan }
function Write-Warn($m) { Write-Host "[dev] $m" -ForegroundColor Yellow }
function Write-Err($m)  { Write-Host "[dev] $m" -ForegroundColor Red }

function Test-PortBusy {
    param([int]$Port)
    # 以系统连接表为准。不用 TcpClient 探测：某些环境会代理回环连接，
    # 导致任何端口都“连得上”，产生误判。
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
        if ($conn) { return $true }
        return $false
    } catch {
        # 查询本身失败时无法判断，按“空闲”处理；真正的冲突由 uvicorn/vite 的绑定失败暴露
        return $false
    }
}

if (-not (Test-Path $ApiDir)) { Write-Err "找不到后端目录: $ApiDir"; exit 1 }
if (-not $BackendOnly -and -not (Test-Path $WebDir)) { Write-Err "找不到前端目录: $WebDir"; exit 1 }
if (Test-PortBusy $ApiPort) { Write-Err "端口 $ApiPort 已被占用，请先停止占用进程或改用 -ApiPort"; exit 1 }
if (-not $BackendOnly -and (Test-PortBusy $WebPort)) { Write-Err "端口 $WebPort 已被占用，请先停止占用进程或改用 -WebPort"; exit 1 }

$candidates = @()
if ($Python) { $candidates += $Python }
$candidates += "D:\anaconda3\envs\github_HVAC\python.exe"
$pathPy = Get-Command python -ErrorAction SilentlyContinue
if ($pathPy) { $candidates += $pathPy.Source }

$Py = $null
foreach ($c in $candidates) {
    if ($c -and (Test-Path $c)) {
        # 不做输出重定向：某些受限环境禁止捕获原生进程的标准输出
        & $c -c "import sys"
        if ($LASTEXITCODE -eq 0) { $Py = $c; break }
    }
}
if (-not $Py) { Write-Err "未找到可用的 Python，请用 -Python 指定解释器路径"; exit 1 }
Write-Step "Python: $Py"

$probeFile = Join-Path $env:TEMP ("hvac_probe_" + [guid]::NewGuid().ToString("N") + ".txt")
$probeCode = "import importlib.util as u,pathlib;missing=[m for m in ['fastapi','uvicorn','torch','CoolProp'] if u.find_spec(m) is None];pathlib.Path(r'" + $probeFile + "').write_text(','.join(missing) or 'OK', encoding='utf-8')"
& $Py -c $probeCode
if (Test-Path $probeFile) {
    $pyCheck = (Get-Content $probeFile -Raw -Encoding UTF8).Trim()
    Remove-Item $probeFile -Force -ErrorAction SilentlyContinue
} else {
    $pyCheck = "UNKNOWN"
}
if ($pyCheck -eq "UNKNOWN") {
    Write-Warn "无法自动探测依赖（环境限制），继续尝试启动"
} elseif ($pyCheck -ne "OK") {
    Write-Err "该 Python 缺少依赖: $pyCheck"
    Write-Warn ("请执行: " + $Py + " -m pip install -r " + $ApiDir + "\requirements.txt")
    exit 1
}
Write-Step "依赖检查: OK"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$BackendOut = Join-Path $LogDir 'backend.out.log'
$BackendErr = Join-Path $LogDir 'backend.err.log'
Remove-Item $BackendOut, $BackendErr -ErrorAction SilentlyContinue

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

Write-Step "启动后端 http://127.0.0.1:$ApiPort ..."
$backendArgs = @("-m","uvicorn","app.main:app","--host","127.0.0.1","--port","$ApiPort")
$backend = Start-Process -FilePath $Py -ArgumentList $backendArgs -WorkingDirectory $ApiDir -PassThru -NoNewWindow -RedirectStandardOutput $BackendOut -RedirectStandardError $BackendErr

$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if ($backend.HasExited) { break }
    if (Test-PortBusy $ApiPort) { $ready = $true; break }
    # 双信号：端口未及时反映时，用 uvicorn 的启动日志兜底
    if ((Test-Path $BackendErr) -and (Select-String -Path $BackendErr -Pattern 'Application startup complete' -Quiet -ErrorAction SilentlyContinue)) {
        Start-Sleep -Milliseconds 500
        $ready = $true
        break
    }
}
if (-not $ready) {
    Write-Err "后端启动失败，日志：$BackendErr"
    if (Test-Path $BackendErr) { Get-Content $BackendErr -Tail 20 | ForEach-Object { Write-Err "  $_" } }
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
    exit 1
}
Write-Step "后端就绪（算法模型加载约 7 秒属正常）"
Write-Host "        API 文档: http://127.0.0.1:$ApiPort/docs"
Write-Host "        运行日志: $BackendOut"

$web = $null
if (-not $BackendOnly) {
    $nodeModules = Join-Path $WebDir "node_modules"
    if (-not $SkipInstall -and -not (Test-Path $nodeModules)) {
        Write-Step "首次运行，安装前端依赖（可能需要几分钟）..."
        Push-Location $WebDir
        try {
            & npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install 失败" }
        } finally { Pop-Location }
    }

    Write-Step "启动前端 http://localhost:$WebPort ..."
    $webArgs = @("run","dev","--","--port","$WebPort")
    $web = Start-Process -FilePath "npm.cmd" -ArgumentList $webArgs -WorkingDirectory $WebDir -PassThru -NoNewWindow

    $webReady = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        if ($web.HasExited) { break }
        if (Test-PortBusy $WebPort) { $webReady = $true; break }
    }
    if (-not $webReady) { Write-Warn "前端未在 30 秒内就绪，请检查上面的输出" }

    if ($ApiPort -ne 8000) {
        Write-Warn "注意：后端未使用默认端口 8000。前端有两处地址写死为 8000，需同步修改："
        Write-Warn "  1) src\main\.env.development 的 VITE_API_BASE_URL"
        Write-Warn "  2) src\main\src\views\SimulationView.vue 的 ws://localhost:8000（否则监控页收不到进度）"
    }

    Write-Host ""
    Write-Host "  ==========================================" -ForegroundColor Green
    Write-Host "   前端: http://localhost:$WebPort" -ForegroundColor Green
    Write-Host "   后端: http://127.0.0.1:$ApiPort/docs" -ForegroundColor Green
    Write-Host "   账号: admin / 123456" -ForegroundColor Green
    Write-Host "  ==========================================" -ForegroundColor Green
    Write-Host ""

    if (-not $NoBrowser) { Start-Process "http://localhost:$WebPort" | Out-Null }
}

try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($backend.HasExited) { Write-Err "后端已退出，日志见 $BackendErr"; break }
        if ($web -and $web.HasExited) { Write-Warn "前端已退出"; break }
    }
}
finally {
    Write-Step "正在停止子进程 ..."
    foreach ($p in @($web, $backend)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
    Write-Step "已停止"
}
