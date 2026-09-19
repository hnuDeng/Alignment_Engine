import { Octree } from '../../src/webgl_engine/Raycaster';

describe('Octree', () => {
  it('should build from 2D points and trigger split', () => {
    const N = 100;
    const xs = new Float32Array(N);
    const ys = new Float32Array(N);
    for (let i = 0; i < N; i++) {
        xs[i] = i - 50;
        ys[i] = i - 50;
    }
    const tree = new Octree({ minX: -50, maxX: 50, minY: -50, maxY: 50, minZ: -50, maxZ: 50 });
    
    tree.buildFrom2D(xs, ys, N);
    expect(tree.size).toBe(N);
  });

  it('should build from flat 3D array', () => {
    const pts = new Float32Array([
      0, 0, 0,
      10, 10, 10,
      -10, -10, -10
    ]);
    const tree = new Octree({ minX: -50, maxX: 50, minY: -50, maxY: 50, minZ: -50, maxZ: 50 });
    tree.buildFromFlatArray(pts, 3);
    expect(tree.size).toBe(3);
  });

  it('should query nearest 2D', () => {
    const xs = new Float32Array([0, 10, 20]);
    const ys = new Float32Array([0, 10, 20]);
    const tree = new Octree({ minX: -50, maxX: 50, minY: -50, maxY: 50, minZ: -50, maxZ: 50 });
    tree.buildFrom2D(xs, ys, 3);

    const res = tree.queryNearest2D(9, 9, 1);
    expect(res.length).toBe(1);
    expect(res[0].index).toBe(1); // 10, 10
  });

  it('should query nearest 3D', () => {
    const pts = new Float32Array([
      0, 0, 0,
      10, 10, 10,
      -10, -10, -10
    ]);
    const tree = new Octree({ minX: -50, maxX: 50, minY: -50, maxY: 50, minZ: -50, maxZ: 50 });
    tree.buildFromFlatArray(pts, 3);

    const res = tree.queryNearest(8, 8, 8, 2);
    expect(res.length).toBe(2);
    expect(res[0].index).toBe(1); // nearest is 10,10,10
    expect(res[1].index).toBe(0); // second is 0,0,0
  });

  it('should query radius', () => {
    const xs = new Float32Array([0, 10, 20]);
    const ys = new Float32Array([0, 10, 20]);
    const tree = new Octree({ minX: -50, maxX: 50, minY: -50, maxY: 50, minZ: -50, maxZ: 50 });
    tree.buildFrom2D(xs, ys, 3);

    const res = tree.queryRadius(0, 0, 0, 5);
    expect(res.length).toBe(1);
    expect(res[0].index).toBe(0);

    const res2 = tree.queryRadius(0, 0, 0, 15);
    expect(res2.length).toBe(2); // 0,0 and 10,10 are within 15 units of 0,0
  });

  it('should query AABB', () => {
    const xs = new Float32Array([0, 10, 20]);
    const ys = new Float32Array([0, 10, 20]);
    const tree = new Octree({ minX: -50, maxX: 50, minY: -50, maxY: 50, minZ: -50, maxZ: 50 });
    tree.buildFrom2D(xs, ys, 3);

    const res = tree.queryAABB({ minX: 5, maxX: 15, minY: 5, maxY: 15, minZ: -10, maxZ: 10 });
    expect(res.length).toBe(1);
    expect(res[0].index).toBe(1);
  });
});
