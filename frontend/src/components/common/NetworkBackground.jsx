import { useEffect, useRef } from 'react'
import { NODE_COLORS } from '../../lib/colors'

// A living fund-flow graph behind the landing page: nodes drift, nearby nodes link up, little "payments" travel along
// the links and light the node they reach, and the cursor gently pushes nodes aside. Decorative only (aria-hidden).
// With "reduce motion" set it draws one still frame instead of animating.
const COLORS = Object.values(NODE_COLORS)
export const LINK_DIST = 165
const MOUSE_RADIUS = 130

export const nodeCount = (w, h) => Math.max(28, Math.min(90, Math.round((w * h) / 14000)))

export function makeNodes(w, h, n, rand = Math.random) {
  return Array.from({ length: n }, () => ({
    x: rand() * w,
    y: rand() * h,
    vx: (rand() - 0.5) * 22,
    vy: (rand() - 0.5) * 22,
    r: 1.6 + rand() * 2.4,
    color: COLORS[Math.floor(rand() * COLORS.length)],
    flash: 0,
  }))
}

// Move every node by dt seconds, bounce off the edges, and push away from the cursor.
export function stepNodes(nodes, w, h, dt, mouse = null) {
  for (const n of nodes) {
    if (mouse) {
      const dx = n.x - mouse.x
      const dy = n.y - mouse.y
      const d = Math.hypot(dx, dy)
      if (d > 0 && d < MOUSE_RADIUS) {
        const push = ((MOUSE_RADIUS - d) / MOUSE_RADIUS) * 90 * dt
        n.vx += (dx / d) * push
        n.vy += (dy / d) * push
      }
    }
    const speed = Math.hypot(n.vx, n.vy)
    if (speed > 34) {
      n.vx = (n.vx / speed) * 34
      n.vy = (n.vy / speed) * 34
    }
    n.x += n.vx * dt
    n.y += n.vy * dt
    if (n.x < 0 || n.x > w) {
      n.vx = -n.vx
      n.x = Math.min(w, Math.max(0, n.x))
    }
    if (n.y < 0 || n.y > h) {
      n.vy = -n.vy
      n.y = Math.min(h, Math.max(0, n.y))
    }
    n.flash = Math.max(0, n.flash - dt * 1.6)
  }
}

// Pairs of nodes close enough to be joined: [i, j, distance].
export function linksOf(nodes, dist = LINK_DIST) {
  const out = []
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const d = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y)
      if (d < dist) out.push([i, j, d])
    }
  }
  return out
}

function draw(ctx, nodes, links, pulses, w, h, mouse) {
  ctx.clearRect(0, 0, w, h)
  ctx.lineWidth = 1
  for (const [i, j, d] of links) {
    ctx.strokeStyle = `rgba(56,189,248,${(1 - d / LINK_DIST) * 0.4})`
    ctx.beginPath()
    ctx.moveTo(nodes[i].x, nodes[i].y)
    ctx.lineTo(nodes[j].x, nodes[j].y)
    ctx.stroke()
  }
  if (mouse) {
    for (const n of nodes) {
      const d = Math.hypot(n.x - mouse.x, n.y - mouse.y)
      if (d < LINK_DIST) {
        ctx.strokeStyle = `rgba(248,250,252,${(1 - d / LINK_DIST) * 0.35})`
        ctx.beginPath()
        ctx.moveTo(mouse.x, mouse.y)
        ctx.lineTo(n.x, n.y)
        ctx.stroke()
      }
    }
  }
  for (const n of nodes) {
    ctx.shadowColor = n.color
    ctx.shadowBlur = 8 + n.flash * 22
    ctx.fillStyle = n.color
    ctx.globalAlpha = 0.7 + n.flash * 0.3
    ctx.beginPath()
    ctx.arc(n.x, n.y, n.r + n.flash * 3, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.globalAlpha = 1
  ctx.shadowBlur = 14
  ctx.shadowColor = '#38bdf8'
  ctx.fillStyle = '#e0f2fe'
  for (const p of pulses) {
    const a = nodes[p.i]
    const b = nodes[p.j]
    ctx.beginPath()
    ctx.arc(a.x + (b.x - a.x) * p.t, a.y + (b.y - a.y) * p.t, 2.2, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.shadowBlur = 0
}

export default function NetworkBackground() {
  const ref = useRef(null)

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas?.getContext?.('2d')
    if (!canvas || !ctx) return undefined // no canvas support (or a test environment): the page still works
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let w = 0
    let h = 0
    let nodes = []
    let pulses = []
    let raf = 0
    let last = performance.now()
    let spawnIn = 0.4
    let mouse = null

    const resize = () => {
      w = canvas.clientWidth || window.innerWidth
      h = canvas.clientHeight || window.innerHeight
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      nodes = makeNodes(w, h, nodeCount(w, h))
      pulses = []
    }
    const onMove = (e) => {
      mouse = { x: e.clientX, y: e.clientY }
    }
    const onLeave = () => {
      mouse = null
    }

    function frame(now) {
      const dt = Math.min((now - last) / 1000, 0.05)
      last = now
      stepNodes(nodes, w, h, dt, mouse)
      const links = linksOf(nodes)
      spawnIn -= dt
      if (spawnIn <= 0 && links.length) {
        const [i, j] = links[Math.floor(Math.random() * links.length)]
        pulses.push(Math.random() < 0.5 ? { i, j, t: 0 } : { i: j, j: i, t: 0 })
        spawnIn = 0.25 + Math.random() * 0.55
      }
      for (const p of pulses) p.t += dt * 0.8
      pulses = pulses.filter((p) => {
        if (p.t >= 1) nodes[p.j].flash = 1
        return p.t < 1
      })
      draw(ctx, nodes, links, pulses, w, h, mouse)
      raf = requestAnimationFrame(frame)
    }

    resize()
    window.addEventListener('resize', resize)
    if (reduce) {
      draw(ctx, nodes, linksOf(nodes), [], w, h, null)
    } else {
      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerleave', onLeave)
      raf = requestAnimationFrame(frame)
    }
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerleave', onLeave)
    }
  }, [])

  return <canvas ref={ref} aria-hidden="true" data-testid="network-background" className="absolute inset-0 h-full w-full" />
}
