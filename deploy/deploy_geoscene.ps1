# ============================================================
# BikeFlowGNN v2 — GeoScene Enterprise 部署辅助脚本（Windows PowerShell）
# 说明: 从项目根目录运行  deploy\deploy_geoscene.ps1
# 功能: 检查 GeoScene Server 连接 → 生成输出数据 → 构建 File GDB 交付包 → 检查服务发布
# 注意: 实际的服务发布（地图服务/场景服务）需 GeoScene Enterprise Server 运行后执行
# ============================================================
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  GeoScene Enterprise 部署辅助" -ForegroundColor Cyan
Write-Host "  (比赛规则第5条: 服务器端 GIS 核心必须基于 GeoScene 服务器端产品)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1) 检查 GeoScene Server 连接
Write-Host ""
Write-Host "[1/4] 检查 GeoScene Server 连接..." -ForegroundColor Green
python -c "from gateway.service.geoscene_client import geoscene_client as c; import json; print(json.dumps(c.status(), ensure_ascii=False, indent=2))"
if ($LASTEXITCODE -ne 0) {
    Write-Host "      连接检查失败（服务未启动或 .env 未配置）" -ForegroundColor Red
    Write-Host "      请确认: GeoScene Enterprise Server 已启动，且 .env 中 BIKEFLOW_GEOSCENE_SERVER_URL 正确" -ForegroundColor Yellow
}

# 2) 生成可视化输出数据（GeoJSON）
Write-Host ""
Write-Host "[2/4] 生成输出数据 (GeoJSON)..." -ForegroundColor Green
python tools/geoscene/publish_services.py --generate

# 3) 构建 File Geodatabase 交付包
Write-Host ""
Write-Host "[3/4] 构建 File Geodatabase 交付包..." -ForegroundColor Green
python tools/geoscene/build_fgdb.py

# 4) 服务发布状态检查
Write-Host ""
Write-Host "[4/4] GeoScene 服务发布状态..." -ForegroundColor Green
python tools/geoscene/publish_services.py --check

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  下一步（需 GeoScene Enterprise Server 运行）:" -ForegroundColor Cyan
Write-Host "  1. 在 GeoScene Pro 中从 File GDB 发布地图服务（参照 server_config.json）" -ForegroundColor White
Write-Host "  2. 或运行: python tools/geoscene/publish_services.py --publish" -ForegroundColor White
Write-Host "  3. 发布完成后再次运行本脚本第 1/4 步验证服务可用" -ForegroundColor White
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
