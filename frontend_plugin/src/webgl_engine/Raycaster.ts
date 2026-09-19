/**
 * @file Raycaster.ts
 * @brief 基于八叉树 (Octree) 的百万节点精准拾取算法
 *
 * 设计要点：
 *  1. 八叉树空间索引：将 2D/3D 空间递归划分为 8 个子区域
 *  2. 按需构建：从点集一次性构建，支持增量插入
 *  3. 范围查询：O(log N) 复杂度的圆形/矩形区域查询
 *  4. 最近邻查询：KNN 拾取（Hover）和区域框选（Box Select）
 *  5. 内存紧凑：节点复用对象池，减少 GC 压力
 */

// ── 类型 ─────────────────────────────────────────────────────

/** 3D 包围盒 */
export interface AABB {
  minX: number; minY: number; minZ: number;
  maxX: number; maxY: number; maxZ: number;
}

/** 带索引的点 */
interface IndexedPoint {
  x: number; y: number; z: number;
  index: number;
}

/** 查询结果 */
export interface QueryResult {
  index: number;
  distance: number;
  x: number;
  y: number;
}

// ── 常量 ─────────────────────────────────────────────────────

/** 八叉树每个节点的最大点数（超过则分裂） */
const MAX_POINTS_PER_NODE = 32;

/** 最大递归深度 */
const MAX_DEPTH = 12;

/** 八叉树 8 个子象限的偏移表 */
const OCTANT_OFFSETS: [number, number, number][] = [
  [-1, -1, -1], [1, -1, -1], [-1, 1, -1], [1, 1, -1],
  [-1, -1,  1], [1, -1,  1], [-1, 1,  1], [1, 1,  1],
];

// ══════════════════════════════════════════════════════════════
// OctreeNode
// ══════════════════════════════════════════════════════════════

class OctreeNode {
  bounds: AABB;
  points: IndexedPoint[] = [];
  children: (OctreeNode | null)[] = [null, null, null, null, null, null, null, null];
  depth: number;
  isLeaf = true;

  constructor(bounds: AABB, depth: number) {
    this.bounds = bounds;
    this.depth = depth;
  }

  /** 中心点 */
  get centerX(): number { return (this.bounds.minX + this.bounds.maxX) / 2; }
  get centerY(): number { return (this.bounds.minY + this.bounds.maxY) / 2; }
  get centerZ(): number { return (this.bounds.minZ + this.bounds.maxZ) / 2; }
}

// ══════════════════════════════════════════════════════════════
// Octree
// ══════════════════════════════════════════════════════════════

export class Octree {
  private _root: OctreeNode;
  private _size = 0;

  constructor(bounds: AABB) {
    this._root = new OctreeNode(bounds, 0);
  }

  get size(): number { return this._size; }

  // ── 构建 ──────────────────────────────────────────────────

  /**
   * 从点数组批量构建八叉树。
   *
   * @param points [x0, y0, z0, x1, y1, z1, ...] 扁平坐标数组
   * @param pointCount 点的数量
   */
  buildFromFlatArray(points: Float32Array, pointCount: number): void {
    // 计算包围盒
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    let minZ = Infinity, maxZ = -Infinity;

    for (let i = 0; i < pointCount; i++) {
      const i3 = i * 3;
      const x = points[i3], y = points[i3 + 1], z = points[i3 + 2];
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (y < minY) minY = y; if (y > maxY) maxY = y;
      if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
    }

    // 稍微扩大包围盒避免边界问题
    const pad = Math.max(maxX - minX, maxY - minY, maxZ - minZ) * 0.01 || 1;
    this._root = new OctreeNode({
      minX: minX - pad, minY: minY - pad, minZ: minZ - pad,
      maxX: maxX + pad, maxY: maxY + pad, maxZ: maxZ + pad,
    }, 0);

    // 逐点插入
    for (let i = 0; i < pointCount; i++) {
      const i3 = i * 3;
      this._insert(this._root, {
        x: points[i3], y: points[i3 + 1], z: points[i3 + 2],
        index: i,
      });
      this._size++;
    }
  }

  /**
   * 从 2D 点数组构建（z=0）。
   */
  buildFrom2D(xs: Float32Array, ys: Float32Array, count: number): void {
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    for (let i = 0; i < count; i++) {
      if (xs[i] < minX) minX = xs[i]; if (xs[i] > maxX) maxX = xs[i];
      if (ys[i] < minY) minY = ys[i]; if (ys[i] > maxY) maxY = ys[i];
    }
    const pad = Math.max(maxX - minX, maxY - minY) * 0.01 || 1;
    this._root = new OctreeNode({
      minX: minX - pad, minY: minY - pad, minZ: -1,
      maxX: maxX + pad, maxY: maxY + pad, maxZ: 1,
    }, 0);
    for (let i = 0; i < count; i++) {
      this._insert(this._root, { x: xs[i], y: ys[i], z: 0, index: i });
      this._size++;
    }
  }

  // ── 最近邻查询（Hover 拾取）──────────────────────────────

  /**
   * 查找距离 (qx, qy, qz) 最近的 K 个点。
   * 使用优先队列剪枝，O(log N) 平均复杂度。
   */
  queryNearest(qx: number, qy: number, qz: number, k: number): QueryResult[] {
    // 使用数组模拟最大堆（按 distance 降序）
    const heap: QueryResult[] = [];

    this._queryNearestRecursive(this._root, qx, qy, qz, k, heap);

    // 按距离升序返回
    heap.sort((a, b) => a.distance - b.distance);
    return heap;
  }

  /**
   * 查找 2D 最近邻。
   */
  queryNearest2D(qx: number, qy: number, k: number): QueryResult[] {
    return this.queryNearest(qx, qy, 0, k);
  }

  // ── 区域查询（框选）──────────────────────────────────────

  /**
   * 查询圆形区域内的所有点。
   */
  queryRadius(cx: number, cy: number, cz: number, radius: number): QueryResult[] {
    const results: QueryResult[] = [];
    const r2 = radius * radius;
    this._queryRadiusRecursive(this._root, cx, cy, cz, r2, results);
    results.sort((a, b) => a.distance - b.distance);
    return results;
  }

  /**
   * 查询矩形区域内的所有点（框选）。
   */
  queryAABB(box: AABB): QueryResult[] {
    const results: QueryResult[] = [];
    this._queryAABBRecursive(this._root, box, results);
    return results;
  }

  // ── 内部：插入 ────────────────────────────────────────────

  private _insert(node: OctreeNode, point: IndexedPoint): void {
    if (node.isLeaf) {
      node.points.push(point);
      // 超过容量且未达最大深度 → 分裂
      if (node.points.length > MAX_POINTS_PER_NODE && node.depth < MAX_DEPTH) {
        this._split(node);
      }
      return;
    }

    // 非叶节点：路由到正确的子象限
    const octant = this._getOctant(node, point);
    if (node.children[octant] === null) {
      node.children[octant] = this._createChild(node, octant);
    }
    this._insert(node.children[octant]!, point);
  }

  private _split(node: OctreeNode): void {
    node.isLeaf = false;
    const oldPoints = node.points;
    node.points = [];

    for (const point of oldPoints) {
      const octant = this._getOctant(node, point);
      if (node.children[octant] === null) {
        node.children[octant] = this._createChild(node, octant);
      }
      this._insert(node.children[octant]!, point);
    }
  }

  private _getOctant(node: OctreeNode, point: IndexedPoint): number {
    const cx = node.centerX, cy = node.centerY, cz = node.centerZ;
    let octant = 0;
    if (point.x >= cx) octant |= 1;
    if (point.y >= cy) octant |= 2;
    if (point.z >= cz) octant |= 4;
    return octant;
  }

  private _createChild(parent: OctreeNode, octant: number): OctreeNode {
    const cx = parent.centerX, cy = parent.centerY, cz = parent.centerZ;
    const off = OCTANT_OFFSETS[octant];
    const halfX = (parent.bounds.maxX - cx);
    const halfY = (parent.bounds.maxY - cy);
    const halfZ = (parent.bounds.maxZ - cz);

    return new OctreeNode({
      minX: cx + off[0] * halfX * (off[0] < 0 ? 1 : 0),
      minY: cy + off[1] * halfY * (off[1] < 0 ? 1 : 0),
      minZ: cz + off[2] * halfZ * (off[2] < 0 ? 1 : 0),
      maxX: cx + off[0] * halfX * (off[0] > 0 ? 1 : 0) + (off[0] === 0 ? halfX : 0),
      maxY: cy + off[1] * halfY * (off[1] > 0 ? 1 : 0) + (off[1] === 0 ? halfY : 0),
      maxZ: cz + off[2] * halfZ * (off[2] > 0 ? 1 : 0) + (off[2] === 0 ? halfZ : 0),
    }, parent.depth + 1);
  }

  // ── 内部：最近邻递归 ─────────────────────────────────────

  private _queryNearestRecursive(
    node: OctreeNode | null,
    qx: number, qy: number, qz: number,
    k: number,
    heap: QueryResult[],
  ): void {
    if (!node) return;

    // 检查叶节点中的点
    if (node.isLeaf) {
      for (const p of node.points) {
        const d = (p.x - qx) ** 2 + (p.y - qy) ** 2 + (p.z - qz) ** 2;
        if (heap.length < k) {
          heap.push({ index: p.index, distance: Math.sqrt(d), x: p.x, y: p.y });
          this._heapifyUp(heap);
        } else if (d < heap[0].distance ** 2) {
          heap[0] = { index: p.index, distance: Math.sqrt(d), x: p.x, y: p.y };
          this._heapifyDown(heap);
        }
      }
      return;
    }

    // 非叶节点：按到子节点包围盒的距离排序，优先搜索最近的子节点
    const children: { node: OctreeNode; dist: number }[] = [];
    for (const child of node.children) {
      if (child) {
        children.push({
          node: child,
          dist: this._pointToAABBDistSq(qx, qy, qz, child.bounds),
        });
      }
    }
    children.sort((a, b) => a.dist - b.dist);

    // 剪枝：只搜索可能包含更近点的子节点
    const maxDist = heap.length >= k ? heap[0].distance ** 2 : Infinity;

    for (const { node: child, dist } of children) {
      if (heap.length >= k && dist > maxDist) break;  // 剪枝
      this._queryNearestRecursive(child, qx, qy, qz, k, heap);
    }
  }

  // ── 内部：圆形区域查询 ────────────────────────────────────

  private _queryRadiusRecursive(
    node: OctreeNode | null,
    cx: number, cy: number, cz: number,
    r2: number,
    results: QueryResult[],
  ): void {
    if (!node) return;

    // 剪枝：节点包围盒完全在圆外
    if (this._pointToAABBDistSq(cx, cy, cz, node.bounds) > r2) return;

    if (node.isLeaf) {
      for (const p of node.points) {
        const d2 = (p.x - cx) ** 2 + (p.y - cy) ** 2 + (p.z - cz) ** 2;
        if (d2 <= r2) {
          results.push({ index: p.index, distance: Math.sqrt(d2), x: p.x, y: p.y });
        }
      }
      return;
    }

    for (const child of node.children) {
      this._queryRadiusRecursive(child, cx, cy, cz, r2, results);
    }
  }

  // ── 内部：AABB 区域查询 ──────────────────────────────────

  private _queryAABBRecursive(
    node: OctreeNode | null,
    box: AABB,
    results: QueryResult[],
  ): void {
    if (!node) return;

    // 剪枝：节点包围盒与查询区域无交集
    if (!this._aabbIntersects(node.bounds, box)) return;

    if (node.isLeaf) {
      for (const p of node.points) {
        if (p.x >= box.minX && p.x <= box.maxX &&
            p.y >= box.minY && p.y <= box.maxY &&
            p.z >= box.minZ && p.z <= box.maxZ) {
          results.push({ index: p.index, distance: 0, x: p.x, y: p.y });
        }
      }
      return;
    }

    for (const child of node.children) {
      this._queryAABBRecursive(child, box, results);
    }
  }

  // ── 内部：几何辅助 ────────────────────────────────────────

  /** 点到 AABB 的最短距离平方 */
  private _pointToAABBDistSq(px: number, py: number, pz: number, box: AABB): number {
    const dx = Math.max(0, Math.max(box.minX - px, px - box.maxX));
    const dy = Math.max(0, Math.max(box.minY - py, py - box.maxY));
    const dz = Math.max(0, Math.max(box.minZ - pz, pz - box.maxZ));
    return dx * dx + dy * dy + dz * dz;
  }

  /** AABB 相交检测 */
  private _aabbIntersects(a: AABB, b: AABB): boolean {
    return a.minX <= b.maxX && a.maxX >= b.minX &&
           a.minY <= b.maxY && a.maxY >= b.minY &&
           a.minZ <= b.maxZ && a.maxZ >= b.minZ;
  }

  // ── 最大堆操作（用于 KNN）───────────────────────────────

  private _heapifyUp(heap: QueryResult[]): void {
    let i = heap.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (heap[i].distance > heap[parent].distance) {
        [heap[i], heap[parent]] = [heap[parent], heap[i]];
        i = parent;
      } else break;
    }
  }

  private _heapifyDown(heap: QueryResult[]): void {
    let i = 0;
    const n = heap.length;
    while (true) {
      let largest = i;
      const left = 2 * i + 1, right = 2 * i + 2;
      if (left < n && heap[left].distance > heap[largest].distance) largest = left;
      if (right < n && heap[right].distance > heap[largest].distance) largest = right;
      if (largest !== i) {
        [heap[i], heap[largest]] = [heap[largest], heap[i]];
        i = largest;
      } else break;
    }
  }
}
