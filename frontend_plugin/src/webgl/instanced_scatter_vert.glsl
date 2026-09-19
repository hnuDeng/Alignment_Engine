#version 300 es
/**
 * @file instanced_scatter_vert.glsl
 * @brief Instanced rendering vertex shader for 1M+ point scatter plots.
 *
 * Renders each point as a camera-facing billboard (quad) using gl_InstanceID
 * to index into per-instance attribute buffers. Supports:
 *   - Per-instance position (vec3) from a_position
 *   - Per-instance color (vec3) from a_color
 *   - Per-instance size (float) from a_size
 *   - Per-instance selection state (float) from a_selected
 *   - Global time uniform for pulse/glow animation
 *   - View-projection matrix for camera transform
 */

// Per-vertex attributes for the billboard quad (4 vertices per instance)
// a_quad_pos encodes the 4 corners of a unit quad: (-1,-1), (1,-1), (1,1), (-1,1)
in vec2 a_quad_pos;

// Per-instance attributes (divisor = 1)
in vec3 a_instance_pos;       // World-space position (x, y, z)
in vec3 a_instance_color;     // RGB color (0..1)
in float a_instance_size;     // Point radius in world units
in float a_instance_selected; // 0.0 = normal, 1.0 = selected

// Uniforms
uniform mat4 u_view_projection; // Combined view-projection matrix
uniform float u_time;           // Elapsed time in seconds (for animation)
uniform float u_point_scale;    // Global scale factor (default 1.0)
uniform float u_pixel_ratio;    // window.devicePixelRatio

// Outputs to fragment shader
out vec3 v_color;
out vec2 v_uv;            // Local UV within the billboard (-1..1)
out float v_selected;
out float v_glow_intensity;

void main() {
    // Billboard size: instance_size * global_scale * device_pixel_ratio
    float base_size = a_instance_size * u_point_scale * u_pixel_ratio;

    // Pulse animation for selected points
    float pulse = 1.0;
    if (a_instance_selected > 0.5) {
        // Sinusoidal pulse: oscillates between 1.0x and 1.3x size
        pulse = 1.0 + 0.15 * sin(u_time * 4.0);
    }

    float final_size = base_size * pulse;

    // Billboard offset: scale the unit quad by final_size
    vec3 billboard_offset = vec3(a_quad_pos * final_size, 0.0);

    // View-space billboard: always face the camera
    // We extract the camera right and up vectors from the view-projection matrix
    vec3 camera_right = vec3(u_view_projection[0][0], u_view_projection[1][0], u_view_projection[2][0]);
    vec3 camera_up    = vec3(u_view_projection[0][1], u_view_projection[1][1], u_view_projection[2][1]);

    // Normalize to remove projection scaling
    camera_right = normalize(camera_right);
    camera_up    = normalize(camera_up);

    // Final world-space position: instance position + billboard offset
    vec3 world_pos = a_instance_pos
                   + camera_right * a_quad_pos.x * final_size
                   + camera_up    * a_quad_pos.y * final_size;

    gl_Position = u_view_projection * vec4(world_pos, 1.0);

    // Pass to fragment
    v_color = a_instance_color;
    v_uv = a_quad_pos; // -1..1 range
    v_selected = a_instance_selected;

    // Glow intensity: selected points glow more, with time-based animation
    v_glow_intensity = a_instance_selected > 0.5
        ? 0.6 + 0.4 * sin(u_time * 3.0)
        : 0.0;
}
