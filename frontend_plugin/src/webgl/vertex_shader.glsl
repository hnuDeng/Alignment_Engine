#version 300 es
precision highp float;

// Instance attributes
layout(location = 0) in vec3 a_instancePosition;
layout(location = 1) in vec3 a_instanceColor;

// Quad attributes
layout(location = 2) in vec2 a_quadPosition;

uniform mat4 u_viewProjectionMatrix;
uniform float u_pointSize;

out vec3 v_color;
out vec2 v_uv;

void main() {
    v_color = a_instanceColor;
    v_uv = a_quadPosition;
    
    // Billboard logic: quad always faces camera
    vec4 worldPos = vec4(a_instancePosition, 1.0);
    vec4 viewPos = u_viewProjectionMatrix * worldPos;
    
    // Displace by quad vertices scaled by point size
    viewPos.xy += a_quadPosition * u_pointSize;
    
    gl_Position = viewPos;
}
