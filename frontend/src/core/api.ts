/** API 客户端 — 与FastAPI后端通信 */
import axios from 'axios'
import type {
  RouteSearchRequest,
  RouteSearchResponse,
} from './types'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

export async function checkHealth() {
  const { data } = await apiClient.get('/health')
  return data
}

export async function getUserTemplates() {
  const { data } = await apiClient.get('/user-templates')
  return data
}

export async function searchRoutes(req: RouteSearchRequest): Promise<RouteSearchResponse> {
  const { data } = await apiClient.post<RouteSearchResponse>('/routes/search', req)
  return data
}

export async function getRouteById(routeId: number) {
  const { data } = await apiClient.get(`/routes/${routeId}`)
  return data
}

export default apiClient
