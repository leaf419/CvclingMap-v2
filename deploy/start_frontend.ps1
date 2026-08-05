# ============================================================
# BikeFlowGNN v2 — 前端启动脚本（开发模式，Windows PowerShell）
# 说明: 从项目根目录运行  deploy\start_frontend.ps1
# ============================================================
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\frontend"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  BikeFlowGNN v2 前端部署 (Vite + GeoScene JS API)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

if (-not (Test-Path "node_modules")) {
    Write-Host "[i] 安装前端依赖..." -ForegroundColor Yellow
    npm install
}

Write-Host "[i] 启动前端: http://localhost:5173" -ForegroundColor Green
Write-Host "    (Ctrl+C 停止)" -ForegroundColor DarkGray
Write-Host ""
npm run dev
