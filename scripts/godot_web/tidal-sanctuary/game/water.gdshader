shader_type spatial;
render_mode cull_disabled;
varying vec3 world_position;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float smooth_noise(vec2 p){
 vec2 i=floor(p);vec2 f=fract(p);f=f*f*(3.0-2.0*f);
 return mix(mix(hash(i),hash(i+vec2(1.0,0.0)),f.x),mix(hash(i+vec2(0.0,1.0)),hash(i+vec2(1.0,1.0)),f.x),f.y);
}
void vertex(){
 world_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
 vec2 p=world_position.xz*0.12+vec2(TIME*0.011,-TIME*0.008);
 float center=smooth_noise(p);
 VERTEX.y+=(center-0.5)*0.035;
 NORMAL=normalize(vec3((center-smooth_noise(p+vec2(0.07,0.0)))*0.06,1.0,(center-smooth_noise(p+vec2(0.0,0.07)))*0.06));
}
void fragment(){
 float a=atan(world_position.z/16.5,world_position.x/12.0);
 float coast=1.0+0.075*sin(a*3.0+0.6)+0.055*sin(a*7.0)+0.025*cos(a*11.0);
 float radius=length(vec2(world_position.x/12.0,world_position.z/16.5))/coast;
 float shallows=1.0-smoothstep(1.0,1.18,radius);
 ALBEDO=mix(vec3(0.034,0.115,0.135),vec3(0.075,0.17,0.15),shallows*0.48);
 ROUGHNESS=0.36;SPECULAR=0.40;METALLIC=0.08;
}
