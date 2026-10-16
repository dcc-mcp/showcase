'use strict';
(() => {
 const $=id=>document.getElementById(id), cfg=JSON.parse($('game-config').textContent);
 const query=new URLSearchParams(location.search),lang=query.get('lang')==='zh'?'zh':'en';
 const embedded=query.get('embed')==='1',mobile=matchMedia('(max-width:700px), (pointer:coarse)').matches;
 const t=lang==='zh'?{start:'开始游戏',retry:'重试',loading:'正在加载花园…',running:'轻触方块或使用方向键与空格操作。',ready:'点击开始后才会下载共享游戏引擎。',error:'加载失败。请检查网络与 WebGL 2 支持，然后重试。',exit:'退出',cancel:'取消加载',full:'全屏',reset:'重新开始',toggle:'暂停 / 继续',mute:'静音',sound:'开启声音',save:'本地保存',load:'读取存档',undo:'撤销',next:'下一关',alternate:'备用操作',saved:'已保存到本机',loaded:'已读取存档',save_failed:'保存失败，浏览器存储不可用',no_save:'尚无本地存档',invalid_save:'存档不可用',note:'原创 Godot 游戏 · 无广告 · 无账号 · 存档仅保留在此浏览器'}:{start:'Start game',retry:'Retry',loading:'Growing your garden…',running:'Tap a tile, or use arrows and Space.',ready:'The shared game engine loads only when you start.',error:'Could not load. Check your connection and WebGL 2 support, then retry.',exit:'Exit',cancel:'Cancel loading',full:'Fullscreen',reset:'Restart',toggle:'Pause / resume',mute:'Mute',sound:'Sound on',save:'Save locally',load:'Load save',undo:'Undo',next:'Next garden',alternate:'Alternative controls',saved:'Saved in this browser',loaded:'Save restored',save_failed:'Save failed: browser storage unavailable',no_save:'No local save yet',invalid_save:'Save unavailable',note:'Original Godot game · No ads · No account · Saves stay in this browser'};
 document.documentElement.lang=lang;document.body.dataset.embed=String(embedded);document.body.dataset.layout=mobile?'mobile':'desktop';
 $('title').textContent=cfg.title[lang];$('status').textContent=t.ready;$('start').textContent=t.start;$('exit').textContent=t.exit;$('cancel').textContent=t.cancel;$('fullscreen').textContent=t.full;$('alternate-label').textContent=t.alternate;$('note').textContent=t.note;$('instructions').textContent=cfg.instructions[lang];
 let audioAllowed=!embedded;const contexts=new Set();const NativeAudio=window.AudioContext||window.webkitAudioContext;
 if(NativeAudio){const ProxyAudio=new Proxy(NativeAudio,{construct(target,args){const c=new target(...args);contexts.add(c);return c;}});if(window.AudioContext)window.AudioContext=ProxyAudio;else window.webkitAudioContext=ProxyAudio;}
 // Embedded games have a hard output gate: engine-driven context.resume cannot bypass mute.
 const outputGates=new Set(),destinationGates=new WeakMap(),nativeConnect=AudioNode.prototype.connect;
 AudioNode.prototype.connect=function(destination,...args){
  if(destination instanceof AudioDestinationNode){
   let gate=destinationGates.get(destination);
   if(!gate){gate=this.context.createGain();gate.gain.value=audioAllowed?1:0;destinationGates.set(destination,gate);outputGates.add(gate);nativeConnect.call(gate,destination);}
   return nativeConnect.call(this,gate,...args);
  }
  return nativeConnect.call(this,destination,...args);
 };
 const notify=(state)=>{if(parent!==window)parent.postMessage(state,location.origin);};
 let engine=null,busy=false,running=false,muted=embedded,timer=null,loader=null,firstNative=true;
 function command(value){if(typeof window.showcaseCommand==='function')window.showcaseCommand(value);}
 async function sound(value){audioAllowed=value;muted=!value;for(const gate of outputGates)gate.gain.value=value?1:0;command(value?'sound-on':'sound-off');for(const c of contexts){try{if(value)await c.resume();else await c.suspend();}catch(_){}}notify({type:'showcase:state',state:running?'running':'ready',audio:!muted});}
 const touch=$('canvas');
 // Let completed touch taps enter the real canvas. Vertical drags scroll the page.
 let touchStart=null;
 touch.addEventListener('touchstart',e=>{if(!mobile)return;e.stopImmediatePropagation();touchStart=e.touches.length===1?{x:e.touches[0].clientX,y:e.touches[0].clientY,moved:false}:null;},{capture:true,passive:true});
 touch.addEventListener('touchmove',e=>{if(!mobile)return;e.stopImmediatePropagation();if(touchStart&&e.touches.length===1&&Math.hypot(e.touches[0].clientX-touchStart.x,e.touches[0].clientY-touchStart.y)>8)touchStart.moved=true;},{capture:true,passive:true});
 touch.addEventListener('touchend',e=>{if(!mobile)return;e.stopImmediatePropagation();if(e.cancelable)e.preventDefault();const p=touchStart;touchStart=null;if(!p||p.moved||e.touches.length)return;touch.focus({preventScroll:true});for(const type of ['mousedown','mouseup'])touch.dispatchEvent(new MouseEvent(type,{bubbles:true,clientX:p.x,clientY:p.y,button:0,buttons:type==='mousedown'?1:0}));},{capture:true,passive:false});
 touch.addEventListener('pointerdown',()=>{if(!muted)for(const c of contexts)if(c.state==='suspended')c.resume().catch(()=>{});});
 for(const key of ['undo','reset','toggle','next','save','load']){const b=document.createElement('button');b.textContent=t[key];b.dataset.command=key;b.addEventListener('click',()=>command(key));$('controls').append(b);}
 const muteButton=document.createElement('button');muteButton.textContent=t.mute;muteButton.addEventListener('click',()=>sound(muted));$('controls').append(muteButton);
 window.showcaseReceive=raw=>{const s=JSON.parse(raw);window.__showcaseState=s;if(firstNative){firstNative=false;if(muted){command("sound-off");return;}}if(s.muted!==muted){muted=s.muted;audioAllowed=!muted;for(const gate of outputGates)gate.gain.value=muted?0:1;for(const c of contexts){if(muted)c.suspend().catch(()=>{});else c.resume().catch(()=>{});}}muteButton.textContent=muted?t.sound:t.mute;$('controls').querySelector('[data-command=next]').disabled=!s.won;if(t[s.status])$('save-status').textContent=t[s.status];};
 function fail(error){clearTimeout(timer);busy=false;running=false;$('status').textContent=t.error;$('start').hidden=false;$('start').disabled=false;$('start').textContent=t.retry;$('cancel').hidden=true;$('progress').hidden=true;document.body.dataset.state='error';notify({type:'showcase:state',state:'error',audio:false});console.error('Godot load failed',error);}
 async function start(){if(busy||running)return;if(document.body.dataset.state==='error'){location.reload();return;}busy=true;document.body.dataset.state='loading';$('start').disabled=true;$('cancel').hidden=false;$('status').textContent=t.loading;$('progress').hidden=false;timer=setTimeout(()=>fail(new Error('Loading timeout')),90000);
  try{if(!loader)loader=new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='../runtime/godot-4.6.3.js';s.onload=resolve;s.onerror=reject;document.head.append(s);});await loader;if(!busy)return;if(!Engine.isWebGLAvailable(2))throw new Error('WebGL 2 unavailable');
   const config=cfg.export;config.args=['--',...(mobile?['--mobile-layout']:[]),...(muted?['--muted']:[]),'--lang='+lang];const size=mobile?cfg.mobileSize:cfg.desktopSize;touch.width=size[0];touch.height=size[1];$('stage').style.aspectRatio=size.join('/');
   engine=new Engine({...config,canvas:touch,executable:'../runtime/godot-4.6.3',mainPack:'game.pck',canvasResizePolicy:0,focusCanvas:true,onProgress:(n,total)=>{if(total){$('progress').max=total;$('progress').value=n;}},onExit:()=>{if(document.body.dataset.state!=='error')location.reload();}});
   await Engine.load(config.executable,config.fileSizes[config.executable+'.wasm']);if(!busy)return;$('stage').hidden=false;await engine.startGame();if(!busy){engine.requestQuit();return;}busy=false;running=true;clearTimeout(timer);$('start').hidden=true;$('cancel').hidden=true;$('progress').hidden=true;$('exit').hidden=false;$('fullscreen').hidden=false;$('alternate').hidden=false;$('status').textContent=t.running;document.body.dataset.state='running';touch.focus({preventScroll:true});notify({type:'showcase:state',state:'running',audio:!muted});
  }catch(e){fail(e);}}
 $('start').addEventListener('click',start);$('cancel').addEventListener('click',()=>location.reload());$('exit').addEventListener('click',()=>{command('pause');if(engine)engine.requestQuit();else location.reload();});$('fullscreen').addEventListener('click',()=>$('stage').requestFullscreen?.().catch(()=>{}));
 window.addEventListener('message',e=>{if(e.origin!==location.origin||e.source!==parent||!e.data||typeof e.data!=='object')return;switch(e.data.type){case 'showcase:start':start();break;case 'showcase:reset':command('reset');break;case 'showcase:sound-on':sound(true);break;case 'showcase:sound-off':sound(false);break;}});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)command('pause');});window.addEventListener('pagehide',()=>command('pause'));notify({type:'showcase:ready'});
})();
