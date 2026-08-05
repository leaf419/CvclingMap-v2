/** 指标面板 — 选中路线的详细指标 */
import { useBikeFlowStore } from '../core/store'
import type { RouteMetrics } from '../core/types'

const METRICS = [
  { key: 'total_length' as const, label: '总距离', max: 20, color: '#3B82F6', suffix: ' km', transform: (v: number) => v / 1000 },
  { key: 'avg_safety' as const, label: '安全性', max: 1, color: '#10B981' },
  { key: 'avg_comfort' as const, label: '舒适度', max: 1, color: '#34D399' },
  { key: 'avg_scenery' as const, label: '风景指数', max: 1, color: '#F59E0B' },
  { key: 'avg_traffic_stress' as const, label: '交通压力', max: 1, color: '#F97316' },
  { key: 'avg_beauty' as const, label: '美观度', max: 1, color: '#8B5CF6' },
  { key: 'avg_pref_score' as const, label: '偏好得分', max: 1, color: '#06B6D4' },
  { key: 'num_segments' as const, label: '街道段数', max: 30, color: '#6B7280' },
]

function MetricCard({ value, max, color, label, suffix }: {
  value: number; max: number; color: string; label: string; suffix?: string
}) {
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value.toFixed(suffix ? 2 : 0)}{suffix || ''}</div>
      <div className="metric-bar">
        <div className="metric-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}

export default function MetricsPanel() {
  const { routes, selectedRouteId, bestRouteId } = useBikeFlowStore()
  if (routes.length === 0) return null

  const selected = routes.find((r) => r.route_id === selectedRouteId)
    || routes.find((r) => r.route_id === bestRouteId)
  if (!selected) return null

  const m: RouteMetrics = selected.metrics

  return (
    <div className="metrics-panel">
      <div className="metrics-header">
        <span className="metrics-title">路线 #{selected.route_id + 1} 详情</span>
        {selected.route_id === bestRouteId && <span className="route-badge">推荐</span>}
      </div>
      <div className="metrics-grid">
        {METRICS.map(({ key, label, max, color, suffix, transform }) => (
          <MetricCard
            key={key}
            label={label}
            value={transform ? transform(m[key]) : m[key]}
            max={max}
            color={color}
            suffix={suffix}
          />
        ))}
      </div>
      <div className="segments-count">
        {m.num_segments} 个街道段
      </div>
    </div>
  )
}
