/** 侧边栏 — 搜索控制面板 */
import { useEffect } from 'react'
import { useBikeFlowStore } from '../core/store'
import { useTheme } from '../core/useTheme'
import type { UserTemplate } from '../core/types'

export default function Sidebar() {
  const {
    source, target, selectedTemplate,
    templates, templatesLoading,
    searchStatus, errorMessage, fromCache, pipelineDuration,
    visibleLayers,
    setSource, setTarget, setSelectedTemplate,
    toggleLayer, fetchTemplates, executeSearch, resetSearch,
  } = useBikeFlowStore()

  const { theme, toggle: toggleTheme } = useTheme()

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  const isSearching = searchStatus === 'searching'
  const canSearch = !!source && !!target && !isSearching

  return (
    <div className="app-sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🚲</div>
          <div className="sidebar-logo-text">
            <h1>BikeFlowGNN</h1>
            <p>北京骑行路线智能分析系统</p>
          </div>
          <button className="theme-toggle" onClick={toggleTheme} title={theme === 'light' ? '切换暗色主题' : '切换亮色主题'}>
            {theme === 'light' ? '🌙' : '☀️'}
          </button>
        </div>
      </div>

      <div className="sidebar-body">
        {/* 起终点 */}
        <div className="sidebar-section">
          <div className="sidebar-section-title">路线设置</div>

          <label className="form-label">起点</label>
          <div className={`coord-box ${!source ? 'empty' : ''}`}>
            {source ? `${source[0].toFixed(6)}, ${source[1].toFixed(6)}` : '点击地图选择起点'}
          </div>
          <button className="btn btn-ghost" onClick={() => setSource(null)} disabled={!source}>清除</button>

          <label className="form-label" style={{ marginTop: 14 }}>终点</label>
          <div className={`coord-box ${!target ? 'empty' : ''}`}>
            {target ? `${target[0].toFixed(6)}, ${target[1].toFixed(6)}` : '点击地图选择终点'}
          </div>
          <button className="btn btn-ghost" onClick={() => setTarget(null)} disabled={!target}>清除</button>
        </div>

        {/* 用户画像 */}
        <div className="sidebar-section">
          <div className="sidebar-section-title">骑行偏好</div>
          <label className="form-label">骑行者画像</label>
          <select
            className="form-select"
            value={selectedTemplate}
            onChange={(e) => setSelectedTemplate(e.target.value as UserTemplate)}
            disabled={templatesLoading}
          >
            {templates.length > 0
              ? templates.map((t) => (
                  <option key={t.key} value={t.key}>{t.name} — {t.description}</option>
                ))
              : (
                  <>
                    <option value="commuter">通勤者 — 高效安全</option>
                    <option value="tourist">游客 — 风景优先</option>
                    <option value="fitness">健身者 — 长距离骑行</option>
                    <option value="family">家庭 — 安全第一</option>
                  </>
                )}
          </select>
        </div>

        {/* 图层 */}
        <div className="sidebar-section">
          <div className="sidebar-section-title">地图图层</div>
          {(['routes'] as const).map((layer) => (
            <div
              key={layer}
              className="layer-toggle-item"
              onClick={() => toggleLayer(layer)}
            >
              <div className={`layer-toggle-switch ${visibleLayers.has(layer) ? 'on' : ''}`} />
              <span>推荐路线</span>
            </div>
          ))}
        </div>

        {/* 搜索 */}
        <div className="sidebar-section">
          <button className="btn btn-primary" onClick={executeSearch} disabled={!canSearch}>
            {isSearching ? '正在分析路线...' : '开始搜索'}
          </button>

          {searchStatus === 'success' && (
            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {fromCache && <span className="cache-badge">缓存</span>}
                {pipelineDuration !== null && (
                  <span style={{ fontSize: 11, color: '#9CA3AF' }}>{pipelineDuration}s</span>
                )}
              </div>
              <button className="btn btn-ghost" onClick={resetSearch}>重置</button>
            </div>
          )}
        </div>

        {/* 错误 */}
        {errorMessage && <div className="status-error">{errorMessage}</div>}

        {/* 搜索中 */}
        {isSearching && (
          <div className="sidebar-section">
            <div className="status-box">
              <div className="spinner" />
              <div className="status-text">正在分析路线</div>
              <div className="status-sub">数据加载 → 图构建 → 边权计算 → 路径搜索</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
