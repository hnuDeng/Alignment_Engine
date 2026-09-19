/**
 * vertex_shader.glsl —— 实例化渲染特征点着色器
 *
 * 设计要点：
 *  1. 使用 gl_InstanceID 实现 Instanced Rendering，单次 drawCall 渲染百万点
 *  2. 每实例属性：offset(vec3), color(vec4), size(float), glowIntensity(float)
 *  3. Billboard 四边形：每个特征点由 4 个顶点组成的正方形面片
 *  4. 相机自适应缩放：点大小根据投影深度动态调整
 *  5. 脉冲动画：异常样本 (glowIntensity > 0) 执行 sin 波动
 */

#version 300 es
precision highp float;

// ── 顶点属性（Billboard 四边形的 4 个角）────────────────────
layout(location = 0) in vec2 aQuadVertex;  // [-0.5, 0.5] x [-0.5, 0.5]

// ── 实例属性（每特征点一个实例）────────────────────────────
layout(location = 1) in vec3  aOffset;         // 特征点世界坐标 (x, y, z)
layout(location = 2) in vec4  aColor;          // RGBA 颜色 (0~1)
layout(location = 3) in float aSize;           // 点基础大小 (像素)
layout(location = 4) in float aGlowIntensity;  // 发光强度 (0=正常, >0=异常发光)
layout(location = 5) in float aSelected;       // 选中状态 (0/1)

// ── Uniform ─────────────────────────────────────────────────
uniform mat4  uViewProjection;  // 视图投影矩阵
uniform vec3  uCameraRight;     // 相机右向量 (Billboard X 轴)
uniform vec3  uCameraUp;        // 相机上向量 (Billboard Y 轴)
uniform float uTime;            // 全局时间 (秒)
uniform float uPointSizeScale;  // 全局点大小缩放因子
uniform float uPixelRatio;      // 设备像素比

// ── 输出到 Fragment Shader ──────────────────────────────────
out vec2  vQuadUV;          // 四边形局部坐标 [-0.5, 0.5]
out vec4  vColor;           // 传递颜色
out float vGlowIntensity;   // 传递发光强度
out float vSelected;        // 传递选中状态
out float vDepth;           // 视空间深度 (用于雾效/LOD)

void main() {
    // ── Billboard 偏移 ──────────────────────────────────────
    // 每个特征点的世界位置 aOffset 作为中心，
    // 用相机的 right/up 向量构建朝向相机的四边形

    // 动态大小：基础大小 × 发光脉冲 × 全局缩放 × 像素比
    float size = aSize * uPointSizeScale * uPixelRatio;

    // 异常样本脉冲动画：sin 波动 3Hz
    if (aGlowIntensity > 0.0) {
        size *= 1.0 + 0.35 * sin(uTime * 6.2832 * 3.0 + aOffset.x * 10.0);
        // 叠加额外发光膨胀
        size *= 1.0 + aGlowIntensity * 0.4;
    }

    // 选中状态放大
    if (aSelected > 0.5) {
        size *= 1.4;
    }

    // Billboard 顶点世界坐标
    vec3 worldPos = aOffset
                  + uCameraRight * aQuadVertex.x * size
                  + uCameraUp    * aQuadVertex.y * size;

    // ── 投影 ────────────────────────────────────────────────
    vec4 viewPos = uViewProjection * vec4(worldPos, 1.0);
    gl_Position  = viewPos;

    // ── 传递 varying ────────────────────────────────────────
    vQuadUV        = aQuadVertex;  // [-0.5, 0.5] 用于圆形成像
    vColor         = aColor;
    vGlowIntensity = aGlowIntensity;
    vSelected      = aSelected;
    vDepth         = viewPos.z / viewPos.w;  // 归一化深度
}
