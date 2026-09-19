/**
 * @file OrbitController.ts
 * @brief 2D/3D 相机轨道控制器 —— 缩放、平移、旋转的流畅交互
 *
 * 设计要点：
 *  1. 正交相机模式：2D 散点图无需透视
 *  2. 惯性缓动：松开鼠标后保持惯性滑动（指数衰减）
 *  3. 缩放限制：最小/最大缩放范围，防止过度缩放
 *  4. 事件驱动：通过回调通知上层相机矩阵更新
 *  5. requestAnimationFrame 驱动平滑插值
 */

// ── 类型 ─────────────────────────────────────────────────────

/** 4x4 矩阵（列主序，兼容 WebGL） */
export type Mat4 = Float32Array;  // 16 elements

/** 2D 向量 */
export interface Vec2 { x: number; y: number; }

/** 相机状态 */
export interface CameraState {
  /** 视图中心（世界坐标） */
  target: Vec2;
  /** 缩放级别（像素/世界单位） */
  zoom: number;
  /** 视图宽度（像素） */
  viewportWidth: number;
  /** 视图高度（像素） */
  viewportHeight: number;
}

/** 控制器配置 */
export interface OrbitConfig {
  /** 最小缩放 */
  minZoom?: number;
  /** 最大缩放 */
  maxZoom?: number;
  /** 惯性衰减系数（0~1，越小衰减越快） */
  inertiaDecay?: number;
  /** 缩放灵敏度 */
  zoomSensitivity?: number;
  /** 平移灵敏度 */
  panSensitivity?: number;
}

// ── 默认配置 ─────────────────────────────────────────────────

const DEFAULT_CONFIG: Required<OrbitConfig> = {
  minZoom: 0.1,
  maxZoom: 1000,
  inertiaDecay: 0.92,
  zoomSensitivity: 0.001,
  panSensitivity: 1.0,
};

// ── 矩阵辅助 ────────────────────────────────────────────────

function createIdentity(): Mat4 {
  const m = new Float32Array(16);
  m[0] = m[5] = m[10] = m[15] = 1;
  return m;
}

function orthoProjection(
  left: number, right: number,
  bottom: number, top: number,
  near: number, far: number,
): Mat4 {
  const m = new Float32Array(16);
  const rl = right - left, tb = top - bottom, fn = far - near;
  m[0]  = 2 / rl;
  m[5]  = 2 / tb;
  m[10] = -2 / fn;
  m[12] = -(right + left) / rl;
  m[13] = -(top + bottom) / tb;
  m[14] = -(far + near) / fn;
  m[15] = 1;
  return m;
}

function multiply(a: Mat4, b: Mat4): Mat4 {
  const out = new Float32Array(16);
  for (let i = 0; i < 4; i++) {
    for (let j = 0; j < 4; j++) {
      out[j * 4 + i] =
        a[i]      * b[j * 4]     +
        a[4 + i]  * b[j * 4 + 1] +
        a[8 + i]  * b[j * 4 + 2] +
        a[12 + i] * b[j * 4 + 3];
    }
  }
  return out;
}

function translationMatrix(tx: number, ty: number): Mat4 {
  const m = createIdentity();
  m[12] = tx;
  m[13] = ty;
  return m;
}


// ══════════════════════════════════════════════════════════════
// OrbitController
// ══════════════════════════════════════════════════════════════

export class OrbitController {
  // ── 相机状态 ──────────────────────────────────────────────
  private _target: Vec2 = { x: 0, y: 0 };
  private _zoom = 1.0;
  private _vpW = 800;
  private _vpH = 600;

  // ── 惯性 ──────────────────────────────────────────────────
  private _velocity: Vec2 = { x: 0, y: 0 };
  private _isDragging = false;
  private _lastMouse: Vec2 = { x: 0, y: 0 };

  // ── 配置 ──────────────────────────────────────────────────
  private readonly _config: Required<OrbitConfig>;

  // ── 矩阵缓存 ──────────────────────────────────────────────
  private _viewProjection: Mat4 = createIdentity();
  private _dirty = true;

  // ── 回调 ──────────────────────────────────────────────────
  private _onUpdate: ((vp: Mat4) => void) | null = null;

  // ── RAF handle ─────────────────────────────────────────────
  private _rafId = 0;

  constructor(config: OrbitConfig = {}) {
    this._config = { ...DEFAULT_CONFIG, ...config };
  }

  // ── 属性 ──────────────────────────────────────────────────

  get target(): Vec2 { return this._target; }
  get zoom(): number { return this._zoom; }
  get viewProjection(): Mat4 {
    if (this._dirty) this._recomputeMatrix();
    return this._viewProjection;
  }

  get state(): CameraState {
    return {
      target: { ...this._target },
      zoom: this._zoom,
      viewportWidth: this._vpW,
      viewportHeight: this._vpH,
    };
  }

  /** 设置矩阵更新回调 */
  set onUpdate(fn: ((vp: Mat4) => void) | null) {
    this._onUpdate = fn;
  }

  // ── 视口设置 ──────────────────────────────────────────────

  setViewport(width: number, height: number): void {
    this._vpW = width;
    this._vpH = height;
    this._dirty = true;
  }

  // ── 鼠标事件绑定 ──────────────────────────────────────────

  /**
   * 绑定到 HTML 元素的鼠标事件。
   * 返回清理函数。
   */
  bind(element: HTMLElement): () => void {
    const onDown  = (e: MouseEvent) => this._onPointerDown(e);
    const onMove  = (e: MouseEvent) => this._onPointerMove(e);
    const onUp    = ()              => this._onPointerUp();
    const onWheel = (e: WheelEvent) => this._onWheel(e);

    element.addEventListener("mousedown", onDown);
    element.addEventListener("mousemove", onMove);
    element.addEventListener("mouseup", onUp);
    element.addEventListener("mouseleave", onUp);
    element.addEventListener("wheel", onWheel, { passive: false });

    // 启动惯性动画循环
    this._startInertiaLoop();

    return () => {
      element.removeEventListener("mousedown", onDown);
      element.removeEventListener("mousemove", onMove);
      element.removeEventListener("mouseup", onUp);
      element.removeEventListener("mouseleave", onUp);
      element.removeEventListener("wheel", onWheel);
      cancelAnimationFrame(this._rafId);
    };
  }

  // ── 编程式控制 ────────────────────────────────────────────

  /** 设置视图中心 */
  setTarget(x: number, y: number): void {
    this._target.x = x;
    this._target.y = y;
    this._dirty = true;
    this._notifyUpdate();
  }

  /** 设置缩放级别 */
  setZoom(zoom: number): void {
    this._zoom = Math.max(this._config.minZoom,
                          Math.min(this._config.maxZoom, zoom));
    this._dirty = true;
    this._notifyUpdate();
  }

  /** 平移到指定位置（带动画） */
  panTo(x: number, y: number, durationMs = 300): void {
    const startX = this._target.x;
    const startY = this._target.y;
    const startTime = performance.now();

    const tick = () => {
      const t = Math.min(1, (performance.now() - startTime) / durationMs);
      const ease = t * t * (3 - 2 * t);  // smoothstep
      this._target.x = startX + (x - startX) * ease;
      this._target.y = startY + (y - startY) * ease;
      this._dirty = true;
      this._notifyUpdate();
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  /** 屏幕坐标 → 世界坐标 */
  screenToWorld(screenX: number, screenY: number): Vec2 {
    // 从屏幕中心算偏移，除以缩放，加上目标
    const halfW = this._vpW / 2;
    const halfH = this._vpH / 2;
    return {
      x: (screenX - halfW) / this._zoom + this._target.x,
      y: (halfH - screenY) / this._zoom + this._target.y,  // Y 翻转
    };
  }

  /** 世界坐标 → 屏幕坐标 */
  worldToScreen(worldX: number, worldY: number): Vec2 {
    const halfW = this._vpW / 2;
    const halfH = this._vpH / 2;
    return {
      x: (worldX - this._target.x) * this._zoom + halfW,
      y: halfH - (worldY - this._target.y) * this._zoom,
    };
  }

  // ── 内部事件处理 ──────────────────────────────────────────

  private _onPointerDown(e: MouseEvent): void {
    if (e.button !== 0) return;  // 仅左键
    this._isDragging = true;
    this._lastMouse = { x: e.clientX, y: e.clientY };
    this._velocity = { x: 0, y: 0 };
  }

  private _onPointerMove(e: MouseEvent): void {
    if (!this._isDragging) return;

    const dx = e.clientX - this._lastMouse.x;
    const dy = e.clientY - this._lastMouse.y;

    // 平移：屏幕像素差 → 世界单位差
    this._target.x -= dx / this._zoom * this._config.panSensitivity;
    this._target.y += dy / this._zoom * this._config.panSensitivity;

    // 记录惯性速度
    this._velocity.x = -dx / this._zoom * this._config.panSensitivity;
    this._velocity.y =  dy / this._zoom * this._config.panSensitivity;

    this._lastMouse = { x: e.clientX, y: e.clientY };
    this._dirty = true;
    this._notifyUpdate();
  }

  private _onPointerUp(): void {
    this._isDragging = false;
    // 惯性动画由 _startInertiaLoop 持续驱动
  }

  private _onWheel(e: WheelEvent): void {
    e.preventDefault();

    // 鼠标位置 → 世界坐标（缩放前）
    const worldBefore = this.screenToWorld(e.clientX, e.clientY);

    // 缩放
    const factor = 1 - e.deltaY * this._config.zoomSensitivity;
    this._zoom = Math.max(this._config.minZoom,
                          Math.min(this._config.maxZoom, this._zoom * factor));

    // 鼠标位置 → 世界坐标（缩放后）
    const worldAfter = this.screenToWorld(e.clientX, e.clientY);

    // 调整 target 使鼠标下的世界坐标不变（缩放中心 = 鼠标）
    this._target.x += worldBefore.x - worldAfter.x;
    this._target.y += worldBefore.y - worldAfter.y;

    this._dirty = true;
    this._notifyUpdate();
  }

  // ── 惯性动画循环 ──────────────────────────────────────────

  private _startInertiaLoop(): void {
    const tick = () => {
      if (!this._isDragging) {
        const decay = this._config.inertiaDecay;
        this._velocity.x *= decay;
        this._velocity.y *= decay;

        if (Math.abs(this._velocity.x) > 0.001 ||
            Math.abs(this._velocity.y) > 0.001) {
          this._target.x += this._velocity.x;
          this._target.y += this._velocity.y;
          this._dirty = true;
          this._notifyUpdate();
        }
      }
      this._rafId = requestAnimationFrame(tick);
    };
    this._rafId = requestAnimationFrame(tick);
  }

  // ── 矩阵重算 ──────────────────────────────────────────────

  private _recomputeMatrix(): void {
    const halfW = this._vpW / (2 * this._zoom);
    const halfH = this._vpH / (2 * this._zoom);

    // 正交投影：以 target 为中心
    const proj = orthoProjection(
      -halfW, halfW,
      -halfH, halfH,
      -1, 1,
    );

    // 平移到 target
    const view = translationMatrix(-this._target.x, -this._target.y);

    // viewProjection = proj * view
    this._viewProjection = multiply(proj, view);
    this._dirty = false;
  }

  private _notifyUpdate(): void {
    this._onUpdate?.(this.viewProjection);
  }
}
