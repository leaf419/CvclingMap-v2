/** 路线对比面板 — Pareto最优路线列表 */
import { useBikeFlowStore } from '../core/store'

const ROUTE_COLORS = ['#27ae60', '#3498db', '#e67e22', '#9b59b6', '#e74c3c']
const METRIC_COLORS = ['#27ae60', '#3498db', '#f39c12', '#e74c3c']

export default function RouteCompare() {
  const { routes, bestRouteId, selectedRouteId, setSelectedRouteId } = useBikeFlowStore()
  if (routes.length === 0) return null

  return (
    <div className="route-panel">
      <div className="route-panel-title">
        <span>Pareto 最优路线</span>
        <span className="route-panel-count">{routes.length} 条</span>
      </div>

      <div className="route-list">
        {routes.map((route, idx) => {
          const isSelected = route.route_id === selectedRouteId
          const isBest = route.route_id === bestRouteId
          const color = ROUTE_COLORS[idx % ROUTE_COLORS.length]

          return (
            <div
              key={route.route_id}
              className={`route-item ${isSelected ? 'selected' : ''} ${isBest ? 'best' : ''}`}
              onClick={() => setSelectedRouteId(route.route_id)}
            >
              <div className="route-item-header">
                <div className="route-item-left">
                  <div className="route-color-dot" style={{ background: color }} />
                  <span className="route-name">路线 #{route.route_id + 1}</span>
                  {isBest && <span className="route-badge">推荐</span>}
                </div>
                <span className="route-rank">#{idx + 1}</span>
              </div>

              <div className="route-meta">
                <span className="route-meta-item">
                  <span className="route-meta-dot" style={{ background: METRIC_COLORS[0] }} />
                  {(route.metrics.total_length / 1000).toFixed(1)}km
                </span>
                <span className="route-meta-item">
                  <span className="route-meta-dot" style={{ background: METRIC_COLORS[1] }} />
                  安全{(route.metrics.avg_safety * 100).toFixed(0)}%
                </span>
                <span className="route-meta-item">
                  <span className="route-meta-dot" style={{ background: METRIC_COLORS[2] }} />
                  风景{(route.metrics.avg_scenery * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
