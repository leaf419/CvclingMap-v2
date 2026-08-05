# ============================================================
# BikeFlowGNN v2 — 部署脚本（Windows PowerShell）
# 说明: 从项目根目录运行  deploy\start_gateway.ps1
# ============================================================
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  BikeFlowGNN v2 网关部署 (FastAPI + GeoScene)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1) 环境变量模板检查
if (-not (Test-Path "$Root\.env")) {
    if (Test-Path "$Root\.env.example") {
        Copy-Item "$Root\.env.example" "$Root\.env"
        Write-Host "[i] 已从 .env.example 生成 .env，请按需编辑其中的 Token 配置。" -ForegroundColor Yellow
    }
}

# 2) 依赖检查（快速）
python -c "import fastapi, uvicorn, httpx" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[i] 安装网关依赖..." -ForegroundColor Yellow
    pip install -r gateway/requirements.txt
}

# 3) 读取 .env 中的端口（默认 8000）
$env:BIKEFLOW_GATEWAY_PORT = (python -c "from gateway.core.config import settings; print(settings.gateway_port)" 2>$null)
if (-not $env:BIKEFLOW_GATEWAY_PORT) { $env:BIKEFLOW_GATEWAY_PORT = "8000" }

# 4) 启动网关
Write-Host "[i] 启动网关: http://localhost:$env:BIKEFLOW_GATEWAY_PORT" -ForegroundColor Green
Write-Host "[i] 文档: http://localhost:$env:BIKEFLOW_GATEWAY_PORT/docs" -ForegroundColor Green
Write-Host "[i] GeoScene 状态: http://localhost:$env:BIKEFLOW_GATEWAY_PORT/api/geoscene/status" -ForegroundColor Green
Write-Host "    (Ctrl+C 停止)" -ForegroundColor DarkGray
Write-Host ""
uvicorn gateway.app:app --host 0.0.0.0 --port $env:BIKEFLOW_GATEWAY_PORT
