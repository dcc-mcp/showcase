shader_type spatial;
render_mode cull_disabled;
uniform vec3 deep_color : source_color = vec3(0.15,0.38,0.42);
uniform vec3 shallow_color : source_color = vec3(0.38,0.67,0.63);
varying vec3 world_position;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise2(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
float cached_noise2(vec2 p,vec2 origin,mat3 lattice){
 ivec2 cell=ivec2(floor(p)-origin);
 vec2 f=fract(p);f=f*f*(3.0-2.0*f);
 return mix(mix(lattice[cell.x][cell.y],lattice[cell.x+1][cell.y],f.x),mix(lattice[cell.x][cell.y+1],lattice[cell.x+1][cell.y+1],f.x),f.y);
}
void noise_stencil(vec2 p,float scale,vec2 drift,out vec3 center_x,out vec2 z){
 // Preserve the original coordinate arithmetic: offset before scaling.
 vec2 center=p*scale+drift;
 vec2 positive_x=(p+vec2(.15,0))*scale+drift;
 vec2 negative_x=(p-vec2(.15,0))*scale+drift;
 vec2 positive_z=(p+vec2(0,.15))*scale+drift;
 vec2 negative_z=(p-vec2(0,.15))*scale+drift;
 // Each axis spans at most 2*.15*2.3=.69 lattice units. Its cells
 // therefore differ by at most one, needing only these 3x3 corners.
 // This reuses hashes, not noise values: all five interpolations remain.
 vec2 origin=floor(min(min(min(center,positive_x),negative_x),min(positive_z,negative_z)));
 mat3 lattice=mat3(
  vec3(hash(origin),hash(origin+vec2(0,1)),hash(origin+vec2(0,2))),
  vec3(hash(origin+vec2(1,0)),hash(origin+vec2(1,1)),hash(origin+vec2(1,2))),
  vec3(hash(origin+vec2(2,0)),hash(origin+vec2(2,1)),hash(origin+vec2(2,2))));
 center_x=vec3(cached_noise2(center,origin,lattice),cached_noise2(positive_x,origin,lattice),cached_noise2(negative_x,origin,lattice));
 z=vec2(cached_noise2(positive_z,origin,lattice),cached_noise2(negative_z,origin,lattice));
}
float ground_height(vec2 p){
 float a=atan(p.y/16.5,p.x/12.0);
 float coastline=1.0+.075*sin(a*3.0+.6)+.055*sin(a*7.0)+.025*cos(a*11.0);
 float r=length(p/vec2(12.0,16.5))/coastline;
 float north=1.0-smoothstep(-10.0,7.0,p.y);
 float base=1.45+3.25*north;
 vec2 shoulder_p=(p+vec2(5.0,1.5))/vec2(3.2,6.5);
 float shoulder=.65*exp(-dot(shoulder_p,shoulder_p));
 float plateau=(1.0-smoothstep(-7.0,-4.5,p.y))*(1.0-smoothstep(4.2,6.0,abs(p.x)));
 float land=mix(base+shoulder,4.55,plateau);
 vec2 cove_p=(p-vec2(8.0,5.0))/vec2(5.1,4.5);
 float cove=2.9*exp(-dot(cove_p,cove_p));
 return -.60+(1.0-smoothstep(.83,1.04,r))*land-2.7*smoothstep(.98,1.36,r)-cove;
}
void vertex(){
 world_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
 vec3 low_center_x,high_center_x;
 vec2 low_z,high_z;
 noise_stencil(world_position.xz,.95,vec2(TIME*.15,TIME*.06),low_center_x,low_z);
 noise_stencil(world_position.xz,2.3,vec2(-TIME*.07,TIME*.11),high_center_x,high_z);
 vec3 center_x=(low_center_x-vec3(.5))*.045+(high_center_x-vec3(.5))*.016;
 vec2 z=(low_z-vec2(.5))*.045+(high_z-vec2(.5))*.016;
 VERTEX.y+=center_x.x;
 float dx=(center_x.y-center_x.z)/.3;
 float dz=(z.x-z.y)/.3;
 NORMAL=normalize(vec3(-dx,1.0,-dz));
}
void fragment(){
 vec2 p=world_position.xz;
 vec2 island_p=p/vec2(12.0,16.5);
 // coastline <= 1.155, so radius >= 1.36*1.155 gives depth >= 3.15.
 // 2.468 conservatively exceeds that radius squared (2.46741264).
 // Both color-depth ramps are saturated there; no height approximation
 // is made near shore, and fragment alpha/lighting remain unchanged.
 float depth=3.15;
 if(dot(island_p,island_p)<2.468){
  depth=max(0.0,-.15-ground_height(p));
 }
 float shallows=1.0-smoothstep(.2,3.0,depth);
 vec3 water=mix(deep_color,shallow_color,shallows*.8);
 float swash=0.0;
 // Noise has no contribution once the swash depth factor reaches zero.
 if(depth<.18){
  float fleck=noise2(p*1.5+vec2(TIME*.07,0));
  swash=(1.0-smoothstep(.02,.18,depth))*smoothstep(.50,.72,fleck)*.23;
 }
 ALBEDO=mix(water,vec3(.68,.82,.75),swash);
 ROUGHNESS=.30;SPECULAR=.48;METALLIC=0.0;
 ALPHA=mix(.94,.66,shallows);
}
