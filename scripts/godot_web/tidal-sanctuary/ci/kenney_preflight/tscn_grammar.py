"""Narrow allowlist for this converter's serialized output, not a Godot parser.
Unknown valid Godot syntax is deliberately rejected, never interpreted.
"""
import json
import math
import re
TOKEN=re.compile(r'\s*(?:("(?:[^"\\\x00-\x1f]|\\["\\/bfnrt]|\\u[0-9A-Fa-f]{4})*")|(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)|([A-Za-z_][A-Za-z_0-9]*)|([\[\]{},():]))')
ARITIES={'Color':4,'Transform3D':12,'AABB':6,'Vector4':4}

def value(text):
    tokens=[];position=0
    while position<len(text):
        if text[position:].isspace():break
        m=TOKEN.match(text,position)
        if not m:raise ValueError('Unsupported value syntax')
        tokens.append(next(x for x in m.groups() if x is not None));position=m.end()
    index=0
    def parse():
        nonlocal index
        if index>=len(tokens):raise ValueError('Truncated value')
        t=tokens[index];index+=1
        if t.startswith('"'):return json.loads(t)
        if t[0].isdigit() or t.startswith('-'):
            n=float(t) if any(c in t for c in '.eE') else int(t)
            if not math.isfinite(n):raise ValueError('Non-finite number')
            return n
        if t in ('[','{'):
            end=']' if t=='[' else '}';out=[] if t=='[' else {}
            while index<len(tokens) and tokens[index]!=end:
                item=parse()
                if t=='{':
                    if not isinstance(item,str) or index>=len(tokens) or tokens[index]!=':' or item in out:raise ValueError('Invalid dictionary')
                    index+=1;out[item]=parse()
                else:out.append(item)
                if index<len(tokens) and tokens[index]==',':index+=1
                elif index<len(tokens) and tokens[index]!=end:raise ValueError('Missing comma')
            if index>=len(tokens):raise ValueError('Unclosed collection')
            index+=1;return out
        if t not in {*ARITIES,'PackedByteArray','SubResource'} or index>=len(tokens) or tokens[index]!='(':
            raise ValueError('Unsupported constructor/identifier')
        index+=1;args=[]
        while index<len(tokens) and tokens[index]!=')':
            args.append(parse())
            if index<len(tokens) and tokens[index]==',':index+=1
            elif index<len(tokens) and tokens[index]!=')':raise ValueError('Missing constructor comma')
        if index>=len(tokens):raise ValueError('Unclosed constructor')
        index+=1
        if t in ARITIES and (len(args)!=ARITIES[t] or any(type(n) not in (int,float) for n in args)):raise ValueError('Invalid numeric constructor')
        if t=='SubResource' and (len(args)!=1 or not isinstance(args[0],str) or not re.fullmatch('[A-Za-z0-9_]+',args[0])):raise ValueError('Invalid resource reference')
        if t=='PackedByteArray' and not (len(args)==1 and isinstance(args[0],str) and re.fullmatch('[A-Za-z0-9+/]*={0,2}',args[0])):raise ValueError('Unsupported packed array')
        return (t,args)
    result=parse()
    if index!=len(tokens):raise ValueError('Trailing value expression')
    return result

def isctor(v,name):return isinstance(v,tuple) and v[0]==name

def audit_bodies(text):
    sections=list(re.finditer(r'^\[([^\n]+)\]\s*$',text,re.M))
    for i,section in enumerate(sections):
        header=section[1];body=text[section.end():sections[i+1].start() if i+1<len(sections) else len(text)]
        fields=list(re.finditer(r'^([A-Za-z_][A-Za-z_0-9/]*) = ',body,re.M));seen=set()
        if (body[:fields[0].start()] if fields else body).strip():raise ValueError('Unexpected section body')
        for j,field in enumerate(fields):
            key=field[1]
            if key in seen:raise ValueError('Duplicate property')
            seen.add(key);v=value(body[field.end():fields[j+1].start() if j+1<len(fields) else len(body)].strip())
            if header.startswith('node '):
                allowed=key=='transform' and isctor(v,'Transform3D')
                if 'type="MeshInstance3D"' in header:allowed |= (key=='mesh' or re.fullmatch(r'surface_material_override/[0-2]',key) is not None) and isctor(v,'SubResource')
            elif 'type="StandardMaterial3D"' in header:
                allowed=(key=='resource_name' and isinstance(v,str)) or (key=='albedo_color' and isctor(v,'Color')) or (key in ('metallic','roughness') and type(v) in (int,float) and 0<=v<=1)
            elif 'type="ArrayMesh"' in header:
                allowed=(key=='resource_name' and isinstance(v,str)) or (key=='blend_shape_mode' and type(v) is int and v in (0,1))
                if key=='_surfaces':
                    allowed=isinstance(v,list) and 1<=len(v)<=3
                    for surface in v if allowed else []:
                        if not isinstance(surface,dict):allowed=False;break
                        for k,item in surface.items():
                            ok=(k in ('format','index_count','primitive','vertex_count') and type(item) is int and item>=0) or (k=='name' and isinstance(item,str)) or (k in ('attribute_data','index_data','vertex_data','skin_data') and isctor(item,'PackedByteArray')) or (k=='aabb' and isctor(item,'AABB')) or (k=='uv_scale' and isctor(item,'Vector4')) or (k=='material' and isctor(item,'SubResource'))
                            if not ok:allowed=False
            else:allowed=False
            if not allowed:raise ValueError('Unsupported property/value: '+key)
