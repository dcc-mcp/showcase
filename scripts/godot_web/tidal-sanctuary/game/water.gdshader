shader_type spatial;
render_mode cull_disabled;
uniform vec3 deep_color : source_color = vec3(0.075,0.40,0.48);
uniform vec3 light_color : source_color = vec3(0.17,0.69,0.68);
varying vec3 world_position;
void vertex() {
 world_position = (MODEL_MATRIX * vec4(VERTEX,1.0)).xyz;
 VERTEX.y += sin(world_position.x*0.45+TIME*0.55)*0.05 + sin(world_position.z*0.8+TIME*0.8)*0.04;
}
void fragment() {
 float wave = sin(world_position.x*0.4 + world_position.z*0.23 + TIME*0.45)*0.5+0.5;
 float ripple = sin(world_position.x*3.2 + world_position.z*2.6 + sin(world_position.z*0.6)+TIME*0.7);
 float glint = pow(max(ripple,0.0),22.0)*0.1;
 ALBEDO = mix(deep_color,light_color,wave*0.35) + glint;
 ROUGHNESS=0.32;
 SPECULAR=0.45;
}
