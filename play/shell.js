'use strict';
(() => {
  const id = (s) => document.getElementById(s);
  const slug = document.body.dataset.case;
  const sonic = slug === 'sonic-loom';
  const lang = new URLSearchParams(location.search).get('lang') === 'zh' ? 'zh' : 'en';
  const strings = {
    en: {start:'Start demo',exit:'Exit demo',full:'Fullscreen',cancel:'Cancel loading',case:'Case study',intro:'A real Godot game runs in your browser. Start downloads the shared engine (about 36 MiB uncompressed).',ready:'Ready. No game files loaded yet.',loading:'Loading Godot…',running:'Running. Click or tap the game to focus it.',error:'Could not load the game. Check WebGL 2 support and your connection, then retry. Your video preview is still available in the case study.',retry:'Retry',play:'Play / pause',reset:'Reset',save:'Save locally',load:'Load save',slower:'Slower',faster:'Faster',select:'Select next',turn:'Turn / open',next:'Next level',pads:'Large touch controls · scroll sideways for all 16 steps',storage:'Save is local to this browser. Save before exiting; unsaved edits are lost. Private browsing or blocked storage may prevent persistence. No account or server saves.',native:'The original artwork and in-game labels remain in English. These browser controls are translated.',sonic:'Tap pads to edit; tap voice names to mute. Space: play/pause. ↑/↓: tempo. S: save, L: load, R: reset. Audio starts only after a click or tap.',prism:'Tap mirrors and shutters to steer the beam. Tab: select, Space/Enter: turn, R: reset, N: next after winning. This original puzzle is silent.',saved:'Saved locally.',loaded:'Saved state restored.',save_failed:'Saving failed. Browser storage may be unavailable.',no_save:'No saved state yet.',invalid_save:'The saved state could not be read.',closed:'Closing the game…',unsupported:'WebGL 2 is unavailable in this browser.',readyState:'Ready',notices:'Third-party notices',canvasLabel:'interactive game',alternate:'Alternative accessible controls',sonicMobile:'Choose a voice, then tap its 16 steps. Mute toggles the selected voice. Play/pause and tempo controls are above the grid; Save, Load and Reset are below. Swipe vertically to scroll.',prismMobile:'Tap a mirror or gate to select it, then use Turn or Toggle below the board. The portrait board scrolls vertically. Next opens after winning; Save and Load are in the alternative controls. This original puzzle is silent.',mute:'Mute',step:'Step',voice:'Voice'},
    zh: {start:'启动试玩',exit:'退出试玩',full:'全屏',cancel:'取消加载',case:'案例详情',intro:'真正的 Godot 游戏在浏览器中运行。点击启动后下载共享引擎（解压后约 36 MiB）。',ready:'准备就绪，尚未加载游戏资源。',loading:'正在加载 Godot…',running:'已启动，点击或轻触游戏即可操作。',error:'游戏未能加载。请检查 WebGL 2 支持及网络后重试；案例页仍可观看视频预览。',retry:'重试',play:'播放 / 暂停',reset:'重置',save:'保存到本机',load:'读取存档',slower:'减速',faster:'加速',select:'选择下一个',turn:'转动 / 开启',next:'下一关',pads:'大号触控按钮 · 横向滑动查看全部 16 步',storage:'存档仅保存在当前浏览器。退出前请先保存，未保存的修改会丢失。隐私浏览或存储限制可能导致无法保留。无需账号，不上传存档。',native:'原作画面与游戏内标签保留英文，浏览器操作区提供中文。',sonic:'轻触步进编辑节奏，点击声部名称切换静音。空格播放/暂停，上下键调速，S 保存、L 读取、R 重置。点击或轻触后才启用声音。',prism:'轻触镜子或闸门引导光束。Tab 选择、空格或回车转动、R 重置，过关后 N 进入下一关。原作没有音轨。',saved:'已保存到当前浏览器。',loaded:'已恢复存档。',save_failed:'保存失败，浏览器存储可能不可用。',no_save:'尚无存档。',invalid_save:'无法读取存档。',closed:'正在退出游戏…',unsupported:'当前浏览器无法使用 WebGL 2。',readyState:'准备就绪',notices:'第三方许可说明',canvasLabel:'交互游戏',alternate:'备用无障碍操作控件',sonicMobile:'先选择声部，再轻触其 16 个步进。Mute 切换所选声部静音。播放、暂停与速度位于网格上方，Save 保存、Load 读取、Reset 重置位于下方。上下滑动可滚动页面。',prismMobile:'先轻触镜子或闸门选择，再用棋盘下方的 Turn 或 Toggle 操作。竖版棋盘可上下滚动，过关后进入下一关。保存和读取位于备用操作区；原作没有音轨。',mute:'静音',step:'步进',voice:'声部'}
  };
  const t = strings[lang];
  const embedded = new URLSearchParams(location.search).get('embed') === '1' && parent !== window;
  if (embedded) document.body.dataset.embed = 'true';
  const report = (state) => { if (embedded) parent.postMessage({type:'showcase:state', state, audio:sonic}, location.origin); };
  let shellMuted = embedded;

  document.documentElement.lang = lang;
  id('alternate-label').textContent=t.alternate; id('notices').textContent=t.notices; id('canvas').setAttribute('aria-label',document.querySelector('h1').textContent+' · '+t.canvasLabel);
  id('start').textContent = t.start; id('exit').textContent=t.exit; id('fullscreen').textContent=t.full; id('cancel').textContent=t.cancel;
  id('case-link').textContent=t.case; id('case-link').href=`../../${lang==='zh'?'zh/':''}cases/${slug}/`;
  id('intro').textContent=t.intro; id('status').textContent=t.ready;
  id('instructions').textContent=t[sonic?'sonic':'prism']; id('storage').textContent=t.storage; id('native-language').textContent=t.native;
  id('language').textContent=lang==='zh'?'English':'中文';
  id('language').addEventListener('click',()=>{const u=new URL(location.href);u.searchParams.set('lang',lang==='zh'?'en':'zh');location.href=u;});
  let engine, started=false, pending=false, lastStatus='', loadTimer;
  // The runtime creates its AudioContext after the async download. Keep that
  // context so a later explicit HTML Play click can unlock it, just like the
  // engine's own canvas input does. Nothing resumes on page load.
  const audioContexts=new Set();
  const audioOutputs=new Map();
  if(embedded && window.AudioNode){
    const connect=AudioNode.prototype.connect;
    AudioNode.prototype.connect=function(destination,...args){
      const output=audioOutputs.get(this.context);
      return connect.call(this,output && this!==output && destination===this.context.destination ? output : destination,...args);
    };
  }
  const NativeAudio=window.AudioContext || window.webkitAudioContext;
  if(NativeAudio){
    const TrackedAudio=new Proxy(NativeAudio,{construct(target,args){const context=new target(...args);audioContexts.add(context);if(embedded){const output=context.createGain();output.gain.value=shellMuted?0:1;output.connect(context.destination);audioOutputs.set(context,output);}return context;}});
    if(window.AudioContext)window.AudioContext=TrackedAudio;else window.webkitAudioContext=TrackedAudio;
  }
  // The official Godot touch listener prevents page scrolling. These demos use
  // taps, not drags: preserve native browser vertical pan and forward a completed
  // tap as canvas mouse input. Never call the game command bridge from this path.
  let touchStart=null;
  const canvas=id('canvas');
  canvas.addEventListener('touchstart',event=>{
    if(document.body.dataset.layout!=='mobile')return;
    event.stopImmediatePropagation();
    touchStart=event.touches.length===1?{x:event.touches[0].clientX,y:event.touches[0].clientY,moved:false}:null;
  },{capture:true,passive:true});
  canvas.addEventListener('touchmove',event=>{
    if(document.body.dataset.layout!=='mobile')return;
    event.stopImmediatePropagation();
    if(touchStart && event.touches.length===1 && Math.hypot(event.touches[0].clientX-touchStart.x,event.touches[0].clientY-touchStart.y)>8)touchStart.moved=true;
  },{capture:true,passive:true});
  canvas.addEventListener('touchend',event=>{
    if(document.body.dataset.layout!=='mobile')return;
    event.stopImmediatePropagation();
    if(event.cancelable)event.preventDefault();
    const start=touchStart;touchStart=null;
    if(!start||start.moved||event.touches.length)return;
    canvas.focus({preventScroll:true});
    for(const type of ['mousedown','mouseup'])canvas.dispatchEvent(new MouseEvent(type,{bubbles:true,clientX:start.x,clientY:start.y,button:0,buttons:type==='mousedown'?1:0}));
  },{capture:true,passive:false});
  canvas.addEventListener('touchcancel',event=>{if(document.body.dataset.layout==='mobile'){event.stopImmediatePropagation();touchStart=null;}},{capture:true,passive:true});
  const buttons=[];
  function command(value) { if(sonic && !shellMuted && value==='toggle')for(const context of audioContexts)if(context.state==='suspended')context.resume().catch(()=>{}); if (typeof window.showcaseCommand === 'function') window.showcaseCommand(value); }
  function addButton(key,value=key) { const b=document.createElement('button');b.type='button';b.textContent=t[key];b.dataset.command=value;b.addEventListener('click',()=>command(value));id('controls').append(b);return b; }
  (sonic?['play','slower','faster','reset','save','load']:['select','turn','next','reset','save','load']).forEach(key=>addButton(key,key==='play'?'toggle':key));
  if(sonic){
    id('pads').querySelector('summary').textContent=t.pads;
    id('pads').open=false;
    ['EARTH','DUST','AIR','GLASS'].forEach((voice,lane)=>{
      const mute=document.createElement('button');mute.className='mute';mute.textContent=voice;mute.setAttribute('aria-label',`${t.mute} ${voice}`);mute.addEventListener('click',()=>command(`mute:${lane}`));id('pad-grid').append(mute);buttons.push({element:mute,lane,mute:true});
      for(let step=0;step<16;step++){const b=document.createElement('button');b.textContent=step+1;b.setAttribute('aria-label',`${voice} ${t.step} ${step+1}`);b.dataset.cell=`${lane}:${step}`;b.addEventListener('click',()=>command(`cell:${lane}:${step}`));id('pad-grid').append(b);buttons.push({element:b,lane,step});}
    });
  }
  window.showcaseReceive = raw => {
    const state=JSON.parse(raw);window.__showcaseState=state;
    for(const b of buttons)b.element.setAttribute('aria-pressed',String(b.mute?state.muted[b.lane]:!!state.pattern[b.lane][b.step]));
    const next=document.querySelector('[data-command=next]');if(next)next.disabled=!state.won;
    if(state.status!==lastStatus){lastStatus=state.status;
      const known={saved:t.saved,loaded:t.loaded,save_failed:t.save_failed,no_save:t.no_save,invalid_save:t.invalid_save,'PATTERN SAVED / LOCAL DEVICE':t.saved,'SAVED PATTERN RESTORED':t.loaded,'NO SAVED PATTERN YET':t.no_save,'SAVE FAILED / STORAGE UNAVAILABLE':t.save_failed};
      if(known[state.status])id('status').textContent=known[state.status];
    }
  };
  function fail(error){if(!pending)return;clearTimeout(loadTimer);pending=false;id('cancel').hidden=true;id('stage').hidden=true;id('progress').hidden=true;id('start').hidden=false;id('start').disabled=false;id('start').textContent=t.retry;id('status').textContent=t.error;console.error(error);document.body.dataset.state='error';report('error');engine?.requestQuit();}
  id('start').addEventListener('click',async()=>{
    if(pending||started)return;
    if(document.body.dataset.state==='error'){location.reload();return;}
    pending=true;id('start').disabled=true;id('status').textContent=t.loading;id('progress').hidden=false;document.body.dataset.state='loading';id('cancel').hidden=false;loadTimer=setTimeout(()=>fail(new Error('Godot startup timed out')),120000);
    try{
      await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='../runtime/godot-4.6.3.js';s.onload=resolve;s.onerror=()=>reject(new Error('Engine loader request failed'));document.head.append(s);});
      if(!pending)return;
      if(!Engine.isWebGLAvailable(2))throw new Error(t.unsupported);
      const config=JSON.parse(id('export-config').textContent);
      const mobile=matchMedia('(max-width:700px), (pointer:coarse)').matches;
      if(mobile){const height=sonic?1320:1760;config.args=['--','--mobile-layout'];id('canvas').width=720;id('canvas').height=height;id('stage').style.aspectRatio=`720 / ${height}`;id('stage').style.setProperty('--mobile-ratio',720/height);document.body.dataset.layout='mobile';}
      id('alternate').open=!mobile;id('instructions').textContent=t[sonic?(mobile?'sonicMobile':'sonic'):(mobile?'prismMobile':'prism')];
      engine=new Engine({...config,canvas:id('canvas'),executable:'../runtime/godot-4.6.3',mainPack:'game.pck',canvasResizePolicy:0,focusCanvas:true,locale:lang,onProgress:(n,total)=>{if(total){id('progress').max=total;id('progress').value=n;}},onExit:()=>{if(document.body.dataset.state!=='error')location.reload();}});
      id('stage').hidden=false;
      // Await the public load promise first: this official runtime's init()
      // does not propagate a failed WASM fetch to startGame().
      await Engine.load(config.executable, config.fileSizes[config.executable+'.wasm']);
      if(!pending)return;
      await engine.startGame();
      if(!pending){engine.requestQuit();return;}
      clearTimeout(loadTimer);id('cancel').hidden=true;
      pending=false;started=true;id('start').hidden=true;id('exit').hidden=false;id('fullscreen').hidden=false;id('controls').hidden=false;id('alternate').hidden=false;id('pads').hidden=!sonic;id('progress').hidden=true;id('status').textContent=t.running;document.body.dataset.state='running';report('running');id('canvas').focus();
    }catch(error){fail(error);}
  });
  id('cancel').addEventListener('click',()=>location.reload());
  id('exit').addEventListener('click',()=>{command('pause');id('status').textContent=t.closed;if(engine)engine.requestQuit();});
  id('fullscreen').addEventListener('click',()=>{id('stage').requestFullscreen?.().catch(()=>{});id('canvas').focus();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)command('pause');});
  window.addEventListener('pagehide',()=>command('pause'));
  // Only this same-origin parent may control its own embedded session. No
  // arbitrary commands, redirect URLs or cross-origin messages are accepted.
  window.addEventListener('message',event=>{
    if(!embedded || event.source!==parent || event.origin!==location.origin)return;
    const type=event.data?.type;
    if(type==='showcase:start')id('start').click();
    if(type==='showcase:reset' && started){command('reset');canvas.focus();}
    if(type==='showcase:sound-on' || type==='showcase:sound-off'){
      shellMuted=type==='showcase:sound-off';
      for(const output of audioOutputs.values())output.gain.value=shellMuted?0:1;
      for(const context of audioContexts)(shellMuted?context.suspend():context.resume()).catch(()=>{});
    }
  });
  if(embedded)parent.postMessage({type:'showcase:ready'},location.origin);
})();
