#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../assets/playable.js'), 'utf8');
function node(extra = {}) {
  const listeners = new Map();
  return Object.assign({dataset:{}, style:{}, hidden:false, children:[],
    addEventListener(k,fn){if(!listeners.has(k))listeners.set(k,new Set());listeners.get(k).add(fn);},
    removeEventListener(k,fn){listeners.get(k)?.delete(fn);},
    emit(k,e={}){for(const fn of listeners.get(k)||[])fn(e);},
    count(k){return listeners.get(k)?.size||0;},
    setAttribute(k,v){this[k]=v;}, append(n){this.children.push(n);},
    replaceChildren(){this.children=[];},
    querySelector(s){return s==='iframe'?this.children.find(n=>n.tag==='iframe')||null:null;},
    focus(options){this.focused=options||true;},
    scrollIntoView(options){this.scrolled=options;},
    getBoundingClientRect(){return {height:this.height||60};}
  },extra);
}
function fixture(caseSlug='dawnkeep-defense') {
  const start=node({dataset:{playUrl:'../../play/'+caseSlug+'/index.html'}}), exit=node(), holder=node(), status=node(), link=node(), actions=node({height:60});
  const map={'[data-play-start]':start,'[data-play-exit]':exit,'[data-play-frame]':holder,'[data-play-status]':status,'[data-play-link]':link,'.playable-actions':actions};
  const section=node({dataset:{playCase:caseSlug,playRevision:'verified'},querySelector:s=>map[s]});
  const observers=[];
  const visualViewport=node({height:844});
  const window=node({innerHeight:844,visualViewport,getComputedStyle:()=>({scrollPaddingTop:'28px'}),location:{href:'https://example.com/cases/test/',origin:'https://example.com'},
    ResizeObserver:class {constructor(fn){this.fn=fn;observers.push(this);}observe(n){this.node=n;}disconnect(){this.disconnected=true;}}});
  const document={documentElement:{lang:'en'},querySelectorAll:()=>[section],createElement:tag=>node({tag,contentWindow:{},offsetHeight:760,clientHeight:758})};
  vm.runInNewContext(source,{window,document,URL,Math,Number});
  return {start,exit,holder,actions,section,window,observers};
}
let passed=0;function test(name,fn){fn();passed++;console.log('PASS '+name);}
test('Dawnkeep opens a viewport-fit frame with an aligned persistent toolbar',()=>{
  const f=fixture();f.start.emit('click');const frame=f.holder.children[0];
  assert.equal(frame.style.height,'732px');assert.equal(frame.style.minHeight,'0');assert.equal(frame.style.maxHeight,'none');
  assert.equal(f.section.dataset.playOpen,'true');assert.equal(f.exit.hidden,false);assert.equal(f.start.hidden,true);
  assert.equal(f.actions.scrolled.block,'start');assert.equal(frame.focused.preventScroll,true);
  assert.equal(f.window.count('resize'),1);assert.equal(f.observers.length,1);
});
test('visual viewport and toolbar changes refit without expanding beyond the screen',()=>{
  const f=fixture();f.start.emit('click');f.window.visualViewport.height=700;f.window.visualViewport.emit('resize');
  assert.equal(f.holder.children[0].style.height,'588px');f.actions.height=112;f.observers[0].fn();
  assert.equal(f.holder.children[0].style.height,'536px');
});
test('root scroll padding is reserved rather than clipping bottom controls',()=>{
  const f=fixture();f.start.emit('click');f.window.getComputedStyle=()=>({scrollPaddingTop:'48px'});f.window.emit('resize');
  assert.equal(f.holder.children[0].style.height,'712px');
});
test('same-origin game resize cannot grow Dawnkeep beyond its bounded frame',()=>{
  const f=fixture();f.start.emit('click');const frame=f.holder.children[0];
  f.window.emit('message',{source:frame.contentWindow,origin:'https://example.com',data:{type:'showcase:resize',height:10000}});
  assert.equal(frame.style.height,'732px');
});
test('foreign resize messages still do nothing',()=>{
  const f=fixture();f.start.emit('click');const frame=f.holder.children[0];f.window.visualViewport.height=600;
  f.window.emit('message',{source:frame.contentWindow,origin:'https://evil.example',data:{type:'showcase:resize',height:9999}});
  assert.equal(frame.style.height,'732px');
});
test('exit removes observers and frame, and reopen creates only one listener',()=>{
  const f=fixture();f.start.emit('click');f.start.emit('click');assert.equal(f.holder.children.length,1);f.exit.emit('click');
  assert.equal(f.holder.children.length,0);assert.equal(f.section.dataset.playOpen,undefined);assert.equal(f.window.count('resize'),0);
  assert.equal(f.window.visualViewport.count('resize'),0);assert.equal(f.observers[0].disconnected,true);assert.equal(f.start.focused,true);
  f.start.emit('click');assert.equal(f.window.count('resize'),1);assert.equal(f.holder.children.length,1);
});
test('other showcases preserve their existing resize and focus behavior',()=>{
  const f=fixture('sample');f.start.emit('click');const frame=f.holder.children[0];
  assert.equal(frame.style.height,undefined);assert.equal(f.actions.scrolled,undefined);assert.equal(frame.focused,true);assert.equal(f.window.count('resize'),0);
  f.window.emit('message',{source:frame.contentWindow,origin:'https://example.com',data:{type:'showcase:resize',height:900}});
  assert.equal(frame.style.height,'902px');
});
console.log(`${passed} playable lifecycle guards passed`);
