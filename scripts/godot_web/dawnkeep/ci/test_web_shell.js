'use strict';
const assert=require('node:assert/strict');
const {attach,browserUI}=require('./web_shell.js');
// DOM-free geometry regression. Actual pixels/hit routing are tested in Chrome.
{
  let box={width:1280,height:676},writes=0,resize;
  const raw={width:1,height:1,getBoundingClientRect:()=>box};
  const canvas=new Proxy(raw,{set:(target,key,value)=>{if(key==='width'||key==='height')writes++;target[key]=value;return true;}});
  const styles=[];
  const element=()=>({append(){},setAttribute(){},addEventListener(){}});
  global.document={head:{append:s=>styles.push(s.textContent)},body:element(),
    createElement:element,getElementById:id=>{assert.equal(id,'canvas');return canvas;}};
  global.ResizeObserver=class {constructor(callback){resize=callback;}observe(value){assert.equal(value,canvas);}};
  browserUI();assert.equal(canvas.width,1280);assert.equal(canvas.height,676);
  assert.match(styles[0],/top:44px/);assert.match(styles[0],/height:44px/);assert.doesNotMatch(styles[0],/top:132px/);
  resize();assert.equal(writes,2,'Unchanged frames must not resize/reset WebGL');
  box={width:390,height:800};resize();assert.equal(canvas.width,390);assert.equal(canvas.height,800);assert.equal(writes,4);
  delete global.document;delete global.ResizeObserver;
}
(async()=>{
  const config={},handlers={},calls=[];
  const ui={labels:w=>calls.push(['labels',w]),ready:()=>calls.push(['ready']),closing:t=>calls.push(['closing',t]),
    exited:t=>calls.push(['exited',t]),failed:t=>calls.push(['failed',t]),reload:()=>calls.push(['reload']),
    onQuit:f=>handlers.quit=f,onRestart:f=>handlers.restart=f,onRetry:f=>handlers.retry=f,onFullscreen:f=>handlers.fullscreen=f,
    fullscreen:async()=>true};
  let quit=0;const shell=attach(config,()=>quit++,ui);
  handlers.quit({isTrusted:true});assert.equal(quit,0,'Cannot quit before actual engine ready');
  config.onPrint('DAWNKEEP_FRAME_READY {"schema":1}');
  handlers.quit({isTrusted:false});assert.equal(quit,0,'Synthetic event cannot request engine exit');
  config.onPrint('DAWNKEEP_STATE {"language":"zh"}');assert.equal(calls.at(-1)[1].quit,'退出游戏');
  handlers.quit({isTrusted:true});assert.equal(quit,1);handlers.quit({isTrusted:true});assert.equal(quit,1,'No repeated quit request');
  config.onExit(0);assert.equal(calls.at(-1)[0],'exited');
  handlers.restart({isTrusted:false});assert.notEqual(calls.at(-1)[0],'reload');
  handlers.restart({isTrusted:true});assert.equal(calls.at(-1)[0],'reload');
  shell.failed(new Error('required PCK load failed'));assert.equal(calls.at(-1)[0],'failed');
  handlers.retry({isTrusted:true});assert.equal(calls.at(-1)[0],'reload');
  await handlers.fullscreen({isTrusted:true});
  console.log('Dawnkeep official-engine lifecycle shell guards passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
