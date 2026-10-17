shader_type spatial;
render_mode cull_disabled;
uniform vec3 deep_color : source_color = vec3(0.075,0.23,0.26);
uniform vec3 light_color : source_color = vec3(0.20,0.39,0.36);
varying vec3 world_position;
void vertex() {
 world_position = (MODEL_MATRIX * vec4(VERTEX,1.0)).xyz;
 float p=world_position.x*0.65+world_position.z*0.28+TIME*0.45;
 float q=world_position.z*0.94-world_position.x*0.34-TIME*0.38;
 VERTEX.y += sin(p)*0.045+sin(q)*0.027;
 NORMAL=normalize(vec3(-cos(p)*0.02925+cos(q)*0.00918,1.0,-cos(p)*0.0126-cos(q)*0.02538));
}
void fragment() {
 float a=atan(world_position.z/16.5,world_position.x/12.0);
 float coastline=1.0+0.075*sin(a*3.0+0.6)+0.055*sin(a*7.0)+0.025*cos(a*11.0);
 float radius=length(vec2(world_position.x/12.0,world_position.z/16.5))/coastline;
 float shallows=1.0-smoothstep(1.0,1.18,radius);
 ALBEDO=mix(deep_color,light_color,shallows*.58);
 ROUGHNESS=0.23;
 SPECULAR=0.55;
 METALLIC=0.22;
}
