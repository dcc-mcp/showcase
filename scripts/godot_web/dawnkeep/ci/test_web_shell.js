'use strict';
const assert=require('node:assert/strict');
const {attach}=require('./web_shell.js');
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
