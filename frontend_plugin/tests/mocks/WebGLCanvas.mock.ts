/**
 * @file tests/mocks/WebGLCanvas.mock.ts
 * @brief Comprehensive WebGL2 context mock for CI environments without GPU.
 *
 * Intercepts all WebGL2RenderingContext calls, records them for assertion,
 * and returns deterministic values. Supports:
 *  - Shader compilation/linking simulation
 *  - Buffer creation and data upload tracking
 *  - Uniform location and value recording
 *  - Draw call parameter capture
 *  - VAO/VBO state machine simulation
 *  - Extension queries
 *  - Error injection for failure testing
 */

// ══════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════

export interface MockBuffer {
  id: number;
  target: number;
  data: ArrayBuffer | ArrayBufferView | null;
  usage: number;
  size: number;
}

export interface MockShader {
  id: number;
  type: number;
  source: string;
  compiled: boolean;
  compileLog: string;
}

export interface MockProgram {
  id: number;
  shaders: number[];
  linked: boolean;
  linkLog: string;
  uniformLocations: Map<string, MockUniformLocation>;
  attribLocations: Map<string, number>;
}

export interface MockUniformLocation {
  name: string;
  type: string;
  value: unknown;
}

export interface MockTexture {
  id: number;
  target: number;
  width: number;
  height: number;
}

export interface MockFramebuffer {
  id: number;
}

export interface MockVertexArrayObject {
  id: number;
  attribs: Map<number, AttribState>;
}

export interface AttribState {
  enabled: boolean;
  size: number;
  type: number;
  normalized: boolean;
  stride: number;
  offset: number;
  buffer: number | null;
  divisor: number;
}

export interface DrawCallRecord {
  mode: number;
  count: number;
  type: number;
  offset: number;
  instanceCount?: number;
}

export interface GLStateRecord {
  clearColor: [number, number, number, number];
  clearDepth: number;
  viewport: [number, number, number, number];
  blendSrc: number;
  blendDst: number;
  depthTest: boolean;
  blend: boolean;
  scissorTest: boolean;
}

export interface MockWebGL2ContextOptions {
  /** Force shader compilation to fail */
  forceShaderFail?: boolean;
  /** Force program link to fail */
  forceLinkFail?: boolean;
  /** Max texture size (default 4096) */
  maxTextureSize?: number;
  /** Max renderbuffer size (default 4096) */
  maxRenderbufferSize?: number;
  /** Simulated renderer string */
  renderer?: string;
}

// ══════════════════════════════════════════════════════════════
// WebGL2 constant map (subset used by the engine)
// ══════════════════════════════════════════════════════════════

const GL_CONSTANTS: Record<string, number> = {
  // Buffer targets
  ARRAY_BUFFER: 34962,
  ELEMENT_ARRAY_BUFFER: 34963,
  // Usage
  STATIC_DRAW: 35044,
  DYNAMIC_DRAW: 35048,
  STREAM_DRAW: 35040,
  // Shader types
  VERTEX_SHADER: 35633,
  FRAGMENT_SHADER: 35632,
  // Shader/program params
  COMPILE_STATUS: 35713,
  LINK_STATUS: 35714,
  DELETE_STATUS: 35712,
  INFO_LOG_LENGTH: 35716,
  // Draw modes
  TRIANGLES: 4,
  TRIANGLE_STRIP: 5,
  TRIANGLE_FAN: 6,
  LINES: 1,
  LINE_STRIP: 3,
  POINTS: 0,
  // Data types
  FLOAT: 5126,
  UNSIGNED_BYTE: 5121,
  UNSIGNED_SHORT: 5123,
  UNSIGNED_INT: 5125,
  INT: 5124,
  BYTE: 5120,
  SHORT: 5122,
  // Clear bits
  COLOR_BUFFER_BIT: 16384,
  DEPTH_BUFFER_BIT: 256,
  STENCIL_BUFFER_BIT: 1024,
  // State
  DEPTH_TEST: 2929,
  BLEND: 3042,
  SCISSOR_TEST: 3089,
  CULL_FACE: 2884,
  // Blend
  SRC_ALPHA: 770,
  ONE_MINUS_SRC_ALPHA: 771,
  ONE: 1,
  ZERO: 0,
  // Texture
  TEXTURE_2D: 3553,
  TEXTURE0: 33984,
  RGBA: 6408,
  RGB: 6407,
  // Boolean
  TRUE: 1,
  FALSE: 0,
  // Errors
  NO_ERROR: 0,
  INVALID_ENUM: 1280,
  INVALID_VALUE: 1281,
  INVALID_OPERATION: 1282,
  OUT_OF_MEMORY: 1285,
  // Get params
  MAX_TEXTURE_SIZE: 3379,
  MAX_RENDERBUFFER_SIZE: 34024,
  RENDERER: 7937,
  VERSION: 7938,
  // Framebuffer
  FRAMEBUFFER: 36160,
  COLOR_ATTACHMENT0: 36064,
  // Misc
  TEXTURE_WRAP_S: 10242,
  TEXTURE_WRAP_T: 10243,
  TEXTURE_MIN_FILTER: 10241,
  TEXTURE_MAG_FILTER: 10240,
  CLAMP_TO_EDGE: 33071,
  LINEAR: 9729,
  NEAREST: 9728,
  UNPACK_ALIGNMENT: 3317,
  PACK_ALIGNMENT: 3333,
};

// ══════════════════════════════════════════════════════════════
// MockWebGL2Context
// ══════════════════════════════════════════════════════════════

export class MockWebGL2Context {
  // ── Object pools ───────────────────────────────────────────
  private _nextId = 1;
  readonly buffers = new Map<number, MockBuffer>();
  readonly shaders = new Map<number, MockShader>();
  readonly programs = new Map<number, MockProgram>();
  readonly textures = new Map<number, MockTexture>();
  readonly framebuffers = new Map<number, MockFramebuffer>();
  readonly vaos = new Map<number, MockVertexArrayObject>();

  // ── State tracking ─────────────────────────────────────────
  readonly state: GLStateRecord = {
    clearColor: [0, 0, 0, 1],
    clearDepth: 1,
    viewport: [0, 0, 0, 0],
    blendSrc: 0,
    blendDst: 0,
    depthTest: false,
    blend: false,
    scissorTest: false,
  };

  // ── Call recording ─────────────────────────────────────────
  readonly drawCalls: DrawCallRecord[] = [];
  readonly callLog: Array<{ method: string; args: unknown[] }> = [];

  // ── Current bindings ───────────────────────────────────────
  private _currentArrayBuffer: number | null = null;
  private _currentElementBuffer: number | null = null;
  private _currentProgram: number | null = null;
  private _currentVAO: number | null = null;
  private _currentTexture: number | null = null;
  private _currentFramebuffer: number | null = null;

  // ── Options ────────────────────────────────────────────────
  private readonly _options: MockWebGL2ContextOptions;

  constructor(options: MockWebGL2ContextOptions = {}) {
    this._options = options;

    // Add all GL constants as properties
    for (const [name, value] of Object.entries(GL_CONSTANTS)) {
      (this as Record<string, unknown>)[name] = value;
    }
  }

  // ── Logging helper ─────────────────────────────────────────

  private _log(method: string, ...args: unknown[]): void {
    this.callLog.push({ method, args });
  }

  // ── ID allocation ──────────────────────────────────────────

  private _allocId(): number {
    return this._nextId++;
  }

  // ── Buffer operations ──────────────────────────────────────

  createBuffer(): WebGLBuffer {
    const id = this._allocId();
    const buf: MockBuffer = { id, target: 0, data: null, usage: 0, size: 0 };
    this.buffers.set(id, buf);
    this._log("createBuffer");
    return { __id: id } as unknown as WebGLBuffer;
  }

  deleteBuffer(buffer: WebGLBuffer): void {
    const id = (buffer as unknown as { __id: number }).__id;
    this.buffers.delete(id);
    this._log("deleteBuffer", id);
  }

  bindBuffer(target: number, buffer: WebGLBuffer | null): void {
    const id = buffer ? (buffer as unknown as { __id: number }).__id : null;
    if (target === GL_CONSTANTS.ARRAY_BUFFER) this._currentArrayBuffer = id;
    else if (target === GL_CONSTANTS.ELEMENT_ARRAY_BUFFER) this._currentElementBuffer = id;
    if (id) {
      const buf = this.buffers.get(id);
      if (buf) buf.target = target;
    }
    this._log("bindBuffer", target, id);
  }

  bufferData(target: number, srcOrSize: ArrayBuffer | ArrayBufferView | number, usage: number): void {
    const bufId = target === GL_CONSTANTS.ARRAY_BUFFER ? this._currentArrayBuffer : this._currentElementBuffer;
    const buf = bufId ? this.buffers.get(bufId) : null;
    if (buf) {
      buf.usage = usage;
      if (typeof srcOrSize === "number") {
        buf.size = srcOrSize;
        buf.data = null;
      } else {
        buf.size = (srcOrSize as ArrayBufferView).byteLength ?? (srcOrSize as ArrayBuffer).byteLength;
        buf.data = srcOrSize;
      }
    }
    this._log("bufferData", target, typeof srcOrSize === "number" ? srcOrSize : "[data]", usage);
  }

  bufferSubData(target: number, dstByteOffset: number, _src: ArrayBuffer | ArrayBufferView): void {
    this._log("bufferSubData", target, dstByteOffset, "[data]");
  }

  // ── Shader operations ──────────────────────────────────────

  createShader(type: number): WebGLShader {
    const id = this._allocId();
    const shader: MockShader = { id, type, source: "", compiled: false, compileLog: "" };
    this.shaders.set(id, shader);
    this._log("createShader", type);
    return { __id: id } as unknown as WebGLShader;
  }

  deleteShader(shader: WebGLShader): void {
    const id = (shader as unknown as { __id: number }).__id;
    this.shaders.delete(id);
    this._log("deleteShader", id);
  }

  shaderSource(shader: WebGLShader, source: string): void {
    const id = (shader as unknown as { __id: number }).__id;
    const s = this.shaders.get(id);
    if (s) s.source = source;
    this._log("shaderSource", id, source.length);
  }

  compileShader(shader: WebGLShader): void {
    const id = (shader as unknown as { __id: number }).__id;
    const s = this.shaders.get(id);
    if (s) {
      s.compiled = !this._options.forceShaderFail;
      s.compileLog = this._options.forceShaderFail ? "Mock compilation error" : "";
    }
    this._log("compileShader", id);
  }

  getShaderParameter(shader: WebGLShader, pname: number): unknown {
    const id = (shader as unknown as { __id: number }).__id;
    const s = this.shaders.get(id);
    if (!s) return null;
    if (pname === GL_CONSTANTS.COMPILE_STATUS) return s.compiled;
    if (pname === GL_CONSTANTS.DELETE_STATUS) return false;
    return null;
  }

  getShaderInfoLog(shader: WebGLShader): string {
    const id = (shader as unknown as { __id: number }).__id;
    return this.shaders.get(id)?.compileLog ?? "";
  }

  // ── Program operations ─────────────────────────────────────

  createProgram(): WebGLProgram {
    const id = this._allocId();
    const prog: MockProgram = {
      id,
      shaders: [],
      linked: false,
      linkLog: "",
      uniformLocations: new Map(),
      attribLocations: new Map(),
    };
    this.programs.set(id, prog);
    this._log("createProgram");
    return { __id: id } as unknown as WebGLProgram;
  }

  deleteProgram(program: WebGLProgram): void {
    const id = (program as unknown as { __id: number }).__id;
    this.programs.delete(id);
    this._log("deleteProgram", id);
  }

  attachShader(program: WebGLProgram, shader: WebGLShader): void {
    const pid = (program as unknown as { __id: number }).__id;
    const sid = (shader as unknown as { __id: number }).__id;
    const p = this.programs.get(pid);
    if (p) p.shaders.push(sid);
    this._log("attachShader", pid, sid);
  }

  detachShader(_program: WebGLProgram, _shader: WebGLShader): void {
    this._log("detachShader");
  }

  linkProgram(program: WebGLProgram): void {
    const pid = (program as unknown as { __id: number }).__id;
    const p = this.programs.get(pid);
    if (p) {
      p.linked = !this._options.forceLinkFail;
      p.linkLog = this._options.forceLinkFail ? "Mock link error" : "";
    }
    this._log("linkProgram", pid);
  }

  useProgram(program: WebGLProgram | null): void {
    this._currentProgram = program ? (program as unknown as { __id: number }).__id : null;
    this._log("useProgram", this._currentProgram);
  }

  getProgramParameter(program: WebGLProgram, pname: number): unknown {
    const pid = (program as unknown as { __id: number }).__id;
    const p = this.programs.get(pid);
    if (!p) return null;
    if (pname === GL_CONSTANTS.LINK_STATUS) return p.linked;
    if (pname === GL_CONSTANTS.DELETE_STATUS) return false;
    return null;
  }

  getProgramInfoLog(program: WebGLProgram): string {
    const pid = (program as unknown as { __id: number }).__id;
    return this.programs.get(pid)?.linkLog ?? "";
  }

  // ── Uniform operations ─────────────────────────────────────

  getUniformLocation(program: WebGLProgram, name: string): WebGLUniformLocation | null {
    const pid = (program as unknown as { __id: number }).__id;
    const p = this.programs.get(pid);
    if (!p) return null;
    if (!p.uniformLocations.has(name)) {
      p.uniformLocations.set(name, { name, type: "unknown", value: null });
    }
    this._log("getUniformLocation", pid, name);
    return { __pid: pid, name } as unknown as WebGLUniformLocation;
  }

  uniform1i(location: WebGLUniformLocation | null, v: number): void {
    this._setUniform(location, "1i", v);
  }
  uniform1f(location: WebGLUniformLocation | null, v: number): void {
    this._setUniform(location, "1f", v);
  }
  uniform2f(location: WebGLUniformLocation | null, x: number, y: number): void {
    this._setUniform(location, "2f", [x, y]);
  }
  uniform3f(location: WebGLUniformLocation | null, x: number, y: number, z: number): void {
    this._setUniform(location, "3f", [x, y, z]);
  }
  uniform4f(location: WebGLUniformLocation | null, x: number, y: number, z: number, w: number): void {
    this._setUniform(location, "4f", [x, y, z, w]);
  }
  uniformMatrix4fv(location: WebGLUniformLocation | null, _transpose: boolean, value: Float32List): void {
    this._setUniform(location, "mat4", value);
  }

  private _setUniform(location: WebGLUniformLocation | null, type: string, value: unknown): void {
    if (!location) return;
    const loc = location as unknown as { __pid: number; name: string };
    const p = this.programs.get(loc.__pid);
    if (p) {
      const u = p.uniformLocations.get(loc.name);
      if (u) { u.type = type; u.value = value; }
    }
    this._log(`uniform${type}`, loc.name, value);
  }

  // ── Vertex attribute operations ────────────────────────────

  getAttribLocation(program: WebGLProgram, name: string): number {
    const pid = (program as unknown as { __id: number }).__id;
    const p = this.programs.get(pid);
    if (!p) return -1;
    const loc = p.attribLocations.size;
    p.attribLocations.set(name, loc);
    this._log("getAttribLocation", pid, name, loc);
    return loc;
  }

  enableVertexAttribArray(index: number): void {
    const vao = this._currentVAO ? this.vaos.get(this._currentVAO) : null;
    if (vao) {
      const attr = vao.attribs.get(index);
      if (attr) attr.enabled = true;
    }
    this._log("enableVertexAttribArray", index);
  }

  disableVertexAttribArray(index: number): void {
    this._log("disableVertexAttribArray", index);
  }

  vertexAttribPointer(index: number, size: number, type: number, normalized: boolean, stride: number, offset: number): void {
    const vao = this._currentVAO ? this.vaos.get(this._currentVAO) : null;
    if (vao) {
      vao.attribs.set(index, {
        enabled: true, size, type, normalized, stride, offset,
        buffer: this._currentArrayBuffer, divisor: 0,
      });
    }
    this._log("vertexAttribPointer", index, size, type, normalized, stride, offset);
  }

  vertexAttribDivisor(index: number, divisor: number): void {
    const vao = this._currentVAO ? this.vaos.get(this._currentVAO) : null;
    if (vao) {
      const attr = vao.attribs.get(index);
      if (attr) attr.divisor = divisor;
    }
    this._log("vertexAttribDivisor", index, divisor);
  }

  // ── VAO operations ─────────────────────────────────────────

  createVertexArray(): WebGLVertexArrayObject {
    const id = this._allocId();
    const vao: MockVertexArrayObject = { id, attribs: new Map() };
    this.vaos.set(id, vao);
    this._log("createVertexArray");
    return { __id: id } as unknown as WebGLVertexArrayObject;
  }

  deleteVertexArray(vao: WebGLVertexArrayObject): void {
    const id = (vao as unknown as { __id: number }).__id;
    this.vaos.delete(id);
    this._log("deleteVertexArray", id);
  }

  bindVertexArray(vao: WebGLVertexArrayObject | null): void {
    this._currentVAO = vao ? (vao as unknown as { __id: number }).__id : null;
    this._log("bindVertexArray", this._currentVAO);
  }

  // ── Texture operations ─────────────────────────────────────

  createTexture(): WebGLTexture {
    const id = this._allocId();
    const tex: MockTexture = { id, target: 0, width: 0, height: 0 };
    this.textures.set(id, tex);
    this._log("createTexture");
    return { __id: id } as unknown as WebGLTexture;
  }

  deleteTexture(texture: WebGLTexture): void {
    const id = (texture as unknown as { __id: number }).__id;
    this.textures.delete(id);
    this._log("deleteTexture", id);
  }

  bindTexture(target: number, texture: WebGLTexture | null): void {
    this._currentTexture = texture ? (texture as unknown as { __id: number }).__id : null;
    this._log("bindTexture", target, this._currentTexture);
  }

  texParameteri(target: number, pname: number, param: number): void {
    this._log("texParameteri", target, pname, param);
  }

  texImage2D(...args: unknown[]): void {
    this._log("texImage2D", ...args);
  }

  activeTexture(texture: number): void {
    this._log("activeTexture", texture);
  }

  // ── Framebuffer operations ─────────────────────────────────

  createFramebuffer(): WebGLFramebuffer {
    const id = this._allocId();
    this.framebuffers.set(id, { id });
    this._log("createFramebuffer");
    return { __id: id } as unknown as WebGLFramebuffer;
  }

  deleteFramebuffer(fb: WebGLFramebuffer): void {
    const id = (fb as unknown as { __id: number }).__id;
    this.framebuffers.delete(id);
    this._log("deleteFramebuffer", id);
  }

  bindFramebuffer(target: number, fb: WebGLFramebuffer | null): void {
    this._currentFramebuffer = fb ? (fb as unknown as { __id: number }).__id : null;
    this._log("bindFramebuffer", target, this._currentFramebuffer);
  }

  framebufferTexture2D(target: number, attachment: number, texTarget: number, texture: WebGLTexture | null, level: number): void {
    this._log("framebufferTexture2D", target, attachment, texTarget, texture, level);
  }

  // ── Draw operations ────────────────────────────────────────

  drawArrays(mode: number, first: number, count: number): void {
    this.drawCalls.push({ mode, count, type: 0, offset: first });
    this._log("drawArrays", mode, first, count);
  }

  drawElements(mode: number, count: number, type: number, offset: number): void {
    this.drawCalls.push({ mode, count, type, offset });
    this._log("drawElements", mode, count, type, offset);
  }

  drawArraysInstanced(mode: number, first: number, count: number, instanceCount: number): void {
    this.drawCalls.push({ mode, count, type: 0, offset: first, instanceCount });
    this._log("drawArraysInstanced", mode, first, count, instanceCount);
  }

  drawElementsInstanced(mode: number, count: number, type: number, offset: number, instanceCount: number): void {
    this.drawCalls.push({ mode, count, type, offset, instanceCount });
    this._log("drawElementsInstanced", mode, count, type, offset, instanceCount);
  }

  // ── State operations ───────────────────────────────────────

  clearColor(r: number, g: number, b: number, a: number): void {
    this.state.clearColor = [r, g, b, a];
    this._log("clearColor", r, g, b, a);
  }

  clearDepth(depth: number): void {
    this.state.clearDepth = depth;
    this._log("clearDepth", depth);
  }

  clear(mask: number): void {
    this._log("clear", mask);
  }

  viewport(x: number, y: number, width: number, height: number): void {
    this.state.viewport = [x, y, width, height];
    this._log("viewport", x, y, width, height);
  }

  enable(cap: number): void {
    if (cap === GL_CONSTANTS.DEPTH_TEST) this.state.depthTest = true;
    if (cap === GL_CONSTANTS.BLEND) this.state.blend = true;
    if (cap === GL_CONSTANTS.SCISSOR_TEST) this.state.scissorTest = true;
    this._log("enable", cap);
  }

  disable(cap: number): void {
    if (cap === GL_CONSTANTS.DEPTH_TEST) this.state.depthTest = false;
    if (cap === GL_CONSTANTS.BLEND) this.state.blend = false;
    if (cap === GL_CONSTANTS.SCISSOR_TEST) this.state.scissorTest = false;
    this._log("disable", cap);
  }

  blendFunc(sfactor: number, dfactor: number): void {
    this.state.blendSrc = sfactor;
    this.state.blendDst = dfactor;
    this._log("blendFunc", sfactor, dfactor);
  }

  pixelStorei(pname: number, param: number): void {
    this._log("pixelStorei", pname, param);
  }

  // ── Query operations ───────────────────────────────────────

  getParameter(pname: number): unknown {
    if (pname === GL_CONSTANTS.MAX_TEXTURE_SIZE) return this._options.maxTextureSize ?? 4096;
    if (pname === GL_CONSTANTS.MAX_RENDERBUFFER_SIZE) return this._options.maxRenderbufferSize ?? 4096;
    if (pname === GL_CONSTANTS.RENDERER) return this._options.renderer ?? "MockWebGL2";
    if (pname === GL_CONSTANTS.VERSION) return "WebGL2 Mock";
    return null;
  }

  getError(): number {
    return GL_CONSTANTS.NO_ERROR;
  }

  getSupportedExtensions(): string[] {
    return ["EXT_color_buffer_float", "OES_texture_float_linear"];
  }

  getExtension(_name: string): unknown {
    return {};
  }

  // ── Scissor ────────────────────────────────────────────────

  scissor(x: number, y: number, width: number, height: number): void {
    this._log("scissor", x, y, width, height);
  }

  // ── Read pixels ────────────────────────────────────────────

  readPixels(x: number, y: number, width: number, height: number, format: number, type: number, dstData: ArrayBufferView | null): void {
    this._log("readPixels", x, y, width, height, format, type);
    // Fill with zeros
    if (dstData && "fill" in dstData) {
      (dstData as Float32Array).fill(0);
    }
  }

  // ── Flush / Finish ─────────────────────────────────────────

  flush(): void { this._log("flush"); }
  finish(): void { this._log("finish"); }

  // ── Test utilities ─────────────────────────────────────────

  /** Get the last draw call */
  get lastDrawCall(): DrawCallRecord | undefined {
    return this.drawCalls[this.drawCalls.length - 1];
  }

  /** Get all calls to a specific method */
  getCallsTo(method: string): Array<{ method: string; args: unknown[] }> {
    return this.callLog.filter((c) => c.method === method);
  }

  /** Get uniform value from current program */
  getUniform(name: string): unknown {
    if (!this._currentProgram) return undefined;
    const p = this.programs.get(this._currentProgram);
    return p?.uniformLocations.get(name)?.value;
  }

  /** Get the number of draw calls */
  get drawCallCount(): number {
    return this.drawCalls.length;
  }

  /** Get the number of buffers created */
  get bufferCount(): number {
    return this.buffers.size;
  }

  /** Reset all recorded state (for test isolation) */
  reset(): void {
    this.drawCalls.length = 0;
    this.callLog.length = 0;
    this.buffers.clear();
    this.shaders.clear();
    this.programs.clear();
    this.textures.clear();
    this.framebuffers.clear();
    this.vaos.clear();
    this._nextId = 1;
    this._currentArrayBuffer = null;
    this._currentElementBuffer = null;
    this._currentProgram = null;
    this._currentVAO = null;
    this._currentTexture = null;
    this._currentFramebuffer = null;
  }
}

// ══════════════════════════════════════════════════════════════
// Factory: create a mock canvas element with WebGL2 context
// ══════════════════════════════════════════════════════════════

export function createMockCanvas(
  options: MockWebGL2ContextOptions = {},
): { canvas: HTMLCanvasElement; gl: MockWebGL2Context } {
  const gl = new MockWebGL2Context(options);

  const canvas = {
    clientWidth: 800,
    clientHeight: 600,
    width: 800,
    height: 600,
    style: {},
    getContext: (type: string) => {
      if (type === "webgl2") return gl as unknown as WebGL2RenderingContext;
      return null;
    },
    getBoundingClientRect: () => ({
      left: 0, top: 0, right: 800, bottom: 600, width: 800, height: 600,
    }),
    addEventListener: () => {},
    removeEventListener: () => {},
  } as unknown as HTMLCanvasElement;

  return { canvas, gl };
}

// ══════════════════════════════════════════════════════════════
// Mock requestAnimationFrame
// ══════════════════════════════════════════════════════════════

export function installRafMock(): { restore: () => void; flush: () => void } {
  const callbacks = new Map<number, FrameRequestCallback>();
  let nextId = 1;

  const raf = (cb: FrameRequestCallback): number => {
    const id = nextId++;
    callbacks.set(id, cb);
    return id;
  };

  const caf = (id: number): void => {
    callbacks.delete(id);
  };

  const originalRaf = globalThis.requestAnimationFrame;
  const originalCaf = globalThis.cancelAnimationFrame;

  globalThis.requestAnimationFrame = raf as unknown as typeof requestAnimationFrame;
  globalThis.cancelAnimationFrame = caf as typeof cancelAnimationFrame;

  return {
    restore: () => {
      globalThis.requestAnimationFrame = originalRaf;
      globalThis.cancelAnimationFrame = originalCaf;
    },
    flush: () => {
      const pending = Array.from(callbacks.entries());
      callbacks.clear();
      for (const [, cb] of pending) {
        cb(performance.now());
      }
    },
  };
}
