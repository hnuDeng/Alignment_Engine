/**
 * fragment_shader.glsl —— 特征点发光与颜色映射片元着色器
 *
 * 设计要点：
 *  1. 圆形 SDF 成像：利用 quadUV 的距离场实现抗锯齿圆形点
 *  2. 多层发光：核心高亮 + 外层光晕 + 脉冲呼吸动画
 *  3. 选中状态：绿色边缘描边
 *  4. 深度雾效：远处点逐渐淡出，增强层次感
 *  5. 输出 alpha 用于透明混合 (GL_BLEND)
 */

#version 300 es
precision highp float;

// ── 从 Vertex Shader 接收 ───────────────────────────────────
in vec2  vQuadUV;          // [-0.5, 0.5]
in vec4  vColor;           // RGBA
in float vGlowIntensity;   // 发光强度
in float vSelected;        // 选中状态
in float vDepth;           // 归一化深度

// ── Uniform ─────────────────────────────────────────────────
uniform float uTime;
uniform float uFogDensity;      // 雾效密度 (0 = 无雾)
uniform vec3  uFogColor;        // 雾效颜色 (通常与背景一致)
uniform float uGlowFalloff;     // 发光衰减指数 (默认 2.0)

// ── 输出 ────────────────────────────────────────────────────
out vec4 fragColor;

// ── 常量 ─────────────────────────────────────────────────────
const float CORE_RADIUS   = 0.32;   // 核心实心圆半径
const float GLOW_RADIUS   = 0.50;   // 发光外边界
const float EDGE_SOFTNESS = 0.04;   // 边缘抗锯齿过渡宽度

void main() {
    // ── 圆形 SDF ────────────────────────────────────────────
    float dist = length(vQuadUV);  // 到中心的距离 (0 ~ 0.707)

    // 超出最大半径则丢弃
    if (dist > GLOW_RADIUS + EDGE_SOFTNESS) discard;

    // ── 基础颜色 ────────────────────────────────────────────
    vec3 baseColor = vColor.rgb;
    float alpha    = vColor.a;

    // ── 核心区域（实心圆）───────────────────────────────────
    // smoothstep 实现抗锯齿边缘
    float coreAlpha = 1.0 - smoothstep(CORE_RADIUS - EDGE_SOFTNESS,
                                        CORE_RADIUS + EDGE_SOFTNESS,
                                        dist);

    // ── 发光层 ──────────────────────────────────────────────
    // 从核心边缘到发光边界的辉光衰减
    float glowMask = 0.0;
    if (vGlowIntensity > 0.0) {
        // 辉光从核心边缘向外指数衰减
        float glowDist = max(0.0, dist - CORE_RADIUS) / (GLOW_RADIUS - CORE_RADIUS);
        glowMask = vGlowIntensity * pow(1.0 - glowDist, uGlowFalloff);

        // 脉冲呼吸动画（与 vertex shader 的频率匹配）
        float pulse = 0.6 + 0.4 * sin(uTime * 6.2832 * 3.0);
        glowMask *= pulse;

        // 发光颜色：向白色偏移
        vec3 glowColor = mix(baseColor, vec3(1.0), 0.5);
        baseColor = mix(baseColor, glowColor, glowMask * 0.6);
    }

    // ── 选中状态：绿色描边 ──────────────────────────────────
    if (vSelected > 0.5) {
        // 在圆环区域绘制绿色边缘
        float ringDist = abs(dist - CORE_RADIUS);
        float ringMask = 1.0 - smoothstep(0.0, EDGE_SOFTNESS * 2.0, ringDist);
        baseColor = mix(baseColor, vec3(0.0, 1.0, 0.5), ringMask * 0.8);
        // 外围绿色光晕
        float selGlow = (1.0 - smoothstep(CORE_RADIUS, GLOW_RADIUS, dist)) * 0.3;
        baseColor += vec3(0.0, 0.4, 0.2) * selGlow;
    }

    // ── 合成 alpha ──────────────────────────────────────────
    // 核心实心 + 外层发光半透明
    float finalAlpha = max(coreAlpha, glowMask * 0.5) * alpha;

    // ── 深度雾效 ────────────────────────────────────────────
    if (uFogDensity > 0.0) {
        float fogFactor = exp(-uFogDensity * abs(vDepth));
        fogFactor = clamp(fogFactor, 0.0, 1.0);
        baseColor  = mix(uFogColor, baseColor, fogFactor);
        finalAlpha *= fogFactor;
    }

    // ── 输出 ────────────────────────────────────────────────
    fragColor = vec4(baseColor, finalAlpha);
}
