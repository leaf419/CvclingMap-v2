/** 主地图页 — 组装交互层（控制面板）与渲染层（Three.js 3D 场景） */
import { useBikeFlowStore } from '../core/store'
import { Scene3DView } from '../rendering'
import { Sidebar, RouteCompare, MetricsPanel } from '../interaction'

export default function MapPage() {
  const source = useBikeFlowStore((s) => s.source)
  const target = useBikeFlowStore((s) => s.target)

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="app-main">
        <div className="map-container">
          <Scene3DView />
          <div className="map-watermark">
            BikeFlowGNN v2 · 北京六区 · 骑行路线智能分析 · 3D Scene
          </div>
        </div>
        <RouteCompare />
        <MetricsPanel />
        {!source && !target && (
          <div className="map-hint">点击地图设置起点 (A) 和终点 (B)</div>
        )}
      </div>
    </div>
  )
}
