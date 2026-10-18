shader_type spatial;
render_mode diffuse_burley;
uniform vec4 shadow_tint : source_color = vec4(.075,.18,.17,1.0);
uniform vec4 sun_tint : source_color = vec4(.14,.30,.24,1.0);
varying vec3 world_pos;
void vertex(){world_pos=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;}
void fragment(){
 float patch = .5+.22*sin(world_pos.x*.43+sin(world_pos.z*.61))+.18*cos(world_pos.z*.72+world_pos.x*.19);
 float grain=.018*sin(world_pos.x*17.7)*sin(world_pos.z*20.2);
 ALBEDO=mix(shadow_tint.rgb,sun_tint.rgb,clamp(patch+grain,0.0,1.0));
 ROUGHNESS=.95;
}
