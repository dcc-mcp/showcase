shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;
uniform sampler2D grain_texture : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D rough_texture : filter_linear_mipmap, repeat_enable;
uniform vec3 stone_tint=vec3(1.0);
uniform bool terrain_surface=false;
varying vec3 surface_position;
varying vec3 surface_normal;
void vertex(){
 surface_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
 surface_normal=normalize(MODEL_NORMAL_MATRIX*NORMAL);
}
void fragment(){
 vec3 n=normalize(surface_normal);
 vec3 weights=pow(abs(n),vec3(4.0));weights/=max(dot(weights,vec3(1.0)),0.001);
 vec3 p=surface_position*0.66;
 vec3 grain=texture(grain_texture,p.zy).rgb*weights.x+texture(grain_texture,p.xz).rgb*weights.y+texture(grain_texture,p.xy).rgb*weights.z;
 float value=dot(grain,vec3(0.2126,0.7152,0.0722));
 if(terrain_surface){
  // One quiet mineral grain unifies soil, moss and stone; vertex colors retain broad patches.
  vec3 base=pow(max(COLOR.rgb,vec3(0.0)),vec3(2.2));
  ALBEDO=base*(0.84+smoothstep(0.04,0.38,value)*0.28);
  ROUGHNESS=0.98;
 }else{
  // Restrained cool limestone replaces the high-contrast brown photographic wash.
  float relief=clamp((value-0.16)*0.29,-0.028,0.048);
  vec3 mineral=(vec3(0.235,0.255,0.245)+relief)*stone_tint;
  float foot=(1.0-smoothstep(4.02,4.35,surface_position.y))*(0.25+value);
  ALBEDO=mix(mineral,vec3(0.12,0.185,0.13),clamp(foot*0.40,0.0,0.22));
  vec3 signs=sign(n);
  vec3 nx=texture(normal_texture,p.zy).xyz*2.0-1.0;
  vec3 ny=texture(normal_texture,p.xz).xyz*2.0-1.0;
  vec3 nz=texture(normal_texture,p.xy).xyz*2.0-1.0;
  vec3 detail=vec3(nx.z*signs.x,nx.y,nx.x)*weights.x+vec3(ny.x,ny.z*signs.y,ny.y)*weights.y+vec3(nz.x,nz.y,nz.z*signs.z)*weights.z;
  NORMAL=normalize((VIEW_MATRIX*vec4(normalize(mix(n,detail,0.13)),0.0)).xyz);
  ROUGHNESS=clamp(texture(rough_texture,p.xz).r,0.86,1.0);
 }
 SPECULAR=0.20;
}
