/* Dawnkeep lifecycle UI around the official Godot engine, without game control. */
(function (root) {
  'use strict';
  const emit = (name, value) => console.log('DAWNKEEP_WEB_' + name + ' ' + JSON.stringify(value));
  function attach(config, requestQuit, ui) {
    let language = 'en', ready = false, quitting = false;
    const words = () => language === 'zh' ? {
      quit:'退出游戏',restart:'重新打开',fullscreen:'全屏',retry:'重新载入',loading:'正在载入曙光堡…',
      exiting:'正在退出…',exited:'游戏已退出',error:'载入失败。请重试。'
    } : {quit:'Quit game',restart:'Open again',fullscreen:'Fullscreen',retry:'Retry loading',loading:'Loading Dawnkeep…',
      exiting:'Closing game…',exited:'Game closed',error:'Loading failed. Please retry.'};
    const originalPrint=config.onPrint, originalError=config.onPrintError, originalExit=config.onExit;
    const update=()=>ui.labels(words());
    update();
    config.onPrint=function(...args) {
      if (originalPrint) originalPrint(...args); else console.log(...args);
      const line=args.join(' ');
      if (line.startsWith('DAWNKEEP_FRAME_READY ')) {
        ready=true;ui.ready();emit('READY',{schema:1});
      }
      if (line.startsWith('DAWNKEEP_STATE ')) {
        try { const state=JSON.parse(line.slice('DAWNKEEP_STATE '.length)); language=state.language==='zh'?'zh':'en';update(); }
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
    style.textContent='#canvas{position:fixed;left:0;top:44px;width:100vw;height:calc(100dvh - 44px)}#dawnkeep-web-tools{box-sizing:border-box;position:fixed;inset:0 0 auto;height:44px;z-index:6;display:flex;align-items:center;justify-content:flex-end;gap:6px;padding:4px 10px;background:#101b24;border-bottom:1px solid #67552e}#dawnkeep-web-tools[hidden],#dawnkeep-web-panel[hidden],#dawnkeep-web-panel button[hidden]{display:none}#dawnkeep-web-tools button,#dawnkeep-web-panel button{font:600 12px system-ui,sans-serif;color:#fff0c9;border:1px solid #b48a40;border-radius:7px;padding:8px;background:#162329}#dawnkeep-web-panel{position:fixed;inset:0;z-index:9;background:#101b24;color:#fff0c9;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:20px;font:16px system-ui,sans-serif;text-align:center;padding:24px}';
    document.head.append(style);
    const canvas=document.getElementById('canvas');
    const resize=()=>{
      const box=canvas.getBoundingClientRect();
      // Game UI units stay CSS-pixel sized, including high-DPI browser windows.
      const width=Math.max(1,Math.round(box.width)),height=Math.max(1,Math.round(box.height));
      if(canvas.width!==width)canvas.width=width;
      if(canvas.height!==height)canvas.height=height;
    };
    resize();new ResizeObserver(resize).observe(canvas);
    const tools=document.createElement('nav');tools.id='dawnkeep-web-tools';tools.hidden=true;
    const panel=document.createElement('section');panel.id='dawnkeep-web-panel';panel.hidden=true;
    const message=document.createElement('p');message.setAttribute('role','status');panel.append(message);
    const make=(name,parent)=>{const b=document.createElement('button');b.id='dawnkeep-web-'+name;b.type='button';parent.append(b);return b;};
    const quit=make('quit',tools),fullscreen=make('fullscreen',tools),restart=make('restart',panel),retry=make('retry',panel);
    document.body.append(tools,panel);
    return {
      labels:w=>{quit.textContent=w.quit;fullscreen.textContent=w.fullscreen;restart.textContent=w.restart;retry.textContent=w.retry;},
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
  root.DawnkeepShell={attach:(config,requestQuit)=>attach(config,requestQuit,browserUI())};
  if(typeof module!=='undefined')module.exports={attach,browserUI};
}(typeof window==='undefined'?globalThis:window));
