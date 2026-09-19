export class WebGLException extends Error {
    constructor(message: string) {
        super(`WebGLException: ${message}`);
        this.name = 'WebGLException';
    }
}

export class BufferExhaustionException extends WebGLException {
    constructor(message: string) {
        super(`BufferExhaustionException: ${message}`);
        this.name = 'BufferExhaustionException';
    }
}

export class OctreeBuildException extends WebGLException {
    constructor(message: string) {
        super(`OctreeBuildException: ${message}`);
        this.name = 'OctreeBuildException';
    }
}

export interface Point3D {
    x: number;
    y: number;
    z: number;
    id: number;
}

export class OctreeNode {
    bounds: { min: Point3D, max: Point3D };
    points: Point3D[] = [];
    children: OctreeNode[] | null = null;
    capacity: number = 64;

    constructor(min: Point3D, max: Point3D) {
        this.bounds = { min, max };
    }

    insert(point: Point3D): boolean {
        if (!this.contains(point)) return false;

        if (this.points.length < this.capacity && this.children === null) {
            this.points.push(point);
            return true;
        }

        if (this.children === null) {
            this.subdivide();
        }

        for (const child of this.children!) {
            if (child.insert(point)) return true;
        }

        throw new OctreeBuildException("Failed to insert point into Octree");
    }

    contains(point: Point3D): boolean {
        return point.x >= this.bounds.min.x && point.x <= this.bounds.max.x &&
               point.y >= this.bounds.min.y && point.y <= this.bounds.max.y &&
               point.z >= this.bounds.min.z && point.z <= this.bounds.max.z;
    }

    subdivide() {
        const min = this.bounds.min;
        const max = this.bounds.max;
        const mid = {
            x: (min.x + max.x) / 2,
            y: (min.y + max.y) / 2,
            z: (min.z + max.z) / 2,
            id: -1
        };

        this.children = [
            new OctreeNode(min, mid),
            new OctreeNode({ x: mid.x, y: min.y, z: min.z, id: -1 }, { x: max.x, y: mid.y, z: mid.z, id: -1 }),
            new OctreeNode({ x: min.x, y: mid.y, z: min.z, id: -1 }, { x: mid.x, y: max.y, z: mid.z, id: -1 }),
            new OctreeNode({ x: mid.x, y: mid.y, z: min.z, id: -1 }, { x: max.x, y: max.y, z: mid.z, id: -1 }),
            new OctreeNode({ x: min.x, y: min.y, z: mid.z, id: -1 }, { x: mid.x, y: mid.y, z: max.z, id: -1 }),
            new OctreeNode({ x: mid.x, y: min.y, z: mid.z, id: -1 }, { x: max.x, y: mid.y, z: max.z, id: -1 }),
            new OctreeNode({ x: min.x, y: mid.y, z: mid.z, id: -1 }, { x: mid.x, y: max.y, z: max.z, id: -1 }),
            new OctreeNode(mid, max)
        ];

        for (const p of this.points) {
            for (const child of this.children) {
                if (child.insert(p)) break;
            }
        }
        this.points = [];
    }

    raycast(rayOrigin: Point3D, rayDir: Point3D, maxDist: number): Point3D | null {
        // Implementation of AABB intersection for O(log N) picking
        if (!this.intersectRayAABB(rayOrigin, rayDir)) return null;

        let closest: Point3D | null = null;
        let minDist = maxDist;

        if (this.children === null) {
            for (const p of this.points) {
                const dist = Math.hypot(p.x - rayOrigin.x, p.y - rayOrigin.y, p.z - rayOrigin.z);
                if (dist < minDist) {
                    minDist = dist;
                    closest = p;
                }
            }
        } else {
            for (const child of this.children) {
                const hit = child.raycast(rayOrigin, rayDir, minDist);
                if (hit) {
                    const dist = Math.hypot(hit.x - rayOrigin.x, hit.y - rayOrigin.y, hit.z - rayOrigin.z);
                    if (dist < minDist) {
                        minDist = dist;
                        closest = hit;
                    }
                }
            }
        }
        return closest;
    }

    private intersectRayAABB(origin: Point3D, dir: Point3D): boolean {
        let tmin = (this.bounds.min.x - origin.x) / dir.x;
        let tmax = (this.bounds.max.x - origin.x) / dir.x;
        if (tmin > tmax) { const temp = tmin; tmin = tmax; tmax = temp; }

        let tymin = (this.bounds.min.y - origin.y) / dir.y;
        let tymax = (this.bounds.max.y - origin.y) / dir.y;
        if (tymin > tymax) { const temp = tymin; tymin = tymax; tymax = temp; }

        if ((tmin > tymax) || (tymin > tmax)) return false;
        if (tymin > tmin) tmin = tymin;
        if (tymax < tmax) tmax = tymax;

        let tzmin = (this.bounds.min.z - origin.z) / dir.z;
        let tzmax = (this.bounds.max.z - origin.z) / dir.z;
        if (tzmin > tzmax) { const temp = tzmin; tzmin = tzmax; tzmax = temp; }

        if ((tmin > tzmax) || (tzmin > tmax)) return false;

        return true;
    }
}

export class InstancedScatter {
    gl: WebGL2RenderingContext;
    program: WebGLProgram;
    maxPoints: number;
    positionsBuffer: Float32Array;
    colorsBuffer: Float32Array;
    vao: WebGLVertexArrayObject;
    octree: OctreeNode;

    constructor(canvas: HTMLCanvasElement, maxPoints: number = 1000000) {
        const gl = canvas.getContext('webgl2');
        if (!gl) throw new WebGLException("WebGL2 not supported");
        this.gl = gl;
        this.maxPoints = maxPoints;

        // Initialize buffers
        this.positionsBuffer = new Float32Array(maxPoints * 3);
        this.colorsBuffer = new Float32Array(maxPoints * 3);
        
        // Initialize Octree bounds roughly
        this.octree = new OctreeNode({ x: -100, y: -100, z: -100, id: -1 }, { x: 100, y: 100, z: 100, id: -1 });

        const vao = this.gl.createVertexArray();
        if (!vao) throw new WebGLException("Failed to create VAO");
        this.vao = vao;
        
        // Program is assumed to be compiled via external shader strings
        this.program = this.gl.createProgram()!;
    }

    updateData(points: Point3D[], colors: Float32Array) {
        if (points.length > this.maxPoints) {
            throw new BufferExhaustionException(`Exceeded max points ${this.maxPoints}`);
        }

        // Rebuild Octree
        this.octree = new OctreeNode({ x: -100, y: -100, z: -100, id: -1 }, { x: 100, y: 100, z: 100, id: -1 });
        for (let i = 0; i < points.length; i++) {
            this.positionsBuffer[i*3] = points[i].x;
            this.positionsBuffer[i*3+1] = points[i].y;
            this.positionsBuffer[i*3+2] = points[i].z;
            this.octree.insert(points[i]);
        }
        this.colorsBuffer.set(colors);
        
        // Upload to GPU
        // (Omitted gl.bindBuffer, gl.bufferData boilerplate for brevity, but strictly implemented in real scenario)
    }

    render() {
        this.gl.useProgram(this.program);
        this.gl.bindVertexArray(this.vao);
        // Instanced draw call
        this.gl.drawArraysInstanced(this.gl.TRIANGLES, 0, 6, this.maxPoints);
    }
}
