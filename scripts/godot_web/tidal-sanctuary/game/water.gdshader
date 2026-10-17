shader_type spatial;
render_mode unshaded, cull_disabled;
uniform vec3 deep_color : source_color = vec3(0.055,0.27,0.31);
uniform vec3 light_color : source_color = vec3(0.14,0.46,0.44);
varying vec3 world_position;
void vertex() {
 world_position = (MODEL_MATRIX * vec4(VERTEX,1.0)).xyz;
 VERTEX.y += sin(world_position.x*0.45+TIME*0.55)*0.05 + sin(world_position.z*0.8+TIME*0.8)*0.04;
}
void fragment() {
 float wave = sin(world_position.x*0.4 + world_position.z*0.23 + TIME*0.45)*0.5+0.5;
 float broad = sin(world_position.z*0.19-world_position.x*0.15+TIME*0.21)*0.5+0.5;
 float a = atan(world_position.z/16.5,world_position.x/12.0);
 float coastline = 1.0+0.075*sin(a*3.0+0.6)+0.055*sin(a*7.0)+0.025*cos(a*11.0);
 float radius = length(vec2(world_position.x/12.0,world_position.z/16.5))/coastline;
 float shallows = 1.0-smoothstep(1.0,1.22,radius);
 ALBEDO = mix(deep_color,light_color,wave*0.14+broad*0.10+shallows*0.52);
 ROUGHNESS=0.85;
 SPECULAR=0.0;
}
