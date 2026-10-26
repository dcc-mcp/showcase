shader_type spatial;

uniform vec4 deep_color : source_color = vec4(0.026, 0.083, 0.098, 1.0);
uniform vec4 ripple_color : source_color = vec4(0.12, 0.27, 0.29, 1.0);
uniform float water_roughness : hint_range(0.05, 0.6) = 0.18;
uniform float wave_height : hint_range(0.0, 0.08) = 0.055;

varying vec2 water_position;

void vertex() {
	water_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz;
	vec2 direction_a = vec2(0.35, 0.77);
	vec2 direction_b = vec2(-0.83, 0.24);
	float phase_a = dot(water_position, direction_a) * 0.4 + TIME * 1.04719755;
	float phase_b = dot(water_position, direction_b) * 0.7 - TIME * 1.57079633;
	VERTEX.y += wave_height * (sin(phase_a) + 0.35 * sin(phase_b));
	vec2 gradient = wave_height * (0.4 * direction_a * cos(phase_a) + 0.245 * direction_b * cos(phase_b));
	NORMAL = normalize(vec3(-gradient.x, 1.0, -gradient.y));
}

void fragment() {
	float facing = clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0);
	float fresnel = pow(1.0 - facing, 5.0);
	float ripples = 0.5 + 0.5 * sin(dot(water_position, vec2(1.3, 1.7)) + TIME * 1.04719755);
	ALBEDO = mix(deep_color.rgb, ripple_color.rgb, clamp(0.08 + fresnel * 0.5 + ripples * 0.06, 0.0, 1.0));
	ROUGHNESS = water_roughness;
	METALLIC = 0.0;
	SPECULAR = 0.55;
}
