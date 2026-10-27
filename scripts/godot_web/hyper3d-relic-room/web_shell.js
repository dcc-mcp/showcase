/* RelicCourier lifecycle UI around the official Godot engine, without game control. */
(function (root) {
  'use strict';
  const emit = (name, value) => console.log('RELIC_WEB_' + name + ' ' + JSON.stringify(value));
  function initialLanguage(search, documentLanguage) {
    const requested = new URLSearchParams(search).get('lang');
    if (requested === 'en' || requested === 'zh') return requested;
    return /^zh(?:-|$)/i.test(documentLanguage || '') ? 'zh' : 'en';
  }
  function attach(config, requestQuit, ui) {
    // Before the engine emits its language, load/retry UI follows the page.
    // Once running, the existing native language control remains authoritative.
    let language = ui.language === 'zh' ? 'zh' : 'en', ready = false, quitting = false;
    const words = () => language === 'zh' ? {
      quit:'退出游戏',restart:'重新打开',fullscreen:'全屏',retry:'重新载入',loading:'正在载入遗迹信使…',
      exiting:'正在退出…',exited:'游戏已退出',error:'载入失败。请重试。',case:'案例详情'
    } : {quit:'Quit game',restart:'Open again',fullscreen:'Fullscreen',retry:'Retry loading',loading:'Loading Relic Courier…',
      exiting:'Closing game…',exited:'Game closed',error:'Loading failed. Please retry.',case:'Case study'};
    const originalPrint=config.onPrint, originalError=config.onPrintError, originalExit=config.onExit;
    const update=()=>ui.labels(words());
    update();
    config.onPrint=function(...args) {
      if (originalPrint) originalPrint(...args); else console.log(...args);
      const line=args.join(' ');
      if (line.startsWith('RELIC_FRAME_READY ')) {
        ready=true;ui.ready();emit('READY',{schema:1});
      }
      if (line.startsWith('RELIC_STATE ')) {
        try { const state=JSON.parse(line.slice('RELIC_STATE '.length)); language=state.locale==='zh'?'zh':'en';update(); }
        catch (_) { emit('OBSERVER_ERROR',{schema:1}); }
      }
    };
    config.onPrintError=function(...args) {
      if(originalError) originalError(...args);else console.error(...args);
    };
    config.onExit=function(code) {
      if(originalExit)originalExit(code);
      ui.exited(words().exited);emit('EXIT',{schema:1,code,requested:quitting,ok:quitting&&code===0});
    };
    ui.onQuit(event=>{
      if(!ready||quitting||event.isTrusted!==true)return;
      quitting=true;ui.closing(words().exiting);emit('QUIT_REQUEST',{schema:1,trusted:true});requestQuit();
    });
    ui.onRestart(event=>{
      if(event.isTrusted!==true)return;emit('RESTART_REQUEST',{schema:1,trusted:true});ui.reload();
    });
    ui.onRetry(event=>{
      if(event.isTrusted!==true)return;emit('RETRY_REQUEST',{schema:1,trusted:true});ui.reload();
    });
    ui.onFullscreen(async event=>{
      if(event.isTrusted!==true)return;
      try { const active=await ui.fullscreen();emit('FULLSCREEN',{schema:1,trusted:true,active}); }
      catch(error){emit('FULLSCREEN',{schema:1,trusted:true,active:false,error:String(error)});}
    });
    return {failed(error){ui.failed(words().error);emit('LOAD_ERROR',{schema:1,message:String(error)});}};
  }
  function browserUI() {
    const style=document.createElement('style');
    // Reserve a real strip outside the engine viewport. Overlaying these tools
    // at y=132 covered Godot's shop Close control, especially on portrait.
    style.textContent='#canvas{position:fixed;left:0;top:44px;width:100vw;height:calc(100dvh - 44px)}#relic-courier-web-tools{box-sizing:border-box;position:fixed;inset:0 0 auto;height:44px;z-index:6;display:flex;align-items:center;justify-content:flex-end;gap:6px;padding:4px 10px;background:#101b24;border-bottom:1px solid #67552e}#relic-courier-web-tools[hidden],#relic-courier-web-panel[hidden],#relic-courier-web-panel button[hidden]{display:none}#relic-courier-web-tools button,#relic-courier-web-panel button,#relic-courier-web-tools a,#relic-courier-web-panel a{font:600 12px system-ui,sans-serif;color:#fff0c9;border:1px solid #b48a40;border-radius:7px;padding:8px;background:#162329;text-decoration:none}#relic-courier-web-panel{position:fixed;inset:0;z-index:9;background:#101b24;color:#fff0c9;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:20px;font:16px system-ui,sans-serif;text-align:center;padding:24px}';
    document.head.append(style);
    const canvas=document.getElementById('canvas');
    const resize=()=>{
      const box=canvas.getBoundingClientRect();
      // Back the CSS viewport with device pixels, bounded for WebGL memory.
      const ratio=root.devicePixelRatio;
      const scale=Number.isFinite(ratio)&&ratio>0?Math.min(ratio,2):1;
      const width=Math.max(1,Math.round(box.width*scale)),height=Math.max(1,Math.round(box.height*scale));
      if(canvas.width!==width)canvas.width=width;
      if(canvas.height!==height)canvas.height=height;
    };
    resize();new ResizeObserver(resize).observe(canvas);
    const tools=document.createElement('nav');tools.id='relic-courier-web-tools';tools.hidden=true;
    const panel=document.createElement('section');panel.id='relic-courier-web-panel';panel.hidden=true;
    const message=document.createElement('p');message.setAttribute('role','status');panel.append(message);
    const make=(name,parent)=>{const b=document.createElement('button');b.id='relic-courier-web-'+name;b.type='button';parent.append(b);return b;};
    const quit=make('quit',tools),fullscreen=make('fullscreen',tools),restart=make('restart',panel),retry=make('retry',panel);
    const links=[tools,panel].map(container=>{const link=document.createElement('a');container.append(link);return link;});
    document.body.append(tools,panel);
    return {
      language:initialLanguage(location.search,document.documentElement.lang),
      labels:w=>{quit.textContent=w.quit;fullscreen.textContent=w.fullscreen;restart.textContent=w.restart;retry.textContent=w.retry;for(const link of links){link.textContent=w.case;link.href='../../'+(w.case==='案例详情'?'zh/':'')+'cases/hyper3d-relic-room/';}},
      ready:()=>{tools.hidden=false;panel.hidden=true;},
      closing:text=>{tools.hidden=true;panel.hidden=false;message.textContent=text;restart.hidden=true;retry.hidden=true;},
      exited:text=>{tools.hidden=true;panel.hidden=false;message.textContent=text;restart.hidden=false;retry.hidden=true;},
      failed:text=>{tools.hidden=true;panel.hidden=false;message.textContent=text;restart.hidden=true;retry.hidden=false;},
      onQuit:f=>quit.addEventListener('click',f),onRestart:f=>restart.addEventListener('click',f),
      onRetry:f=>retry.addEventListener('click',f),onFullscreen:f=>fullscreen.addEventListener('click',f),
      reload:()=>location.reload(),
      fullscreen:async()=>{if(document.fullscreenElement){await document.exitFullscreen();return false;}await document.documentElement.requestFullscreen();return true;}
    };
  }
  root.RelicCourierShell={attach:(config,requestQuit)=>attach(config,requestQuit,browserUI())};
  if(typeof module!=='undefined')module.exports={attach,browserUI,initialLanguage};
}(typeof window==='undefined'?globalThis:window));
