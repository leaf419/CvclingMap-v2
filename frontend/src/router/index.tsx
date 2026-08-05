/** React Router 路由配置 */
import { createBrowserRouter, Navigate } from 'react-router-dom'
import MapPage from '../pages/MapPage'

export const router = createBrowserRouter([
  { path: '/', element: <MapPage /> },
  { path: '*', element: <Navigate to="/" replace /> },
])
