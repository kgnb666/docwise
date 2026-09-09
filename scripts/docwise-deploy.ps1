#Requires -Version 5.1
<#
通用 Docker Compose 一键部署脚本（Windows / PowerShell）

一个脚本部署任意项目：打包 -> scp 上传 -> 服务器解压 -> compose 重建重启 -> 健康检查 -> 外网验证。
项目差异（服务器、端口、健康检查路径、容器名等）通过 deploy-config.json 配置，脚本本身不用改。

用法：
  powershell -ExecutionPolicy Bypass -File .\docwise-deploy.ps1              # 用默认值 / 项目自带配置
  powershell -ExecutionPolicy Bypass -File .\docwise-deploy.ps1 -Config xxx.json
  powershell -ExecutionPolicy Bypass -File .\docwise-deploy.ps1 -Server 1.2.3.4 -Port 9000

取值优先级：命令行参数 > deploy-config.json > 内置默认值。
配置模板见同目录 deploy-config.example.json（复制为 deploy-config.json 后修改）。

安全说明：
  - 打包会自动排除 .env 之外的大目录（node_modules / .venv / data / logs 等），
    其中 data 默认排除是为了不覆盖服务器上的数据卷；如项目确实需要随包传数据，在 extraExcludes 里移除该项并自行评估。
  - backend/.env（API Key）会随包上传，线上运行需要，请确认服务器是可信环境。
#>

[CmdletBinding()]
param(
    [string]$Server = "",
    [string]$User = "",
    [string]$SshKey = "",
    [string]$ServerDir = "",
    [int]$Port = 0,
    [string]$ProjectDir = "",
    [string]$Config = "",
    [string]$HealthPath = "",
    [string]$ComposeFile = "",
    [string]$BackendContainer = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function First([string]$a, $b, [string]$def) {
    if ($a) { return $a }
    if ($b) { return [string]$b }
    return $def
}

function Step($n, $msg) {
    Write-Host ""
    Write-Host "[$n] $msg" -ForegroundColor Cyan
}

# ---------- 1. 定位项目目录（参数 > 脚本所在位置探测） ----------
if (-not $ProjectDir) {
    if (Test-Path (Join-Path $scriptDir "docker-compose.yml")) {
        $ProjectDir = $scriptDir
    } elseif (Test-Path (Join-Path $scriptDir "..\docker-compose.yml")) {
        $ProjectDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
    }
}

# ---------- 2. 加载配置文件（-Config > 项目目录 > 脚本目录） ----------
$configPath = ""
if ($Config) {
    if (-not (Test-Path $Config)) { throw "找不到配置文件：$Config" }
    $configPath = $Config
} elseif ($ProjectDir -and (Test-Path (Join-Path $ProjectDir "deploy-config.json"))) {
    $configPath = Join-Path $ProjectDir "deploy-config.json"
} elseif (Test-Path (Join-Path $scriptDir "deploy-config.json")) {
    $configPath = Join-Path $scriptDir "deploy-config.json"
}
$cfg = @{}
if ($configPath) {
    $cfg = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "使用配置文件：$configPath" -ForegroundColor DarkGray
}

# ---------- 3. 项目目录兜底（配置 > 默认 DocWise 路径） ----------
if (-not $ProjectDir) {
    if ($cfg.projectDir) {
        $ProjectDir = [string]$cfg.projectDir
    } else {
        $ProjectDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
    }
}
if (-not (Test-Path (Join-Path $ProjectDir "docker-compose.yml"))) {
    throw "找不到项目根目录（缺 docker-compose.yml）：$ProjectDir（可用 -ProjectDir 指定）"
}

# ---------- 4. 解析最终配置：参数 > 配置文件 > 必需项校验 ----------
$Server = First $Server $cfg.server ""
$User = First $User $cfg.user "root"
$SshKey = First $SshKey $cfg.sshKey ""
$ServerDir = First $ServerDir $cfg.serverDir "/root/docwise"

if (-not $Server) {
    throw "未配置目标服务器 IP。请通过 -Server 参数传入，或在 scripts/deploy-config.json 中配置 'server'。"
}
if (-not $SshKey) {
    throw "未配置 SSH 私钥路径。请通过 -SshKey 参数传入，或在 scripts/deploy-config.json 中配置 'sshKey'。"
}
if ($Port -le 0) { $Port = if ($cfg.port) { [int]$cfg.port } else { 8080 } }
$HealthPath = First $HealthPath $cfg.healthPath "/api/health"
$ComposeFile = First $ComposeFile $cfg.composeFile "docker-compose.yml"
$BackendContainer = First $BackendContainer $cfg.backendContainer "docwise-backend"

# 打包排除项：内置安全集 + 配置里的 extraExcludes
$builtinExcludes = @(
    ".git", ".venv", "node_modules", ".npm-cache", "dist", ".tmp", "logs", "data",
    ".pytest_cache", ".ruff_cache", "__pycache__", "*.pyc",
    "vite.config.local.ts", "tsconfig.tsbuildinfo",
    "docwise-deploy.ps1", "docwise-deploy.cmd",
    "deploy-config.json", "deploy-config.example.json", "*.tar.gz"
)
$excludes = @()
foreach ($e in ($builtinExcludes + @($cfg.extraExcludes))) {
    if ($e) { $excludes += "--exclude=$e" }
}

if (-not (Test-Path $SshKey)) {
    throw "找不到 SSH 密钥：$SshKey（可用 -SshKey 或配置 sshKey 指定）"
}
foreach ($cmd in @("tar", "scp", "ssh")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "缺少命令：$cmd（Windows 需启用 OpenSSH 客户端）"
    }
}

Write-Host "项目目录：$ProjectDir" -ForegroundColor DarkGray
Write-Host "目标服务器：${User}@${Server}  ->  $ServerDir  （端口 $Port）" -ForegroundColor DarkGray
Write-Host "健康检查：http://localhost:${Port}${HealthPath}" -ForegroundColor DarkGray

# ---------- 5. 本地打包 ----------
Step "1/5" "打包代码（排除 venv/node_modules/日志/数据等）..."
$tarPath = Join-Path $env:TEMP "docwise-deploy.tar.gz"
Remove-Item $tarPath -ErrorAction SilentlyContinue
& tar -czf $tarPath @excludes -C $ProjectDir .
if ($LASTEXITCODE -ne 0) { throw "本地打包失败（tar 退出码 $LASTEXITCODE）" }
$sizeMB = [math]::Round((Get-Item $tarPath).Length / 1MB, 2)
Write-Host "  打包完成：$sizeMB MB"

# ---------- 6. 上传 ----------
Step "2/5" "上传到 ${User}@${Server} ..."
scp -i $SshKey $tarPath "${User}@${Server}:/root/docwise-deploy.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "上传失败（scp 退出码 $LASTEXITCODE）" }
Write-Host "  上传完成"

# ---------- 7. 服务器解压 + 修正端口 + 重建启动 + 健康检查 ----------
Step "3/5" "服务器解压、修正端口映射并重建启动容器..."
$remoteFile = Join-Path $env:TEMP "docwise-deploy-remote.sh"
$remote = @"
#!/usr/bin/env bash
set -e
mkdir -p $ServerDir
tar -xzf /root/docwise-deploy.tar.gz -C $ServerDir
rm -f /root/docwise-deploy.tar.gz
# 本地 compose 若映射 80 且目标端口不是 80，则统一改成 $Port（避免服务器 80 被占）
sed -i 's|"80:80"|"${Port}:80"|' $ServerDir/$ComposeFile
cd $ServerDir
docker compose up --build -d
sleep 5
curl -s -o /dev/null -w '%{http_code}' -m 15 http://localhost:${Port}${HealthPath} | grep -qx 200 && echo HEALTH_OK || echo HEALTH_FAIL
"@
# 注意：不要用管道把脚本喂给 ssh 的 stdin——PowerShell 5.1 会注入 UTF-8 BOM，
# 导致远端 bash 首行报 "command not found"。写成无 BOM 文件再 scp 过去执行。
[System.IO.File]::WriteAllText($remoteFile, $remote, (New-Object System.Text.UTF8Encoding $false))
scp -i $SshKey $remoteFile "${User}@${Server}:/root/docwise-deploy-remote.sh"
if ($LASTEXITCODE -ne 0) { throw "上传部署脚本失败（scp 退出码 $LASTEXITCODE）" }
$result = ssh -i $SshKey "${User}@${Server}" "bash /root/docwise-deploy-remote.sh"
if ($LASTEXITCODE -ne 0) { throw "服务器执行失败（SSH 退出码 $LASTEXITCODE）" }
if ($result -match "HEALTH_OK") {
    Write-Host "  后端健康检查通过"
} else {
    throw "服务器健康检查未通过：$result"
}
Remove-Item $remoteFile -ErrorAction SilentlyContinue

# ---------- 8. 外网验证 ----------
Step "4/5" "外网验证 http://${Server}:${Port} ..."
$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if ($curl) {
    # PS 5.1 的 Invoke-WebRequest 偶发兼容问题，优先用系统自带的 curl.exe
    $pageCode = & curl.exe -s -o NUL -w "%{http_code}" -m 15 "http://${Server}:${Port}/"
    if ($pageCode -eq "200") {
        Write-Host "  外网页面访问正常（HTTP 200）"
    } else {
        Write-Warning "  外网状态码异常：$pageCode"
    }
} else {
    $tcpOk = (Test-NetConnection -ComputerName $Server -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded
    if ($tcpOk) {
        Write-Host "  外网端口连通正常（TCP $Port）"
    } else {
        Write-Warning "  外网端口不通，请检查云控制台「防火墙/安全组」是否放行了 TCP $Port（来源 0.0.0.0/0）"
    }
}

# ---------- 完成 ----------
Step "5/5" "部署完成"
Write-Host "  访问地址：http://${Server}:${Port}" -ForegroundColor Green
Write-Host "  日志：docker logs -f $BackendContainer" -ForegroundColor DarkGray
Write-Host "  数据/会话不受重建影响（卷持久化）" -ForegroundColor DarkGray
