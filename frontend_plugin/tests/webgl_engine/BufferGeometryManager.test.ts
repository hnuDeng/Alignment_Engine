import { BufferGeometryManager } from '../../src/webgl_engine/BufferGeometryManager';
import { createMockCanvas } from '../mocks/WebGLCanvas.mock';

describe('BufferGeometryManager', () => {
  let manager: BufferGeometryManager;
  let gl: WebGL2RenderingContext;

  beforeEach(() => {
    const mock = createMockCanvas();
    gl = mock.gl as unknown as WebGL2RenderingContext;
    manager = new BufferGeometryManager({ maxPoints: 100 });
  });

  afterEach(() => {
    manager.dispose();
  });

  it('should initialize with correct maxPoints', () => {
    expect(manager.maxPoints).toBe(100);
    expect(manager.count).toBe(0);
  });

  it('should initGL and create buffers', () => {
    manager.initGL(gl);
    // basic check to ensure no crash
    expect(manager['maxPoints']).toBe(100);
  });

  it('should set points correctly', () => {
    manager.initGL(gl);
    manager.setPoints([
      { x: 1, y: 2, r: 0.1, g: 0.2, b: 0.3 }
    ]);
    expect(manager.count).toBe(1);
    expect(manager.positions[0]).toBe(1);
    expect(manager.positions[1]).toBe(2);
    expect(manager.positions[2]).toBe(0); // z defaults to 0
    expect(manager.colors[0]).toBeCloseTo(0.1);
    expect(manager.colors[1]).toBeCloseTo(0.2);
    expect(manager.colors[2]).toBeCloseTo(0.3);
    expect(manager.colors[3]).toBe(1.0); // a defaults to 1.0
  });

  it('should upload without errors', () => {
    manager.initGL(gl);
    manager.setPoints([{ x: 1, y: 2, r: 0.1, g: 0.2, b: 0.3 }]);
    manager.upload();
    // Test passes if upload doesn't throw
  });

  it('should update position', () => {
    manager.initGL(gl);
    manager.setPoints([{ x: 1, y: 2, r: 0.1, g: 0.2, b: 0.3 }]);
    manager.updatePosition(0, 5, 6, 7);
    expect(manager.positions[0]).toBe(5);
    expect(manager.positions[1]).toBe(6);
    expect(manager.positions[2]).toBe(7);
  });

  it('should update selection', () => {
    manager.initGL(gl);
    manager.setPoints([{ x: 1, y: 2, r: 0.1, g: 0.2, b: 0.3 }]);
    manager.updateSelection([0], true);
    // prop is size, glow, selected
    expect(manager['_props'][2]).toBe(1.0);
  });

  it('should draw', () => {
    manager.initGL(gl);
    manager.setPoints([{ x: 1, y: 2, r: 0.1, g: 0.2, b: 0.3 }]);
    manager.draw();
    // Test passes if draw doesn't throw
  });

  it('should convert embedding to RGB', () => {
    const rgb = BufferGeometryManager.embeddingToRGB(new Array(128).fill(0.5));
    expect(rgb.length).toBe(3);
    expect(rgb[0]).toBeGreaterThanOrEqual(0);
    expect(rgb[0]).toBeLessThanOrEqual(1);
  });
});
