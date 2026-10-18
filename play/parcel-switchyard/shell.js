'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const config = JSON.parse($('game-config').textContent);
  const query = new URLSearchParams(location.search);
  const lang = query.get('lang') === 'zh' ? 'zh' : 'en';
  const embedded = query.get('embed') === '1' && parent !== window;
  const t = lang === 'zh' ? {
    start:'开始游戏', retry:'重试', cancel:'取消加载', exit:'退出游戏', full:'全屏', leaveFull:'退出全屏',
    instructions:'匹配下一件包裹的号码与目的地，选择线路后发送。键盘 1/2/3 选线，空格发送，A 自动，P 暂停，R 重置。手机可直接轻触画面按钮，上下滑动可滚动。',
    ready:'点击开始后才加载共享 Godot 引擎（解压后约 36 MiB）。', loading:'正在加载 Godot…', running:'游戏已启动。可轻触画面操作。', error:'无法加载游戏。请检查网络和 WebGL 2 支持后重试。',
    note:'游戏无音轨、账号或网络存档。离开或刷新即开始新班次。游戏画面与浏览器控件均支持中英文。',
    rights:'原生项目、作品和适配代码保留原有权利边界；没有新增授权。共享 Godot 引擎另有 MIT 及第三方许可。',
    alternate:'备用无障碍操作控件', case:'案例详情', notices:'第三方许可说明',
    route0:'1 码头', route1:'2 花园', route2:'3 市场', send:'发送包裹', auto:'自动 开 / 关', pause:'暂停 / 继续', reset:'重置班次',
    next:'下一件', delivered:'送达', missed:'错投', paused:'已暂停', active:'运输中'
  } : {
    start:'Start game', retry:'Retry', cancel:'Cancel loading', exit:'Exit game', full:'Fullscreen', leaveFull:'Exit fullscreen',
    instructions:'Match the next parcel’s number and destination. Choose a route, then send. Keys: 1/2/3 route, Space send, A auto, P pause, R reset. On phones, tap the game buttons; swipe vertically to scroll.',
    ready:'Start downloads the shared Godot engine (about 36 MiB uncompressed).', loading:'Loading Godot…', running:'Running. Click or tap the game to play.', error:'Could not load. Check your connection and WebGL 2 support, then retry.',
    note:'This game is silent. No account or online saves. Leaving or reloading starts a fresh shift. The game and browser controls support English and Chinese.',
    rights:'The native project, artwork and adaptation retain their original rights boundaries; no additional license is granted. The shared Godot engine has separate MIT and third-party notices.',
    alternate:'Alternative accessible controls', case:'Case study', notices:'Third-party notices',
    route0:'1 Harbor', route1:'2 Garden', route2:'3 Market', send:'Send parcel', auto:'Auto on / off', pause:'Pause / resume', reset:'Fresh shift',
    next:'Next', delivered:'Delivered', missed:'Misrouted', paused:'Paused', active:'In transit'
  };
  document.documentElement.lang = lang;
  document.body.dataset.embed = String(embedded);
  for (const [id,key] of [['start','start'],['cancel','cancel'],['exit','exit'],['fullscreen','full'],['leave-fullscreen','leaveFull'],['instructions','instructions'],['note','note'],['rights','rights'],['alternate-label','alternate'],['case-link','case'],['notices','notices']]) $(id).textContent = t[key];
  $('case-link').href = `../../${lang==='zh'?'zh/':''}cases/parcel-switchyard/`;
  $('language').textContent = lang === 'zh' ? 'English' : '中文';
  $('language').onclick = () => { const url = new URL(location.href); url.searchParams.set('lang',lang==='zh'?'en':'zh'); location.href=url; };
  $('canvas').setAttribute('aria-label',lang==='zh'?'Parcel Switchyard 包裹分拣游戏':'Parcel Switchyard interactive sorting game');
  $('status').textContent = t.ready;
  const notify = state => { if(parent!==window) parent.postMessage(state,location.origin); };
  const command = value => { if(typeof window.showcaseCommand === 'function') window.showcaseCommand(value); };
  let engine, pending=false, running=false, timeout, mobile=null;
  function resize() {
    const compact = document.documentElement.clientWidth < 1100 || matchMedia('(pointer:coarse)').matches;
    if(compact===mobile) return;
    mobile=compact; document.body.dataset.layout=mobile?'mobile':'desktop';
    $('canvas').width=mobile?720:1280; $('canvas').height=mobile?1320:720;
    fitEmbeddedCanvas();
    if(running) command(mobile?'layout:mobile':'layout:desktop');
    notify({type:'showcase:layout',mode:mobile?'mobile':'desktop',width:mobile?720:1280,height:mobile?1320:720});
  }
  function fitEmbeddedCanvas() {
    if(!embedded || $('stage').hidden)return;
    const ratio=mobile?720/1320:1280/720;
    const width=Math.min($('stage').clientWidth,$('stage').clientHeight*ratio);
    if(width<=0)return;
    $('canvas').style.width=width+'px';$('canvas').style.height=(width/ratio)+'px';
  }
  new ResizeObserver(fitEmbeddedCanvas).observe($('stage'));
  new ResizeObserver(resize).observe(document.documentElement);
  window.addEventListener('resize',resize); resize();
  new ResizeObserver(()=>notify({type:'showcase:resize',height:Math.ceil(document.querySelector('main').getBoundingClientRect().height)})).observe(document.querySelector('main'));
  // Same tap/pan approach as existing Showcase portrait exports: a real browser
  // touch tap becomes canvas mouse input; a vertical drag scrolls and never plays.
  // This does not call the game command bridge or modify the game state.
  let touch=null;
  $('canvas').addEventListener('touchstart',event=>{
    if(!mobile)return; event.stopImmediatePropagation();
    touch=event.touches.length===1?{x:event.touches[0].clientX,y:event.touches[0].clientY,moved:false}:null;
  },{capture:true,passive:true});
  $('canvas').addEventListener('touchmove',event=>{
    if(!mobile)return; event.stopImmediatePropagation();
    if(touch && event.touches.length===1 && Math.hypot(event.touches[0].clientX-touch.x,event.touches[0].clientY-touch.y)>8) touch.moved=true;
  },{capture:true,passive:true});
  $('canvas').addEventListener('touchend',event=>{
    if(!mobile)return; event.stopImmediatePropagation();
    if(event.cancelable)event.preventDefault(); const point=touch;touch=null;
    if(!point || point.moved || event.touches.length)return;
    $('canvas').focus({preventScroll:true});
    for(const type of ['mousedown','mouseup']) $('canvas').dispatchEvent(new MouseEvent(type,{bubbles:true,clientX:point.x,clientY:point.y,button:0,buttons:type==='mousedown'?1:0}));
  },{capture:true,passive:false});
  $('canvas').addEventListener('touchcancel',()=>{touch=null;},{capture:true,passive:true});
  for(const value of ['route:0','route:1','route:2','send','auto','pause','reset']) {
    const button=document.createElement('button');button.type='button';button.dataset.command=value;
    button.textContent=t[value.replace(':','')];button.addEventListener('click',()=>command(value));$('controls').append(button);
  }
  let lastSummary='';
  window.showcaseReceive = raw => {
    const state=JSON.parse(raw);window.__parcelState=state;
    const summary=`${t.next}: ${state.next_target+1}. ${t.delivered}: ${state.delivered}. ${t.missed}: ${state.missed}. ${t.active}: ${state.active}.${state.paused?' '+t.paused:''}`;
    if(summary!==lastSummary){$('accessible-state').textContent=summary;lastSummary=summary;}
    for(let route=0;route<3;route++) $('controls').querySelector(`[data-command="route:${route}"]`).setAttribute('aria-pressed',String(state.selected===route));
  };
  function fail(error) {
    clearTimeout(timeout);pending=false;running=false;document.body.dataset.state='error';
    $('status').textContent=t.error;$('start').hidden=false;$('start').disabled=false;$('start').textContent=t.retry;$('cancel').hidden=true;$('progress').hidden=true;
    if(engine)engine.requestQuit();notify({type:'showcase:state',state:'error',audio:false});console.error('Godot load failed',error);
  }
  async function start() {
    if(pending||running)return;
    if(document.body.dataset.state==='error'){location.reload();return;}
    pending=true;document.body.dataset.state='loading';$('start').disabled=true;$('cancel').hidden=false;$('progress').hidden=false;$('status').textContent=t.loading;
    timeout=setTimeout(()=>fail(new Error('Loading timeout')),90000);
    try {
      await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='../runtime/godot-4.6.3.js';script.onload=resolve;script.onerror=reject;document.head.append(script);});
      if(!pending)return;if(!Engine.isWebGLAvailable(2))throw new Error('WebGL 2 unavailable');
      const options={...config,canvas:$('canvas'),executable:'../runtime/godot-4.6.3',mainPack:'game.pck',canvasResizePolicy:0,focusCanvas:true,args:['--','--lang='+lang,...(mobile?['--mobile-layout']:[])],onProgress:(value,total)=>{if(total){$('progress').max=total;$('progress').value=value;}},onExit:()=>{if(document.body.dataset.state!=='error')location.reload();}};
      engine=new Engine(options);await Engine.load(options.executable,options.fileSizes[options.executable+'.wasm']);
      if(!pending)return;$('stage').hidden=false;
      // Keep the stable Godot virtual filename, but use the hash-bound URL so a
      // cached old PCK cannot silently satisfy a new review export.
      await engine.preloadFile('game.pck?v='+config.showcasePackSha256,'game.pck');
      await engine.start({args:['--main-pack','game.pck',...options.args]});
      if(!pending){engine.requestQuit();return;}
      pending=false;running=true;clearTimeout(timeout);$('start').hidden=true;$('cancel').hidden=true;$('progress').hidden=true;$('exit').hidden=false;$('fullscreen').hidden=false;$('alternate').hidden=false;$('status').textContent=t.running;
      document.body.dataset.state='running';fitEmbeddedCanvas();command(mobile?'layout:mobile':'layout:desktop');$('canvas').focus({preventScroll:true});notify({type:'showcase:state',state:'running',audio:false});
    } catch(error){fail(error);}
  }
  $('start').onclick=start;$('cancel').onclick=()=>location.reload();$('exit').onclick=()=>{command('stop');if(engine)engine.requestQuit();else location.reload();};
  function leaveFullscreen() {
    if(document.fullscreenElement===$('stage')) document.exitFullscreen?.().catch(()=>{});
  }
  $('fullscreen').onclick=()=>{$('stage').requestFullscreen?.().catch(()=>{});};
  $('leave-fullscreen').onclick=leaveFullscreen;
  document.addEventListener('fullscreenchange',()=>{
    const full=document.fullscreenElement===$('stage');
    $('fullscreen-tools').hidden=!full;
    $('fullscreen').setAttribute('aria-expanded',String(full));
    if(!full && running) $('fullscreen').focus({preventScroll:true});
  });
  // Keep a real keyboard exit even when the canvas consumes the browser's key.
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape' && document.fullscreenElement===$('stage')) {
      event.preventDefault();leaveFullscreen();
    }
  },true);
  window.addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==parent||!event.data)return;if(event.data.type==='showcase:start')start();else if(event.data.type==='showcase:reset')command('reset');else if(event.data.type==='showcase:pause')command('stop');});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)command('stop');});window.addEventListener('pagehide',()=>command('stop'));
  notify({type:'showcase:ready'});
})();
