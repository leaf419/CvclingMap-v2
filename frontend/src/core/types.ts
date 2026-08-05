/** BikeFlowGNN 前端类型定义 */

export type LatLng = [number, number]

export interface RouteMetrics {
  total_length: number
  total_cost: number
  avg_safety: number
  avg_comfort: number
  avg_scenery: number
  avg_traffic_stress: number
  avg_beauty: number
  avg_pref_score: number
  num_segments: number
}

export interface RouteResult {
  route_id: number
  coordinates: LatLng[]
  metrics: RouteMetrics
}

export interface SceneConfig {
  center: [number, number]
  zoom?: number
  user_template?: string
}

export interface RouteSearchResponse {
  routes: RouteResult[]
  best_route_id: number
  scene_config: SceneConfig
  from_cache: boolean
  pipeline_duration_sec?: number
}

export interface RouteSearchRequest {
  source: LatLng
  target: LatLng
  user_template: UserTemplate
  use_cache?: boolean
  skip_gnn?: boolean
}

export type UserTemplate = 'commuter' | 'tourist' | 'fitness' | 'family'

export type SearchStatus = 'idle' | 'searching' | 'success' | 'error'

export type MapLayer = 'segments' | 'stations' | 'routes'
