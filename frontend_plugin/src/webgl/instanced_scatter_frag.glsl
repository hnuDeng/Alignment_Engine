#version 300 es
/**
 * @file instanced_scatter_frag.glsl
 * @brief Fragment shader for instanced scatter plot with SDF + glow.
 *
 * Renders each billboard as a smooth circle using Signed Distance Field (SDF),
 * with optional glow effect for selected/hovered points and depth-based fog.
 */

precision highp float;

// Inputs from vertex shader
in vec3 v_color;
in vec2 v_uv;            // Local UV within billboard (-1..1)
in float v_selected;
in float v_glow_intensity;

// Uniforms
uniform float u_time;
uniform float u_opacity;        // Global opacity (default 1.0)
uniform float u_hovered_id;     // ID of currently hovered point (-1 = none)
uniform float u_current_id;     // ID of this instance

// Output
out vec4 frag_color;

/**
 * Signed Distance Field for a circle.
 * Returns negative values inside the circle, positive outside.
 *
 * @param uv       Point coordinates in [-1, 1]
 * @param radius   Circle radius in UV space
 */
float sdf_circle(vec2 uv, float radius) {
    return length(uv) - radius;
}

/**
 * Smooth step with anti-aliasing.
 * Uses screen-space derivatives for resolution-independent smoothing.
 */
float aastep(float threshold, float value) {
    float afwidth = length(vec2(dFdx(value), dFdy(value))) * 0.7;
    return smoothstep(threshold - afwidth, threshold + afwidth, value);
}

void main() {
    // Distance from center of billboard
    float dist = length(v_uv);

    // SDF circle: render as a disc with soft edge
    // radius = 0.85 leaves a small anti-aliasing border
    float circle_sdf = sdf_circle(v_uv, 0.85);

    // Anti-aliased alpha: hard edge with smooth falloff
    float alpha = 1.0 - aastep(0.0, circle_sdf);

    // Discard fully transparent fragments early
    if (alpha < 0.01) discard;

    // Base color
    vec3 color = v_color;

    // Hovered point: add bright ring highlight
    if (u_hovered_id >= 0.0 && abs(u_current_id - u_hovered_id) < 0.5) {
        // Ring effect: bright at the edge, darker in center
        float ring = smoothstep(0.6, 0.85, dist) * smoothstep(1.0, 0.85, dist);
        color = mix(color, vec3(1.0, 1.0, 1.0), ring * 0.8);

        // Inner glow for hovered
        float inner_glow = 1.0 - smoothstep(0.0, 0.5, dist);
        color += inner_glow * 0.15;
    }

    // Selected point: outer glow
    if (v_glow_intensity > 0.0) {
        // Glow extends beyond the disc edge
        float glow_falloff = exp(-dist * dist * 3.0);
        vec3 glow_color = v_color * 1.5; // Brighter version of the point color
        color = mix(color, glow_color, glow_falloff * v_glow_intensity * 0.5);

        // Add a bright rim
        float rim = smoothstep(0.7, 0.9, dist) * (1.0 - smoothstep(0.9, 1.1, dist));
        color += rim * v_glow_intensity * 0.3;
    }

    // Depth-based fog: points further from center fade slightly
    float depth_fog = 1.0 - smoothstep(0.0, 0.3, dist) * 0.05;
    color *= depth_fog;

    // Final output
    frag_color = vec4(color, alpha * u_opacity);
}
