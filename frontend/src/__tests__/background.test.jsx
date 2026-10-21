import { render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import NetworkBackground, { LINK_DIST, linksOf, makeNodes, nodeCount, stepNodes } from '../components/common/NetworkBackground'
import { NODE_COLORS } from '../lib/colors'

// a repeatable "random": 0.1, 0.2, ... so the same nodes come out every run
const seeded = () => {
  let i = 0
  return () => ((++i * 0.137) % 1)
}

describe('nodes', () => {
  it('makes the requested number inside the area, in the portal colours', () => {
    const nodes = makeNodes(800, 600, 40, seeded())
    expect(nodes).toHaveLength(40)
    for (const n of nodes) {
      expect(n.x).toBeGreaterThanOrEqual(0)
      expect(n.x).toBeLessThanOrEqual(800)
      expect(n.y).toBeGreaterThanOrEqual(0)
      expect(n.y).toBeLessThanOrEqual(600)
      expect(Object.values(NODE_COLORS)).toContain(n.color)
      expect(n.r).toBeGreaterThan(1)
    }
  })

  it('scales the count with the screen and stays between 28 and 90', () => {
    expect(nodeCount(300, 300)).toBe(28)
    expect(nodeCount(1200, 800)).toBe(69)
    expect(nodeCount(4000, 3000)).toBe(90)
  })
})

describe('movement', () => {
  it('moves each node by its speed', () => {
    const n = { x: 100, y: 100, vx: 10, vy: -4, r: 2, color: '#fff', flash: 0 }
    stepNodes([n], 800, 600, 0.5)
    expect([n.x, n.y]).toEqual([105, 98])
  })

  it('bounces off the edges and never leaves the area', () => {
    const nodes = makeNodes(200, 150, 30, seeded())
    for (let i = 0; i < 2000; i++) stepNodes(nodes, 200, 150, 0.05)
    for (const n of nodes) {
      expect(n.x).toBeGreaterThanOrEqual(0)
      expect(n.x).toBeLessThanOrEqual(200)
      expect(n.y).toBeGreaterThanOrEqual(0)
      expect(n.y).toBeLessThanOrEqual(150)
    }
    const left = { x: 1, y: 50, vx: -30, vy: 0, r: 2, color: '#fff', flash: 0 }
    stepNodes([left], 200, 150, 0.1)
    expect(left.vx).toBeGreaterThan(0)
  })

  it('caps the speed so nothing races across the page', () => {
    const n = { x: 100, y: 100, vx: 500, vy: 500, r: 2, color: '#fff', flash: 0 }
    stepNodes([n], 800, 600, 0.01)
    expect(Math.hypot(n.vx, n.vy)).toBeLessThanOrEqual(34.0001)
  })

  it('pushes nodes away from the cursor, and only nearby ones', () => {
    const near = { x: 110, y: 100, vx: 0, vy: 0, r: 2, color: '#fff', flash: 0 }
    const far = { x: 700, y: 500, vx: 0, vy: 0, r: 2, color: '#fff', flash: 0 }
    stepNodes([near, far], 800, 600, 0.1, { x: 100, y: 100 })
    expect(near.vx).toBeGreaterThan(0)
    expect([far.vx, far.vy]).toEqual([0, 0])
  })

  it('lets a node flash fade out', () => {
    const n = { x: 5, y: 5, vx: 0, vy: 0, r: 2, color: '#fff', flash: 1 }
    for (let i = 0; i < 40; i++) stepNodes([n], 100, 100, 0.05)
    expect(n.flash).toBe(0)
  })
})

describe('links', () => {
  const at = (x, y) => ({ x, y, vx: 0, vy: 0, r: 2, color: '#fff', flash: 0 })

  it('joins only nodes that are close, each pair once', () => {
    const links = linksOf([at(0, 0), at(50, 0), at(0, 80), at(900, 900)])
    expect(links.map(([i, j]) => [i, j])).toEqual([[0, 1], [0, 2], [1, 2]])
    expect(links.every(([, , d]) => d < LINK_DIST)).toBe(true)
  })

  it('has no links when nodes are far apart', () => {
    expect(linksOf([at(0, 0), at(500, 500), at(1000, 0)])).toEqual([])
  })
})

describe('the background component', () => {
  let ctx
  beforeEach(() => {
    ctx = new Proxy({}, { get: (t, k) => (k in t ? t[k] : (t[k] = vi.fn())), set: (t, k, v) => ((t[k] = v), true) })
    HTMLCanvasElement.prototype.getContext = () => ctx
  })
  afterEach(() => {
    HTMLCanvasElement.prototype.getContext = () => null
    vi.unstubAllGlobals()
  })

  it('draws, keeps animating, and stops cleanly when removed', () => {
    const frames = []
    vi.stubGlobal('requestAnimationFrame', (fn) => frames.push(fn) && frames.length)
    const cancel = vi.fn()
    vi.stubGlobal('cancelAnimationFrame', cancel)
    const { unmount } = render(<NetworkBackground />)
    expect(frames).toHaveLength(1)                       // the first frame is queued
    frames[0](performance.now() + 16)
    expect(ctx.clearRect).toHaveBeenCalled()
    expect(ctx.arc).toHaveBeenCalled()                   // nodes are drawn
    expect(frames).toHaveLength(2)                       // and the next frame is queued
    unmount()
    expect(cancel).toHaveBeenCalled()
  })

  it('draws a single still frame when the visitor prefers reduced motion', () => {
    const raf = vi.fn()
    vi.stubGlobal('requestAnimationFrame', raf)
    window.matchMedia = () => ({ matches: true, addEventListener() {}, removeEventListener() {} })
    render(<NetworkBackground />)
    expect(raf).not.toHaveBeenCalled()
    expect(ctx.arc).toHaveBeenCalled()
    window.matchMedia = (q) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  })

  it('follows the pointer while it is on screen and lets go on unmount', () => {
    const frames = []
    vi.stubGlobal('requestAnimationFrame', (fn) => frames.push(fn) && frames.length)
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const remove = vi.spyOn(window, 'removeEventListener')
    const { unmount } = render(<NetworkBackground />)
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: 50, clientY: 60 }))
    frames[0](performance.now() + 16)                     // draws with the pointer known, without throwing
    unmount()
    expect(remove.mock.calls.map((c) => c[0])).toEqual(expect.arrayContaining(['resize', 'pointermove']))
  })

  it('renders nothing animated and does not crash when canvas is unavailable', () => {
    HTMLCanvasElement.prototype.getContext = () => null
    const raf = vi.fn()
    vi.stubGlobal('requestAnimationFrame', raf)
    expect(() => render(<NetworkBackground />)).not.toThrow()
    expect(raf).not.toHaveBeenCalled()
  })
})
