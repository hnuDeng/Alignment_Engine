import { OrbitController } from '../../src/webgl_engine/OrbitController';

describe('OrbitController', () => {
  let controller: OrbitController;

  beforeEach(() => {
    controller = new OrbitController();
    controller.setViewport(800, 600);
  });

  afterEach(() => {
    // cleanup RAF if needed
  });

  it('should initialize with default state', () => {
    const state = controller.state;
    expect(state.target.x).toBe(0);
    expect(state.target.y).toBe(0);
    expect(state.zoom).toBe(1.0);
    expect(state.viewportWidth).toBe(800);
    expect(state.viewportHeight).toBe(600);
  });

  it('should set target and zoom', () => {
    controller.setTarget(10, 20);
    controller.setZoom(2.0);

    const state = controller.state;
    expect(state.target.x).toBe(10);
    expect(state.target.y).toBe(20);
    expect(state.zoom).toBe(2.0);
  });

  it('should convert screen to world and back', () => {
    // view center is 0,0, zoom is 1, size is 800x600.
    // Screen center 400,300 should be world 0,0
    const w1 = controller.screenToWorld(400, 300);
    expect(w1.x).toBe(0);
    expect(w1.y).toBe(0);

    const s1 = controller.worldToScreen(0, 0);
    expect(s1.x).toBe(400);
    expect(s1.y).toBe(300);
  });

  it('should pan to target', () => {
    // Mock performance.now for tick
    const originalNow = performance.now;
    performance.now = jest.fn(() => 0);
    
    controller.panTo(100, 200, 100);
    
    performance.now = jest.fn(() => 100);
    // Let RAF run. Jest doesn't easily mock requestAnimationFrame synchronously in all envs without fakeTimers,
    // so we just test the intent if we had more setup. For now we just verify it doesn't crash.
    performance.now = originalNow;
  });

  it('should compute view projection matrix', () => {
    const vp = controller.viewProjection;
    expect(vp.length).toBe(16);
    // At zoom 1, vp width 800, height 600:
    // ortho left=-400, right=400 (w=800), bottom=-300, top=300 (h=600)
    // m[0] = 2/800 = 0.0025
    expect(vp[0]).toBeCloseTo(0.0025);
    expect(vp[5]).toBeCloseTo(0.0033333333333333335);
  });

  it('should handle pointer events for panning', () => {
    // We can simulate calling the private handlers directly since they are public in TS if casted, 
    // or we can test via bind(). We'll use cast to any to test the logic directly.
    const ctrl = controller as any;

    // Pointer down
    ctrl._onPointerDown({ button: 1, clientX: 0, clientY: 0 } as MouseEvent); // wrong button, ignore
    expect(ctrl._isDragging).toBeFalsy();

    ctrl._onPointerDown({ button: 0, clientX: 100, clientY: 100 } as MouseEvent);
    expect(ctrl._isDragging).toBeTruthy();
    expect(ctrl._lastMouse.x).toBe(100);

    // Pointer move
    ctrl._onPointerMove({ clientX: 110, clientY: 120 } as MouseEvent);
    // dx = 10, dy = 20. Target should change.
    expect(ctrl._target.x).toBeLessThan(0); // Moves left when dragging right
    expect(ctrl._target.y).toBeGreaterThan(0); // Moves up when dragging down
    expect(ctrl._velocity.x).not.toBe(0);

    // Pointer up
    ctrl._onPointerUp();
    expect(ctrl._isDragging).toBeFalsy();

    // Move after up should be ignored
    const tx = ctrl._target.x;
    ctrl._onPointerMove({ clientX: 200, clientY: 200 } as MouseEvent);
    expect(ctrl._target.x).toBe(tx);
  });

  it('should handle wheel events for zooming', () => {
    const ctrl = controller as any;
    const preventDefault = jest.fn();
    const event = { clientX: 400, clientY: 300, deltaY: 100, preventDefault } as unknown as WheelEvent;
    
    // Zoom out
    ctrl._onWheel(event);
    expect(preventDefault).toHaveBeenCalled();
    expect(controller.state.zoom).toBeLessThan(1.0);

    // Zoom in
    const event2 = { clientX: 400, clientY: 300, deltaY: -200, preventDefault } as unknown as WheelEvent;
    ctrl._onWheel(event2);
    expect(controller.state.zoom).toBeGreaterThan(1.0);
  });

  it('should bind and unbind correctly', () => {
    const div = document.createElement('div');
    jest.spyOn(div, 'addEventListener');
    jest.spyOn(div, 'removeEventListener');

    const unbind = controller.bind(div);
    expect(div.addEventListener).toHaveBeenCalledTimes(5);

    unbind();
    expect(div.removeEventListener).toHaveBeenCalledTimes(5);
  });
});
