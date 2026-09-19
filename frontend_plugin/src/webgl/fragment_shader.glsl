#version 300 es
precision highp float;

in vec3 v_color;
in vec2 v_uv;

out vec4 fragColor;

void main() {
    // Calculate SDF (Signed Distance Field) for a circle
    float dist = length(v_uv);
    
    // Anti-aliased circle edge
    float alpha = 1.0 - smoothstep(0.45, 0.5, dist);
    
    if (alpha < 0.01) {
        discard;
    }
    
    // Glow effect
    vec3 glow = v_color * 1.5 * (1.0 - dist);
    
    fragColor = vec4(glow, alpha);
}
