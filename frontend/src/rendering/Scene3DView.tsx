/** 3D 场景 — Three.js 建筑白模 + 路网 + 路线叠加
 *
 *  比赛合规：GIS 核心后端使用 GeoScene Server，前端 Three.js 仅做应用可视化
 */
import { useEffect, useRef, useMemo, useCallback } from 'react'
import { Canvas, useThree, ThreeEvent } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { useBikeFlowStore } from '../core/store'
import type { LatLng, RouteResult } from '../core/types'

// ============================================================
// 坐标转换 WGS84 → 局部 3D 空间
// ============================================================
const REF_LON = 116.37
const REF_LAT = 39.92
const DEG2M_LON = 111320 * Math.cos((REF_LAT * Math.PI) / 180)
const DEG2M_LAT = 111320

function to3D(lon: number, lat: number, y = 0): [number, number, number] {
  return [(lon - REF_LON) * DEG2M_LON, y, -(lat - REF_LAT) * DEG2M_LAT]
}
function toLngLat(x: number, z: number): LatLng {
  return [REF_LON + x / DEG2M_LON, REF_LAT - z / DEG2M_LAT]
}

const ROUTE_COLORS = ['#27ae60', '#3498db', '#e67e22', '#9b59b6', '#e74c3c']

// ============================================================
// 主题色彩
// ============================================================
const DARK_COLORS = {
  groundFill: '#0F1720', gridStroke: '#1F2A3A',
  bldgTexture: '#1E2A38', bldg3D: '#CDD6E0',
  roadTexture: '#506878', road3D: '#405868', roadOpacity: 0.15,
  adminStroke: '#556688', sceneBg: '#0D1117',
  sky: '#334455', ground: '#0D1117',
}
const LIGHT_COLORS = {
  groundFill: '#E4EAF0', gridStroke: '#D0D8E0',
  bldgTexture: '#C8D0D8', bldg3D: '#D5D9DF',
  roadTexture: '#C4A882', road3D: '#B8956E', roadOpacity: 0.25,
  adminStroke: '#8898A8', sceneBg: '#E8EDF2',
  sky: '#D4DCE4', ground: '#E8EDF2',
}

function getThemeColors() {
  return document.documentElement.getAttribute('data-theme') === 'dark' ? DARK_COLORS : LIGHT_COLORS
}

// ============================================================
// 地图纹理地面（Canvas 绘制建筑轮廓 + 路网 + 六区轮廓）
// ============================================================
const TSIZE = 2048
const HALF = 35000

function MapGround() {
  const col = getThemeColors()
  const canvas = useMemo(() => {
    const c = document.createElement('canvas')
    c.width = TSIZE; c.height = TSIZE
    const ctx = c.getContext('2d')!
    ctx.fillStyle = col.groundFill; ctx.fillRect(0, 0, TSIZE, TSIZE)
    return c
  }, [col.groundFill])

  const texture = useMemo(() => {
    const t = new THREE.CanvasTexture(canvas)
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping
    return t
  }, [canvas])

  // 加载数据后更新纹理
  useEffect(() => {
    Promise.all([
      fetch('/data/buildings.geojson').then(r => r.json()),
      fetch('/data/segments.geojson').then(r => r.json()),
      fetch('/data/beijing_districts_osm.geojson').then(r => r.json()),
    ]).then(([bldGeo, segGeo, distGeo]) => {
      const ctx = canvas.getContext('2d')!
      const c = getThemeColors()
      ctx.fillStyle = c.groundFill; ctx.fillRect(0, 0, TSIZE, TSIZE)

      const toPx3 = (x3d: number, z3d: number) => ({
        px: (x3d + HALF) / (HALF * 2) * TSIZE,
        py: (z3d + HALF) / (HALF * 2) * TSIZE,
      })

      // 网格
      ctx.strokeStyle = c.gridStroke; ctx.lineWidth = 0.5
      for (let i = 0; i < TSIZE; i += TSIZE / 20) {
        ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, TSIZE); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(TSIZE, i); ctx.stroke()
      }

      // 建筑轮廓
      ctx.fillStyle = c.bldgTexture
      const bldFeats = bldGeo.features || []
      for (const f of bldFeats) {
        const ring = parseCoords3(f)
        if (!ring || ring.length < 3) continue
        ctx.beginPath()
        const p0 = toPx3(ring[0][0], ring[0][2]); ctx.moveTo(p0.px, p0.py)
        for (let k = 1; k < ring.length; k++) {
          const p = toPx3(ring[k][0], ring[k][2]); ctx.lineTo(p.px, p.py)
        }
        ctx.closePath(); ctx.fill()
      }

      // 行政区边界
      ctx.strokeStyle = c.adminStroke; ctx.lineWidth = 2
      const distFeats = distGeo.features || []
      for (const f of distFeats) {
        const coordsList = f.geometry?.coordinates || []
        for (const wayCoords of coordsList) {
          if (!Array.isArray(wayCoords) || wayCoords.length < 2) continue
          ctx.beginPath()
          const [sx, , sz] = to3D(wayCoords[0][0], wayCoords[0][1]); const s = toPx3(sx, sz); ctx.moveTo(s.px, s.py)
          for (let k = 1; k < wayCoords.length; k++) {
            const [x, , z] = to3D(wayCoords[k][0], wayCoords[k][1]); const p = toPx3(x, z); ctx.lineTo(p.px, p.py)
          }
          ctx.stroke()
        }
      }

      // 路网
      ctx.strokeStyle = c.roadTexture; ctx.lineWidth = 1
      const segFeats = segGeo.features || []
      let segDrawn = 0
      for (const f of segFeats) {
        const coords = f.geometry?.coordinates || []
        if (coords.length < 2) continue
        ctx.beginPath()
        const [sx, , sz] = to3D(coords[0][0], coords[0][1]); const s = toPx3(sx, sz); ctx.moveTo(s.px, s.py)
        for (let k = 1; k < coords.length; k++) {
          const [x, , z] = to3D(coords[k][0], coords[k][1]); const p = toPx3(x, z); ctx.lineTo(p.px, p.py)
        }
        ctx.stroke()
        segDrawn++
      }
      console.log('[3D] 纹理: 建筑轮廓 + 行政区边界 + 路网', segDrawn, '条')

      texture.needsUpdate = true
      console.log('[3D] 地图纹理更新完成')
    }).catch(err => console.warn('[3D] 纹理失败:', err))
  }, [canvas, texture])

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.5, 0]}>
      <planeGeometry args={[HALF * 2, HALF * 2]} />
      <meshBasicMaterial map={texture} side={THREE.DoubleSide} />
    </mesh>
  )
}

// 坐标解析（同 test_3d.html）
function parseCoords3(feat: any): Array<[number, number, number]> | null {
  const c = feat.geometry?.coordinates
  if (!c || !Array.isArray(c)) return null
  const first = c[0]
  if (first && typeof first === 'object' && !Array.isArray(first) && 'lat' in first) {
    return c.map((p: any) => to3D(p.lon, p.lat, 0) as [number, number, number])
  }
  if (Array.isArray(first) && first.length >= 2 && typeof first[0] === 'number') {
    return c[0].map((p: any) => to3D(p[0], p[1], 0) as [number, number, number])
  }
  if (Array.isArray(first) && Array.isArray(first[0])) {
    return first.map((p: any) => to3D(p[0], p[1], 0) as [number, number, number])
  }
  return null
}

// ============================================================
// 建筑层 — InstancedMesh 单次 draw call
// ============================================================
function BuildingLayer() {
  const groupRef = useRef<THREE.Group>(new THREE.Group())
  const loadedRef = useRef(false)

  useEffect(() => {
    if (loadedRef.current) return

    console.log('[3D] 开始加载建筑数据...')
    fetch('/data/buildings.geojson')
      .then((r) => {
        console.log('[3D] 建筑响应状态:', r.status, '大小:', r.headers.get('content-length'))
        return r.json()
      })
      .then((geojson: any) => {
        const features = geojson.features || []
        const count = features.length
        const col = getThemeColors()
        console.log('[3D] 加载建筑:', count)

        const mat = new THREE.MeshPhongMaterial({
          color: col.bldg3D,
          specular: '#8899AA',
          shininess: 4,
          flatShading: true,
          transparent: true,
          opacity: 0.94,
        })

        const unitBox = new THREE.BoxGeometry(1, 1, 1)
        const im = new THREE.InstancedMesh(unitBox, mat, count)
        im.castShadow = true
        im.receiveShadow = true

        const dummy = new THREE.Object3D()
        let valid = 0

        for (let i = 0; i < count; i++) {
          const feat = features[i]
          const geom = feat.geometry
          if (!geom) continue

          const rawCoords = geom.coordinates
          if (!rawCoords || !Array.isArray(rawCoords)) continue

          let ring: number[][] | null = null
          if (Array.isArray(rawCoords[0]) && Array.isArray(rawCoords[0][0]) && typeof rawCoords[0][0][0] === 'number') {
            ring = rawCoords[0]
          } else if (typeof rawCoords[0] === 'object' && !Array.isArray(rawCoords[0]) && 'lat' in rawCoords[0]) {
            ring = rawCoords.map((p: any) => [p.lon, p.lat])
          }

          if (!ring || ring.length < 3) continue

          let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity
          for (const c of ring) {
            const [x, , z] = to3D(c[0], c[1], 0)
            if (x < minX) minX = x; if (x > maxX) maxX = x
            if (z < minZ) minZ = z; if (z > maxZ) maxZ = z
          }

          const w = maxX - minX || 1
          const d = maxZ - minZ || 1
          const cx = (minX + maxX) / 2
          const cz = (minZ + maxZ) / 2
          const h = (feat.properties?.height_m || 9) * 3

          dummy.position.set(cx, h / 2, cz)
          dummy.scale.set(w, h, d)
          dummy.updateMatrix()
          im.setMatrixAt(valid, dummy.matrix)
          im.setColorAt(valid, new THREE.Color(col.bldg3D))
          valid++
        }

        im.count = valid
        im.instanceMatrix.needsUpdate = true
        if (im.instanceColor) im.instanceColor.needsUpdate = true

        groupRef.current.add(im)
        loadedRef.current = true
        console.log('[3D] 建筑 InstancedMesh:', valid, '栋 (1 draw call)')
      })
      .catch((err: any) => console.warn('[3D] 建筑加载失败:', err.message || err, err.stack))
  }, [])

  return <primitive object={groupRef.current} />
}

// ============================================================
// 路网层 — 合并为单几何体
// ============================================================
function RoadLayer() {
  const groupRef = useRef<THREE.Group>(new THREE.Group())
  const loadedRef = useRef(false)

  useEffect(() => {
    if (loadedRef.current) return

    console.log('[3D] 开始加载路网数据...')
    fetch('/data/segments.geojson')
      .then((r) => {
        console.log('[3D] 路网响应状态:', r.status, '大小:', r.headers.get('content-length'))
        return r.json()
      })
      .then((geojson: any) => {
        const features = geojson.features || []
        const col = getThemeColors()
        console.log('[3D] 加载路网:', features.length)

        const mat = new THREE.LineBasicMaterial({ color: col.road3D, transparent: true, opacity: col.roadOpacity })

        const positions: number[] = []
        for (const feat of features) {
          const coords = feat.geometry?.coordinates || []
          if (coords.length < 2) continue
          for (let k = 0; k < coords.length - 1; k++) {
            const [x1, , z1] = to3D(coords[k][0], coords[k][1], 0.5)
            const [x2, , z2] = to3D(coords[k + 1][0], coords[k + 1][1], 0.5)
            positions.push(x1, 0.5, z1, x2, 0.5, z2)
          }
        }

        const geo = new THREE.BufferGeometry()
        geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
        groupRef.current.add(new THREE.LineSegments(geo, mat))
        loadedRef.current = true
        console.log('[3D] 路网合并完成: 1 draw call')
      })
      .catch((err: any) => console.warn('[3D] 路网加载失败:', err.message || err, err.stack))
  }, [])

  return <primitive object={groupRef.current} />
}

// ============================================================
// 路线叠加
// ============================================================
function RouteOverlay() {
  const routes = useBikeFlowStore((s) => s.routes)
  const selectedRouteId = useBikeFlowStore((s) => s.selectedRouteId)
  const bestRouteId = useBikeFlowStore((s) => s.bestRouteId)
  const groupRef = useRef<THREE.Group>(new THREE.Group())

  useEffect(() => {
    const g = groupRef.current
    // 清理旧管线
    g.traverse((child) => { if (child instanceof THREE.Mesh) { child.geometry.dispose(); (child.material as THREE.Material).dispose() } })
    g.children.length = 0

    routes.forEach((route: RouteResult, idx: number) => {
      if (route.coordinates.length < 2) return
      const isSelected = route.route_id === selectedRouteId
      const isBest = route.route_id === bestRouteId
      const baseColor = new THREE.Color(ROUTE_COLORS[idx % ROUTE_COLORS.length])
      const pts = route.coordinates.map((c) => new THREE.Vector3(...to3D(c[0], c[1], 20)))
      const curve = new THREE.CatmullRomCurve3(pts)
      const segments = pts.length * 3
      const tubeRadius = isBest ? 10 : isSelected ? 8 : 5

      // ── 光晕层（粗 2.2x，半透明，无深度写入）──
      const glowGeo = new THREE.TubeGeometry(curve, segments, tubeRadius * 2.2, 8, false)
      const glowMat = new THREE.MeshBasicMaterial({
        color: baseColor, transparent: true, opacity: 0.15, depthWrite: false,
      })
      g.add(new THREE.Mesh(glowGeo, glowMat))

      // ── 主体管状路线 ──
      const tubeGeo = new THREE.TubeGeometry(curve, segments, tubeRadius, 8, false)
      const tubeMat = new THREE.MeshBasicMaterial({
        color: baseColor,
        transparent: true,
        opacity: isSelected ? 1.0 : isBest ? 0.9 : 0.65,
      })
      g.add(new THREE.Mesh(tubeGeo, tubeMat))
    })
  }, [routes, selectedRouteId, bestRouteId])

  return <primitive object={groupRef.current} />
}

// ============================================================
// 起终点标记
// ============================================================
function StartEndMarkers() {
  const source = useBikeFlowStore((s) => s.source)
  const target = useBikeFlowStore((s) => s.target)
  const groupRef = useRef<THREE.Group>(new THREE.Group())

  const sphereGeo = useMemo(() => new THREE.SphereGeometry(60, 16, 16), [])

  useEffect(() => {
    const g = groupRef.current
    g.children.length = 0

    if (source) {
      const m = new THREE.Mesh(sphereGeo, new THREE.MeshPhongMaterial({ color: '#27ae60', emissive: '#0a4020' }))
      m.position.set(...to3D(source[0], source[1], 150))
      g.add(m)
    }
    if (target) {
      const m = new THREE.Mesh(sphereGeo, new THREE.MeshPhongMaterial({ color: '#e74c3c', emissive: '#601010' }))
      m.position.set(...to3D(target[0], target[1], 150))
      g.add(m)
    }
  }, [source, target, sphereGeo])

  return <primitive object={groupRef.current} />
}

// ============================================================
// 点击处理
// ============================================================
function ClickHandler() {
  const { camera, gl } = useThree()
  const raycaster = useMemo(() => new THREE.Raycaster(), [])
  const planeRef = useRef(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0))
  const setSource = useBikeFlowStore((s) => s.setSource)
  const setTarget = useBikeFlowStore((s) => s.setTarget)

  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      const rect = gl.domElement.getBoundingClientRect()
      const mouse = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1,
      )
      raycaster.setFromCamera(mouse, camera)
      const intersection = new THREE.Vector3()
      raycaster.ray.intersectPlane(planeRef.current, intersection)
      if (!intersection) return

      const coords = toLngLat(intersection.x, intersection.z)
      const state = useBikeFlowStore.getState()
      if (!state.source) setSource(coords)
      else if (!state.target) setTarget(coords)
      else { setSource(coords); setTarget(null) }
    },
    [camera, gl, raycaster, setSource, setTarget],
  )

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.2, 0]} onClick={handleClick} visible={false}>
      <planeGeometry args={[200000, 200000]} />
      <meshBasicMaterial transparent opacity={0} />
    </mesh>
  )
}

// ============================================================
// 北京 16 区配色
// ============================================================
const DISTRICT_COLORS: Record<string, string> = {
  '海淀区': '#3a7ca5',
  '西城区': '#5a8a6a',
  '东城区': '#8a7a4a',
  '朝阳区': '#7a5a8a',
  '石景山区': '#5a8a8a',
  '丰台区': '#8a8a5a',
  '大兴区': '#8a5a7a',
  '通州区': '#5a7a8a',
  '顺义区': '#6a8a5a',
  '昌平区': '#4a6a8a',
  '门头沟区': '#6a5a8a',
  '房山区': '#8a6a5a',
  '怀柔区': '#5a6a7a',
  '平谷区': '#7a6a8a',
  '密云区': '#5a8a7a',
  '延庆区': '#8a5a6a',
}

function DistrictLayer() {
  const groupRef = useRef<THREE.Group>(new THREE.Group())
  const loadedRef = useRef(false)

  useEffect(() => {
    if (loadedRef.current) return

    fetch('/data/beijing_districts_osm.geojson')
      .then((r) => r.json())
      .then((geojson: any) => {
        const features = geojson.features || []
        console.log('[3D] 加载行政区:', features.length)

        // 按颜色分组合并线条
        const colorGroups: Record<string, number[]> = {}
        const fills: Array<{ pts: THREE.Vector3[]; color: string; name: string; cx: number; cz: number }> = []

        for (const feat of features) {
          const name: string = feat.properties?.name || ''
          const color = DISTRICT_COLORS[name] || '#557799'
          const coordsList = feat.geometry?.coordinates || []

          const allLines: THREE.Vector3[][] = []
          for (const wayCoords of coordsList) {
            if (!Array.isArray(wayCoords) || wayCoords.length < 2) continue
            const pts = wayCoords.map((c: number[]) => {
              const [x, , z] = to3D(c[0], c[1], 0.3)
              return new THREE.Vector3(x, 0.3, z)
            })
            if (pts.length >= 2) allLines.push(pts)
          }

          if (allLines.length === 0) continue

          // 合并该区边界为独立线段 (LineSegments, 无NaN)
          if (!colorGroups[color]) colorGroups[color] = []
          for (const pts of allLines) {
            for (let k = 0; k < pts.length - 1; k++) {
              colorGroups[color].push(pts[k].x, 0.3, pts[k].z, pts[k + 1].x, 0.3, pts[k + 1].z)
            }
          }

          // 填充面
          const largestLine = allLines.reduce((a, b) => a.length > b.length ? a : b)
          const allPts = allLines.flat()
          const cx = allPts.reduce((s, p) => s + p.x, 0) / allPts.length
          const cz = allPts.reduce((s, p) => s + p.z, 0) / allPts.length
          fills.push({ pts: largestLine, color, name, cx, cz })
        }

        // 按颜色创建合并线段（LineSegments, 每种颜色 1 draw call）
        for (const [color, positions] of Object.entries(colorGroups)) {
          const geo = new THREE.BufferGeometry()
          geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
          const line = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({
            color, transparent: true, opacity: 0.7,
          }))
          groupRef.current.add(line)
        }

        // 填充面 + 标签
        for (const { pts, color, name, cx, cz } of fills) {
          if (pts.length >= 3) {
            const shape = new THREE.Shape()
            shape.moveTo(pts[0].x, pts[0].z)
            for (let k = 1; k < pts.length; k++) shape.lineTo(pts[k].x, pts[k].z)
            shape.closePath()
            const shapeGeo = new THREE.ShapeGeometry(shape)
            shapeGeo.rotateX(-Math.PI / 2)
            const fillMesh = new THREE.Mesh(shapeGeo, new THREE.MeshPhongMaterial({
              color, transparent: true, opacity: 0.12, side: THREE.DoubleSide,
            }))
            fillMesh.position.y = 0.12
            groupRef.current.add(fillMesh)
          }

          const canvas = document.createElement('canvas')
          canvas.width = 256; canvas.height = 64
          const ctx = canvas.getContext('2d')!
          ctx.fillStyle = '#ffffffcc'
          ctx.font = 'bold 32px "Microsoft YaHei", sans-serif'
          ctx.textAlign = 'center'
          ctx.fillText(name, 128, 40)
          const tex = new THREE.CanvasTexture(canvas)
          const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }))
          sprite.position.set(cx, 250, cz)
          sprite.scale.set(2800, 700, 1)
          groupRef.current.add(sprite)
        }

        loadedRef.current = true
        console.log('[3D] 行政区完成:', features.length, '区,', Object.keys(colorGroups).length, '线条组')
      })
      .catch((err) => console.warn('[3D] 行政区加载失败:', err))
  }, [])

  return <primitive object={groupRef.current} />
}

// ============================================================
// 主场景
// ============================================================
function Scene() {
  const col = getThemeColors()
  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[8000, 20000, 5000]} intensity={0.65} />
      <directionalLight position={[-5000, 5000, -5000]} intensity={0.12} />
      <hemisphereLight args={[col.sky, col.ground, 0.25]} />

      <MapGround />
      <DistrictLayer />
      <BuildingLayer />
      <RoadLayer />
      <RouteOverlay />
      <StartEndMarkers />
      <ClickHandler />

      <OrbitControls
        target={[0, 0, 0]}
        maxPolarAngle={Math.PI / 2.3}
        minDistance={500}
        maxDistance={1000000}
        enableDamping
        dampingFactor={0.06}
        screenSpacePanning
      />
    </>
  )
}

// ============================================================
// 导出
// ============================================================
export default function Scene3DView() {
  const col = getThemeColors()
  return (
    <Canvas
      camera={{ position: [0, 22000, 13000], fov: 42, near: 10, far: 500000 }}
      style={{ width: '100%', height: '100%', background: col.sceneBg }}
      gl={{ antialias: true }}
      onCreated={({ camera }: any) => camera.lookAt(0, 0, 0)}
    >
      <Scene />
    </Canvas>
  )
}
