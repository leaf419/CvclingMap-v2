/** Zustand 全局状态管理 */
import { create } from 'zustand'
import type {
  RouteResult, SearchStatus, UserTemplate, LatLng, MapLayer,
} from './types'
import { searchRoutes, getUserTemplates } from './api'

interface TemplateInfo {
  key: string
  name: string
  description: string
}

interface BikeFlowState {
  searchStatus: SearchStatus
  errorMessage: string | null
  source: LatLng | null
  target: LatLng | null
  selectedTemplate: UserTemplate
  routes: RouteResult[]
  bestRouteId: number | null
  selectedRouteId: number | null
  fromCache: boolean
  pipelineDuration: number | null
  templates: TemplateInfo[]
  templatesLoading: boolean
  mapCenter: [number, number]
  mapZoom: number
  visibleLayers: Set<MapLayer>

  setSource: (coords: LatLng | null) => void
  setTarget: (coords: LatLng | null) => void
  setSelectedTemplate: (template: UserTemplate) => void
  setSelectedRouteId: (id: number | null) => void
  toggleLayer: (layer: MapLayer) => void
  setMapCenter: (center: [number, number]) => void

  fetchTemplates: () => Promise<void>
  executeSearch: () => Promise<void>
  resetSearch: () => void
}

export const useBikeFlowStore = create<BikeFlowState>((set, get) => ({
  searchStatus: 'idle',
  errorMessage: null,
  source: null,
  target: null,
  selectedTemplate: 'commuter',
  routes: [],
  bestRouteId: null,
  selectedRouteId: null,
  fromCache: false,
  pipelineDuration: null,
  templates: [],
  templatesLoading: false,
  mapCenter: [116.40, 39.92],
  mapZoom: 13,
  visibleLayers: new Set(['routes']),

  setSource: (coords) => set({ source: coords }),
  setTarget: (coords) => set({ target: coords }),
  setSelectedTemplate: (t) => set({ selectedTemplate: t }),
  setSelectedRouteId: (id) => set({ selectedRouteId: id }),
  setMapCenter: (center) => set({ mapCenter: center }),

  toggleLayer: (layer) =>
    set((s) => {
      const next = new Set(s.visibleLayers)
      next.has(layer) ? next.delete(layer) : next.add(layer)
      return { visibleLayers: next }
    }),

  fetchTemplates: async () => {
    set({ templatesLoading: true })
    try {
      const resp = await getUserTemplates()
      set({ templates: resp.templates, templatesLoading: false })
    } catch {
      set({ templatesLoading: false })
    }
  },

  executeSearch: async () => {
    const { source, target, selectedTemplate } = get()
    if (!source || !target) {
      set({ errorMessage: '请先设置起点和终点' })
      return
    }
    set({ searchStatus: 'searching', errorMessage: null })
    try {
      const resp = await searchRoutes({
        source, target,
        user_template: selectedTemplate,
      })
      set({
        searchStatus: 'success',
        routes: resp.routes,
        bestRouteId: resp.best_route_id,
        selectedRouteId: resp.best_route_id,
        fromCache: resp.from_cache,
        pipelineDuration: resp.pipeline_duration_sec ?? null,
      })
      if (resp.scene_config?.center) {
        set({ mapCenter: resp.scene_config.center as [number, number] })
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '搜索失败'
      set({ searchStatus: 'error', errorMessage: msg })
    }
  },

  resetSearch: () =>
    set({
      searchStatus: 'idle', errorMessage: null,
      routes: [], bestRouteId: null, selectedRouteId: null,
      fromCache: false, pipelineDuration: null,
    }),
}))
