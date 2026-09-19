/**
 * @file components/DriftScatterPlot.tsx
 * @brief WebGL2 scatter plot -- instanced rendering via webgl_engine primitives
 *
 * Design:
 *  1. BufferGeometryManager SoA layout + Instanced Rendering (single drawCall)
 *  2. OrbitController for ortho camera pan/zoom/inertia
 *  3. Octree (Raycaster) for O(log N) hover pick and box select
 *  4. Engine vertex/fragment shaders for pulse glow and selection ring
 *  5. Zero Three.js dependency -- pure WebGL2
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import type { DriftScatterPlotProps, UmapPoint } from "../types";
import {
  BufferGeometryManager,
  type PointData,
} from "../webgl_engine/BufferGeometryManager";
import { OrbitController } from "../webgl_engine/OrbitController";
import { Octree, type QueryResult } from "../webgl_engine/Raycaster";

// -- GLSL shaders (instanced Billboard) -----------------------

const VERT: string = [
  "#version 300 es",
  "precision highp float;",
  "layout(location = 0) in vec2 aQuadVertex;",
  "layout(location = 1) in vec3  aOffset;",
  "layout(location = 2) in vec4  aColor;",
  "layout(location = 3) in float aSize;",
  "layout(location = 4) in float aGlowIntensity;",
  "layout(location = 5) in float aSelected;",
  "uniform mat4  uViewProjection;",
  "uniform vec3  uCameraRight;",
  "uniform vec3  uCameraUp;",
  "uniform float uTime;",
  "uniform float uPointSizeScale;",
  "uniform float uPixelRatio;",
  "out vec2  vQuadUV;",
  "out vec4  vColor;",
  "out float vGlowIntensity;",
  "out float vSelected;",
  "out float vDepth;",
  "void main() {",
  "    float size = aSize * uPointSizeScale * uPixelRatio;",
  "    if (aGlowIntensity > 0.0) {",
  '        size *= 1.0 + 0.35 * sin(uTime * 6.2832 * 3.0 + aOffset.x * 10.0);',
  "        size *= 1.0 + aGlowIntensity * 0.4;",
  "    }",
  "    if (aSelected > 0.5) size *= 1.4;",
  "    vec3 worldPos = aOffset",
  "                  + uCameraRight * aQuadVertex.x * size",
  "                  + uCameraUp    * aQuadVertex.y * size;",
  "    vec4 viewPos = uViewProjection * vec4(worldPos, 1.0);",
  "    gl_Position  = viewPos;",
  "    vQuadUV        = aQuadVertex;",
  "    vColor         = aColor;",
  "    vGlowIntensity = aGlowIntensity;",
  "    vSelected      = aSelected;",
  "    vDepth         = viewPos.z / viewPos.w;",
  "}",
].join("\\n");

const FRAG: string = [
  "#version 300 es",
  "precision highp float;",
  "in vec2  vQuadUV;",
  "in vec4  vColor;",
  "in float vGlowIntensity;",
  "in float vSelected;",
  "in float vDepth;",
  "uniform float uTime;",
  "uniform float uFogDensity;",
  "uniform vec3  uFogColor;",
  "uniform float uGlowFalloff;",
  "out vec4 fragColor;",
  "const float CORE_RADIUS   = 0.32;",
  "const float GLOW_RADIUS   = 0.50;",
  "const float EDGE_SOFTNESS = 0.04;",
  "void main() {",
  "    float dist = length(vQuadUV);",
  "    if (dist > GLOW_RADIUS + EDGE_SOFTNESS) discard;",
  "    vec3 baseColor = vColor.rgb;",
  "    float alpha    = vColor.a;",
  "    float coreAlpha = 1.0 - smoothstep(CORE_RADIUS - EDGE_SOFTNESS,",
  "                                        CORE_RADIUS + EDGE_SOFTNESS, dist);",
  "    float glowMask = 0.0;",
  "    if (vGlowIntensity > 0.0) {",
  "        float glowDist = max(0.0, dist - CORE_RADIUS) / (GLOW_RADIUS - CORE_RADIUS);",
  "        glowMask = vGlowIntensity * pow(1.0 - glowDist, uGlowFalloff);",
  "        float pulse = 0.6 + 0.4 * sin(uTime * 6.2832 * 3.0);",
  "        glowMask *= pulse;",
  "        vec3 glowColor = mix(baseColor, vec3(1.0), 0.5);",
  "        baseColor = mix(baseColor, glowColor, glowMask * 0.6);",
  "    }",
  "    if (vSelected > 0.5) {",
  "        float ringDist = abs(dist - CORE_RADIUS);",
  "        float ringMask = 1.0 - smoothstep(0.0, EDGE_SOFTNESS * 2.0, ringDist);",
  "        baseColor = mix(baseColor, vec3(0.0, 1.0, 0.5), ringMask * 0.8);",
  "        float selGlow = (1.0 - smoothstep(CORE_RADIUS, GLOW_RADIUS, dist)) * 0.3;",
  "        baseColor += vec3(0.0, 0.4, 0.2) * selGlow;",
  "    }",
  "    float finalAlpha = max(coreAlpha, glowMask * 0.5) * alpha;",
  "    if (uFogDensity > 0.0) {",
  "        float fogFactor = clamp(exp(-uFogDensity * abs(vDepth)), 0.0, 1.0);",
  "        baseColor  = mix(uFogColor, baseColor, fogFactor);",
  "        finalAlpha *= fogFactor;",
  "    }",
  "    fragColor = vec4(baseColor, finalAlpha);",
  "}",
].join("\\n");

// -- Color mapping ---------------------------------------------

const LABEL_COLORS: Record<number, [number, number, number]> = {
  0: [0.231, 0.510, 0.965],
  1: [0.133, 0.773, 0.369],
  2: [0.961, 0.620, 0.043],
  3: [0.937, 0.267, 0.267],
  4: [0.545, 0.361, 0.965],
  5: [0.925, 0.282, 0.600],
  6: [0.024, 0.714, 0.835],
  7: [0.976, 0.451, 0.086],
  8: [0.078, 0.722, 0.655],
  9: [0.659, 0.333, 0.969],
};

const DRIFT_COLOR: [number, number, number] = [1.0, 0.133, 0.267];
const BG_COLOR: [number, number, number] = [0.039, 0.039, 0.102];
const NORMAL_SIZE = 3.0;
const DRIFT_SIZE  = 8.0;

// -- Shader compilation ----------------------------------------

function compileShader(
  gl: WebGL2RenderingContext,
  type: number,
  source: string,
): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error("[DriftScatterPlot] Shader compile error:", gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function createProgram(
  gl: WebGL2RenderingContext,
  vertSrc: string,
  fragSrc: string,
): WebGLProgram | null {
  const vs = compileShader(gl, gl.VERTEX_SHADER, vertSrc);
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, fragSrc);
  if (!vs || !fs) return null;
  const prog = gl.createProgram();
  if (!prog) return null;
  gl.attachShader(prog, vs);
  gl.attachShader(prog, fs);
  gl.linkProgram(prog);
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    console.error("[DriftScatterPlot] Program link error:", gl.getProgramInfoLog(prog));
    gl.deleteProgram(prog);
    return null;
  }
  return prog;
}

// ===============================================================
// DriftScatterPlot
// ===============================================================

export const DriftScatterPlot: React.FC<DriftScatterPlotProps> = ({
  snapshot,
  highlightedIds,
  onPointClick,
  onSelectionComplete,
  width,
  height = 480,
}) => {
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const glRef        = useRef<WebGL2RenderingContext | null>(null);
  const progRef      = useRef<WebGLProgram | null>(null);
  const bufMgrRef    = useRef<BufferGeometryManager | null>(null);
  const orbitRef     = useRef<OrbitController | null>(null);
  const octreeRef    = useRef<Octree | null>(null);
  const pointsMapRef = useRef<UmapPoint[]>([]);
  const rafRef       = useRef<number>(0);
  const t0Ref        = useRef<number>(Date.now());
  const cleanupRef   = useRef<(() => void) | null>(null);
  const [tooltip, setTooltip] = useState<{
    x: number; y: number; p: UmapPoint;
  } | null>(null);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);

  // -- WebGL2 + Engine init ------------------------------------

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let disposed = false;

    const gl = canvas.getContext("webgl2", {
      antialias: true,
      alpha: true,
      premultipliedAlpha: false,
    });
    if (!gl) {
      console.error("[DriftScatterPlot] WebGL2 not available");
      return;
    }
    glRef.current = gl;

    const prog = createProgram(gl, VERT, FRAG);
    if (!prog) return;
    progRef.current = prog;

    const bufMgr = new BufferGeometryManager({ maxPoints: 200_000 });
    bufMgr.initGL(gl);
    bufMgrRef.current = bufMgr;

    const orbit = new OrbitController({
      minZoom: 0.05,
      maxZoom: 500,
      inertiaDecay: 0.92,
    });
    orbit.setViewport(canvas.clientWidth, canvas.clientHeight);
    orbitRef.current = orbit;

    const unbind = orbit.bind(canvas);
    cleanupRef.current = unbind;

    const uViewProjection = gl.getUniformLocation(prog, "uViewProjection");
    const uCameraRight    = gl.getUniformLocation(prog, "uCameraRight");
    const uCameraUp       = gl.getUniformLocation(prog, "uCameraUp");
    const uTime           = gl.getUniformLocation(prog, "uTime");
    const uPointSizeScale = gl.getUniformLocation(prog, "uPointSizeScale");
    const uPixelRatio     = gl.getUniformLocation(prog, "uPixelRatio");
    const uFogDensity     = gl.getUniformLocation(prog, "uFogDensity");
    const uFogColor       = gl.getUniformLocation(prog, "uFogColor");
    const uGlowFalloff    = gl.getUniformLocation(prog, "uGlowFalloff");

    const renderFrame = () => {
      if (disposed) return;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== w * devicePixelRatio ||
          canvas.height !== h * devicePixelRatio) {
        canvas.width  = w * devicePixelRatio;
        canvas.height = h * devicePixelRatio;
        gl.viewport(0, 0, canvas.width, canvas.height);
        orbit.setViewport(w, h);
      }

      gl.clearColor(BG_COLOR[0], BG_COLOR[1], BG_COLOR[2], 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.useProgram(prog);

      const vp = orbit.viewProjection;
      gl.uniformMatrix4fv(uViewProjection, false, vp);
      gl.uniform3f(uCameraRight, 1, 0, 0);
      gl.uniform3f(uCameraUp, 0, 1, 0);
      gl.uniform1f(uTime, (Date.now() - t0Ref.current) / 1000);
      gl.uniform1f(uPointSizeScale, 1.0);
      gl.uniform1f(uPixelRatio, devicePixelRatio);
      gl.uniform1f(uFogDensity, 0.0);
      gl.uniform3f(uFogColor, BG_COLOR[0], BG_COLOR[1], BG_COLOR[2]);
      gl.uniform1f(uGlowFalloff, 2.0);

      bufMgr.upload();
      bufMgr.draw();

      rafRef.current = requestAnimationFrame(renderFrame);
    };
    rafRef.current = requestAnimationFrame(renderFrame);

    return () => {
      disposed = true;
      cancelAnimationFrame(rafRef.current);
      cleanupRef.current?.();
      bufMgr.dispose();
      gl.deleteProgram(prog);
      glRef.current = null;
      progRef.current = null;
      bufMgrRef.current = null;
      orbitRef.current = null;
    };
  }, []);

  // -- Data update: snapshot -> BufferGeometryManager + Octree --

  useEffect(() => {
    if (!snapshot || !bufMgrRef.current) return;
    const pts = snapshot.points;
    const n = pts.length;
    pointsMapRef.current = pts;

    let xMin = Infinity, xMax = -Infinity;
    let yMin = Infinity, yMax = -Infinity;
    for (const p of pts) {
      if (p.x < xMin) xMin = p.x;
      if (p.x > xMax) xMax = p.x;
      if (p.y < yMin) yMin = p.y;
      if (p.y > yMax) yMax = p.y;
    }
    const rX = xMax - xMin || 1;
    const rY = yMax - yMin || 1;
    const SCALE = 600;

    const pointData: PointData[] = new Array(n);
    const xs = new Float32Array(n);
    const ys = new Float32Array(n);

    for (let i = 0; i < n; i++) {
      const p = pts[i];
      const nx = ((p.x - xMin) / rX - 0.5) * SCALE;
      const ny = ((p.y - yMin) / rY - 0.5) * SCALE;
      xs[i] = nx;
      ys[i] = ny;

      const color = p.isDrift
        ? DRIFT_COLOR
        : (LABEL_COLORS[p.labelId % 10] ?? [0.267, 0.533, 0.8]);

      pointData[i] = {
        x: nx,
        y: ny,
        r: color[0],
        g: color[1],
        b: color[2],
        a: 1.0,
        size: p.isDrift ? DRIFT_SIZE : NORMAL_SIZE,
        glowIntensity: p.isDrift ? 0.8 : 0.0,
        selected: highlightedIds.has(p.sampleId),
      };
    }

    bufMgrRef.current.setPoints(pointData);

    const octree = new Octree({
      minX: -SCALE, minY: -SCALE, minZ: -1,
      maxX:  SCALE, maxY:  SCALE, maxZ:  1,
    });
    octree.buildFrom2D(xs, ys, n);
    octreeRef.current = octree;
  }, [snapshot]);

  // -- Highlight sync ------------------------------------------

  useEffect(() => {
    if (!bufMgrRef.current || !snapshot) return;
    const indices: number[] = [];
    const points = snapshot.points;
    for (let i = 0; i < points.length; i++) {
      if (highlightedIds.has(points[i].sampleId)) {
        indices.push(i);
      }
    }
    bufMgrRef.current.updateSelection(indices, true);
  }, [highlightedIds, snapshot]);

  // -- Hover pick (Octree KNN) ---------------------------------

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!octreeRef.current || !canvasRef.current || !orbitRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const screenX = e.clientX - rect.left;
      const screenY = e.clientY - rect.top;
      const world = orbitRef.current.screenToWorld(e.clientX, e.clientY);

      const results: QueryResult[] = octreeRef.current.queryNearest2D(
        world.x, world.y, 1,
      );
      if (results.length > 0 && results[0].distance < 15) {
        const idx = results[0].index;
        const p = pointsMapRef.current[idx];
        if (p) {
          setTooltip({ x: screenX, y: screenY, p });
          return;
        }
      }
      setTooltip(null);
    },
    [],
  );

  const handleClick = useCallback(() => {
    if (tooltip) onPointClick?.(tooltip.p.sampleId);
  }, [tooltip, onPointClick]);

  // -- Box select (Octree AABB) --------------------------------

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (e.button !== 0 || !e.shiftKey) return;
      dragStartRef.current = { x: e.clientX, y: e.clientY };
    },
    [],
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!dragStartRef.current || !octreeRef.current || !canvasRef.current || !orbitRef.current) return;
      const start = dragStartRef.current;
      dragStartRef.current = null;

      const toWorld = (sx: number, sy: number) =>
        orbitRef.current!.screenToWorld(sx, sy);

      const wA = toWorld(start.x, start.y);
      const wB = toWorld(e.clientX, e.clientY);
      const box = {
        minX: Math.min(wA.x, wB.x),
        minY: Math.min(wA.y, wB.y),
        minZ: -Infinity,
        maxX: Math.max(wA.x, wB.x),
        maxY: Math.max(wA.y, wB.y),
        maxZ: Infinity,
      };

      const results = octreeRef.current.queryAABB(box);
      const selected = results
        .map((r) => pointsMapRef.current[r.index]?.sampleId)
        .filter(Boolean) as string[];

      if (selected.length > 0) onSelectionComplete?.(selected);
    },
    [onSelectionComplete],
  );

  // -- Render --------------------------------------------------

  return (
    <div
      style={{
        position: "relative",
        width: width ?? "100%",
        height,
        overflow: "hidden",
        borderRadius: 8,
        border: "1px solid #1e293b",
        backgroundColor: `rgb(${(BG_COLOR[0] * 255) | 0},${(BG_COLOR[1] * 255) | 0},${(BG_COLOR[2] * 255) | 0})`,
      }}
    >
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", display: "block", cursor: "crosshair" }}
        onMouseMove={handleMouseMove}
        onClick={handleClick}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
      />

      {tooltip && (
        <div
          style={{
            position: "absolute",
            left: tooltip.x + 12,
            top: tooltip.y - 8,
            padding: "8px 12px",
            backgroundColor: "rgba(15,23,42,0.95)",
            border: "1px solid #334155",
            borderRadius: 6,
            color: "#e2e8f0",
            fontSize: 12,
            fontFamily: "monospace",
            pointerEvents: "none",
            zIndex: 10,
          }}
        >
          <div style={{ color: "#38bdf8", marginBottom: 4 }}>
            {tooltip.p.sampleId.slice(0, 12)}
          </div>
          <div>label: {tooltip.p.label}</div>
          <div>({tooltip.p.x.toFixed(3)}, {tooltip.p.y.toFixed(3)})</div>
          {tooltip.p.isDrift && (
            <div style={{ color: "#ef4444", marginTop: 4 }}>
              DRIFT (score={tooltip.p.isolationScore?.toFixed(2)})
            </div>
          )}
        </div>
      )}

      <div
        style={{
          position: "absolute",
          bottom: 8,
          right: 8,
          padding: "6px 10px",
          backgroundColor: "rgba(15,23,42,0.8)",
          borderRadius: 4,
          fontSize: 11,
          color: "#94a3b8",
          display: "flex",
          gap: 12,
        }}
      >
        <span>
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              backgroundColor: "#4488cc",
              marginRight: 4,
            }}
          />
          normal
        </span>
        <span>
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              backgroundColor: "#ff2244",
              marginRight: 4,
            }}
          />
          drift
        </span>
        <span style={{ color: "#64748b" }}>
          {snapshot ? snapshot.points.length + " pts" : "no data"}
        </span>
      </div>
    </div>
  );
};
