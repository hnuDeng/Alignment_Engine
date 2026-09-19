/**
 * @file BufferGeometryManager.ts
 * @brief WebGL 缓冲区管理器 —— 手动管理百万级特征点的 GPU 内存
 *
 * 设计要点：
 *  1. 使用 Float32Array 手动管理所有顶点属性，零 GC 压力
 *  2. Instanced Rendering 布局：Billboard 四边形 (4 verts) + 实例属性
 *  3. 64 字节对齐：所有 Float32Array 按 16 元素 (64B) 对齐，匹配 GPU 缓存行
 *  4. 增量更新：仅上传 dirty 区域到 GPU，避免全量 bufferSubData
 *  5. 128 维降维颜色映射：将高维嵌入向量映射到 RGB 色彩空间
 */

// ── 类型 ─────────────────────────────────────────────────────

/** 单个特征点的原始数据 */
export interface PointData {
  x: number;
  y: number;
  z?: number;
  /** RGBA 归一化颜色 (0~1) */
  r: number;
  g: number;
  b: number;
  a?: number;
  /** 点大小 (像素) */
  size?: number;
  /** 发光强度 (0=正常, >0=异常) */
  glowIntensity?: number;
  /** 选中状态 */
  selected?: boolean;
}

/** 缓冲区配置 */
export interface BufferConfig {
  /** 最大支持的点数（预分配） */
  maxPoints: number;
  /** 是否启用 Z 坐标（2D 散点图可关闭以节省内存） */
  enableZ?: boolean;
}

// ── 常量 ─────────────────────────────────────────────────────

/** Billboard 四边形的 4 个顶点（两个三角形） */
const QUAD_VERTICES = new Float32Array([
  -0.5, -0.5,
   0.5, -0.5,
   0.5,  0.5,
  -0.5,  0.5,
]);

/** Billboard 四边形的索引（两个三角形） */
const QUAD_INDICES = new Uint16Array([0, 1, 2, 0, 2, 3]);

/** 内存对齐：16 个 float = 64 字节 */
const ALIGNMENT_FLOATS = 16;

/** 实例属性步长（float 数量）：offset(3) + color(4) + size(1) + glow(1) + selected(1) = 10 */
const INSTANCE_STRIDE_FLOATS = 10;

// ── 辅助：对齐到缓存行 ─────────────────────────────────────

function alignedLength(n: number): number {
  return Math.ceil(n / ALIGNMENT_FLOATS) * ALIGNMENT_FLOATS;
}

// ══════════════════════════════════════════════════════════════
// BufferGeometryManager
// ══════════════════════════════════════════════════════════════

export class BufferGeometryManager {
  /** 最大点数 */
  readonly maxPoints: number;
  /** 当前活跃点数 */
  private _count = 0;

  // ── Billboard 四边形缓冲区 ────────────────────────────────
  /** 四边形顶点 (4 * 2 = 8 floats) */
  private readonly _quadVerts: Float32Array;
  /** 四边形索引 (6 indices) */
  private readonly _quadIdx: Uint16Array;

  // ── 实例属性缓冲区（SoA 布局，缓存友好）────────────────
  /** 位置：maxPoints * 3 (x, y, z) */
  private readonly _positions: Float32Array;
  /** 颜色：maxPoints * 4 (r, g, b, a) */
  private readonly _colors: Float32Array;
  /** 大小 + 发光 + 选中：maxPoints * 3 */
  private readonly _props: Float32Array;

  // ── GPU 缓冲区句柄 ────────────────────────────────────────
  private _gl: WebGL2RenderingContext | null = null;
  private _quadVBO: WebGLBuffer | null = null;
  private _quadIBO: WebGLBuffer | null = null;
  private _posVBO: WebGLBuffer | null = null;
  private _colVBO: WebGLBuffer | null = null;
  private _propVBO: WebGLBuffer | null = null;
  private _vao: WebGLVertexArrayObject | null = null;

  // ── Dirty 追踪（增量上传）───────────────────────────────
  private _dirtyStart = Infinity;
  private _dirtyEnd = -1;

  constructor(config: BufferConfig) {
    this.maxPoints = config.maxPoints;
    const aligned = alignedLength(this.maxPoints);

    // 预分配对齐的 TypedArray
    this._quadVerts = new Float32Array(QUAD_VERTICES);
    this._quadIdx   = new Uint16Array(QUAD_INDICES);
    this._positions = new Float32Array(aligned * 3);  // x, y, z
    this._colors    = new Float32Array(aligned * 4);  // r, g, b, a
    this._props     = new Float32Array(aligned * 3);  // size, glow, selected
  }

  // ── 属性 ──────────────────────────────────────────────────

  get count(): number { return this._count; }
  get positions(): Float32Array { return this._positions; }
  get colors(): Float32Array { return this._colors; }

  // ── GPU 初始化 ────────────────────────────────────────────

  /**
   * 初始化所有 GPU 缓冲区和 VAO。
   * 必须在 WebGL2 上下文中调用。
   */
  initGL(gl: WebGL2RenderingContext): void {
    this._gl = gl;

    // ── Billboard 四边形 VBO + IBO ──────────────────────────
    this._quadVBO = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this._quadVBO);
    gl.bufferData(gl.ARRAY_BUFFER, this._quadVerts, gl.STATIC_DRAW);

    this._quadIBO = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this._quadIBO);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, this._quadIdx, gl.STATIC_DRAW);

    // ── 实例属性 VBO（Dynamic，会频繁更新）─────────────────
    this._posVBO = this._createDynamicBuffer(gl, this._positions);
    this._colVBO = this._createDynamicBuffer(gl, this._colors);
    this._propVBO = this._createDynamicBuffer(gl, this._props);

    // ── VAO 绑定 ────────────────────────────────────────────
    this._vao = gl.createVertexArray();
    gl.bindVertexArray(this._vao);

    // location 0: aQuadVertex (vec2)
    gl.bindBuffer(gl.ARRAY_BUFFER, this._quadVBO);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    // location 1: aOffset (vec3) — 实例属性
    this._bindInstanceAttrib(gl, this._posVBO, 1, 3, INSTANCE_STRIDE_FLOATS, 0, 1);

    // location 2: aColor (vec4) — 实例属性
    this._bindInstanceAttrib(gl, this._colVBO, 2, 4, 0, 0, 1);

    // location 3: aSize (float) — 实例属性
    this._bindInstanceAttrib(gl, this._propVBO, 3, 1, 3, 0, 1);

    // location 4: aGlowIntensity (float) — 实例属性
    this._bindInstanceAttrib(gl, this._propVBO, 4, 1, 3, 1, 1);

    // location 5: aSelected (float) — 实例属性
    this._bindInstanceAttrib(gl, this._propVBO, 5, 1, 3, 2, 1);

    gl.bindVertexArray(null);
  }

  // ── 数据写入 ──────────────────────────────────────────────

  /**
   * 批量写入特征点数据。
   * 写入后调用 upload() 将 dirty 区域上传到 GPU。
   */
  setPoints(points: PointData[]): void {
    const n = Math.min(points.length, this.maxPoints);
    this._count = n;

    for (let i = 0; i < n; i++) {
      const p = points[i];
      const i3 = i * 3;
      const i4 = i * 4;

      // 位置
      this._positions[i3]     = p.x;
      this._positions[i3 + 1] = p.y;
      this._positions[i3 + 2] = p.z ?? 0;

      // 颜色
      this._colors[i4]     = p.r;
      this._colors[i4 + 1] = p.g;
      this._colors[i4 + 2] = p.b;
      this._colors[i4 + 3] = p.a ?? 1.0;

      // 属性
      this._props[i3]     = p.size ?? 4.0;
      this._props[i3 + 1] = p.glowIntensity ?? 0.0;
      this._props[i3 + 2] = p.selected ? 1.0 : 0.0;
    }

    // 标记全量 dirty
    this._dirtyStart = 0;
    this._dirtyEnd = n;
  }

  /**
   * 更新单个点的位置（用于拖拽/动画）。
   */
  updatePosition(index: number, x: number, y: number, z?: number): void {
    if (index >= this._count) return;
    const i3 = index * 3;
    this._positions[i3]     = x;
    this._positions[i3 + 1] = y;
    this._positions[i3 + 2] = z ?? 0;
    this._markDirty(index);
  }

  /**
   * 批量更新选中状态（高性能热路径）。
   */
  updateSelection(indices: number[], selected: boolean): void {
    const val = selected ? 1.0 : 0.0;
    for (const idx of indices) {
      if (idx >= this._count) continue;
      this._props[idx * 3 + 2] = val;
      this._markDirty(idx);
    }
  }

  // ── GPU 上传 ──────────────────────────────────────────────

  /**
   * 将 dirty 区域上传到 GPU。
   * 仅上传 _dirtyStart ~ _dirtyEnd 区间，避免全量 bufferSubData。
   */
  upload(): void {
    const gl = this._gl;
    if (!gl || this._dirtyEnd <= this._dirtyStart) return;

    const start = this._dirtyStart;
    const end   = this._dirtyEnd;

    // 位置缓冲区：3 floats/点
    const posOffset = start * 3 * 4;  // byte offset
    const posLen    = (end - start) * 3;
    gl.bindBuffer(gl.ARRAY_BUFFER, this._posVBO);
    gl.bufferSubData(gl.ARRAY_BUFFER, posOffset,
                     this._positions.subarray(start * 3, start * 3 + posLen));

    // 颜色缓冲区：4 floats/点
    const colOffset = start * 4 * 4;
    const colLen    = (end - start) * 4;
    gl.bindBuffer(gl.ARRAY_BUFFER, this._colVBO);
    gl.bufferSubData(gl.ARRAY_BUFFER, colOffset,
                     this._colors.subarray(start * 4, start * 4 + colLen));

    // 属性缓冲区：3 floats/点
    const propOffset = start * 3 * 4;
    const propLen    = (end - start) * 3;
    gl.bindBuffer(gl.ARRAY_BUFFER, this._propVBO);
    gl.bufferSubData(gl.ARRAY_BUFFER, propOffset,
                     this._props.subarray(start * 3, start * 3 + propLen));

    // 重置 dirty 范围
    this._dirtyStart = Infinity;
    this._dirtyEnd = -1;
  }

  // ── 渲染 ──────────────────────────────────────────────────

  /**
   * 执行 Instanced Rendering 的 drawCall。
   * 单次调用渲染所有点。
   */
  draw(): void {
    const gl = this._gl;
    if (!gl || !this._vao || this._count === 0) return;

    gl.bindVertexArray(this._vao);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this._quadIBO);
    // Instanced draw: 6 indices per quad, this._count instances
    gl.drawElementsInstanced(gl.TRIANGLES, 6, gl.UNSIGNED_SHORT, 0, this._count);
    gl.bindVertexArray(null);
  }

  // ── 清理 ──────────────────────────────────────────────────

  dispose(): void {
    const gl = this._gl;
    if (!gl) return;
    gl.deleteBuffer(this._quadVBO);
    gl.deleteBuffer(this._quadIBO);
    gl.deleteBuffer(this._posVBO);
    gl.deleteBuffer(this._colVBO);
    gl.deleteBuffer(this._propVBO);
    gl.deleteVertexArray(this._vao);
    this._gl = null;
  }

  // ── 内部辅助 ──────────────────────────────────────────────

  private _createDynamicBuffer(gl: WebGL2RenderingContext, data: Float32Array): WebGLBuffer {
    const buf = gl.createBuffer()!;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, data.byteLength, gl.DYNAMIC_DRAW);
    return buf;
  }

  private _bindInstanceAttrib(
    gl: WebGL2RenderingContext,
    vbo: WebGLBuffer,
    location: number,
    size: number,
    stride: number,
    offset: number,
    divisor: number,
  ): void {
    gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location, size, gl.FLOAT, false,
                           stride * 4, offset * 4);
    gl.vertexAttribDivisor(location, divisor);
  }

  private _markDirty(index: number): void {
    if (index < this._dirtyStart) this._dirtyStart = index;
    if (index >= this._dirtyEnd)  this._dirtyEnd = index + 1;
  }

  // ── 128 维降维颜色映射 ────────────────────────────────────

  /**
   * 将 128 维嵌入向量降维映射到 RGB 色彩空间。
   *
   * 算法：
   *  1. 对 128 维向量进行 PCA-like 投影到 3 维
   *     (使用固定的随机投影矩阵，保证确定性)
   *  2. 将 3 维投影归一化到 [0, 1]
   *  3. 应用 HSV 色彩空间增强对比度
   *
   * @param embedding 128 维浮点向量
   * @returns [r, g, b] 归一化到 [0, 1]
   */
  static embeddingToRGB(embedding: number[]): [number, number, number] {
    const dim = embedding.length;
    // 简化的哈希投影（确定性、零分配）
    let h0 = 0, h1 = 0, h2 = 0;
    for (let i = 0; i < dim; i++) {
      const v = embedding[i];
      // 三个不同的素数种子产生三个独立投影
      h0 += v * Math.sin(i * 0.1 + 0.0);
      h1 += v * Math.sin(i * 0.1 + 2.094);  // 2π/3
      h2 += v * Math.sin(i * 0.1 + 4.189);  // 4π/3
    }
    // 归一化到 [0, 1]
    const scale = 1.0 / (Math.sqrt(dim) * 1.5);
    const r = Math.max(0, Math.min(1, h0 * scale + 0.5));
    const g = Math.max(0, Math.min(1, h1 * scale + 0.5));
    const b = Math.max(0, Math.min(1, h2 * scale + 0.5));
    return [r, g, b];
  }
}
