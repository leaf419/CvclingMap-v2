# ============================================================
# BikeFlowGNN v2 — 一键构建脚本（生产部署，Windows PowerShell）
# 说明: 从项目根目录运行  deploy\build_all.ps1
# 产出: 前端 dist/ 静态产物 + 网关校验
# ============================================================
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  BikeFlowGNN v2 生产构建" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1) .env 检查
Set-Location $Root
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "[i] 已生成 .env，请填写 BIKEFLOW_GEOSCENE_SERVER_URL / TOKEN" -ForegroundColor Yellow
    }
}

# 2) 前端构建
Write-Host ""
Write-Host "[1/3] 前端构建 (npm run build)..." -ForegroundColor Green
Set-Location "$Root\frontend"
if (-not (Test-Path "node_modules")) {
    Write-Host "      安装依赖..." -ForegroundColor Yellow
    npm install
}
npm run build
if ($LASTEXITCODE -ne 0) { Write-Host "前端构建失败" -ForegroundColor Red; exit 1 }
Write-Host "      前端构建完成: frontend\dist" -ForegroundColor Green

# 3) GeoScene 服务状态检查
Write-Host ""
Write-Host "[2/3] GeoScene Server 状态检查..." -ForegroundColor Green
Set-Location $Root
python tools/geoscene/publish_services.py --check

# 4) File Geodatabase 交付包
Write-Host ""
Write-Host "[3/3] File Geodatabase 交付包..." -ForegroundColor Green
python tools/geoscene/build_fgdb.py

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  构建完成。后续部署:" -ForegroundColor Cyan
Write-Host "  1. 启动网关:    deploy\start_gateway.ps1" -ForegroundColor White
Write-Host "  2. 生产服务:    用静态服务器托管 frontend/dist，并将 /api 反代到网关 :8000" -ForegroundColor White
Write-Host "  3. GeoScene 服务发布: 参见 docs\部署文档.md" -ForegroundColor White
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
