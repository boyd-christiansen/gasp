'use strict';
// All tracks share radar time. Word annotations stay unplaced until explicitly aligned.
const channels={audio:true,words:true,phase:true,range:true};
let trackLayout={},trackCache={},spanSignature='',transcriptSignature='';
function trackGeometry(){let y=32;const rows={};for(const [key,height]of Object.entries({audio:52,words:50,phase:64,range:76})){if(channels[key]){rows[key]={y,height};y+=height;}}return{rows,height:y+8};}
function renderUnplaced(){renderTranscript();}
function selectTimelineWord(index){
 wordIndex=index;wordPlacement=words[index]?.start_s==null;
 drawTimeline();updateWordLabel();
}
function jumpToWord(index){if(words[index]?.start_s!=null){pause();setTime(words[index].start_s);followTimeline();}}
function renderTranscript(){
 const signature=words.map(w=>[w.text,w.start_s,w.end_s].join('|')).join('\n');
 if(signature!==transcriptSignature&&!timelineDrag){
  transcriptSignature=signature;
  GaspWorkspace.render($('reviewTranscript'),words.length?words.map((w,i)=>`<button data-ui-key="word-${i}" data-transcript="${i}" class="${w.start_s==null?'unplaced':''}" title="${w.start_s==null?'Drag into Audio or Words to place':'Select to edit · double-click to jump'}">${esc(w.text)}</button>`).join(' '):'<span class="subtle">Add or confirm the text below. Word timing is optional.</span>',selected?.id||'empty');
 }
 $('reviewTranscript').querySelectorAll('button').forEach(b=>{const i=Number(b.dataset.transcript),w=words[i];b.classList.toggle('active',w.start_s!=null&&time>=w.start_s&&time<=w.end_s);b.classList.toggle('selected',i===wordIndex);b.setAttribute('aria-pressed',String(i===wordIndex));});
}
function followTimeline(){if(!replay)return;const scroller=$('timelineScroll'),x=time/replay.duration_s*$('timelineSheet').clientWidth;if(x<scroller.scrollLeft+10||x>scroller.scrollLeft+scroller.clientWidth-10)scroller.scrollLeft=Math.max(0,x-scroller.clientWidth*.25);}
function renderSpans(){if(!replay)return;const signature=JSON.stringify([words,zoom,channels.words]);if(spanSignature!==signature&&!timelineDrag){spanSignature=signature;GaspWorkspace.render($('wordSpans'),words.map((w,i)=>w.start_s!=null&&w.end_s!=null?`<div class="word-span" data-ui-key="span-${i}" data-span="${i}"><button class="word-edge start" data-edge="start_s" data-index="${i}" aria-label="Start of ${esc(w.text)}" title="Drag or use arrow keys"></button><button class="word-body" data-word="${i}">${esc(w.text)}</button><button class="word-edge end" data-edge="end_s" data-index="${i}" aria-label="End of ${esc(w.text)}" title="Drag or use arrow keys"></button></div>`:'').join(''),selected.id);}
 const lane=trackLayout.words;$('wordSpans').hidden=!lane;$('wordSpans').style.top=(lane?.y+11)+'px';
 $('wordSpans').querySelectorAll('[data-span]').forEach(el=>{const i=Number(el.dataset.span),w=words[i];el.style.left=w.start_s/replay.duration_s*100+'%';el.style.width=(w.end_s-w.start_s)/replay.duration_s*100+'%';el.classList.toggle('estimated',w.source!=='manual');el.classList.toggle('selected',i===wordIndex);el.classList.toggle('active',time>=w.start_s&&time<=w.end_s);el.querySelector('.word-body').title=`${w.text} · ${w.start_s.toFixed(2)}–${w.end_s.toFixed(2)} s`;for(const edge of el.querySelectorAll('[data-edge]'))edge.setAttribute('aria-label',`${edge.dataset.edge==='start_s'?'Start':'End'} of ${w.text}, ${w[edge.dataset.edge].toFixed(2)} seconds`);});}
function drawTimeline(){if(!replay||stage!=='replay'||tab!=='capture'||dictation)return;const geom=trackGeometry();trackLayout=geom.rows;const scroll=$('timelineScroll'),sheet=$('timelineSheet'),width=Math.max(240,scroll.clientWidth)*zoom;sheet.style.width=width+'px';sheet.style.height=geom.height+'px';$('timeline').style.height=geom.height+'px';$('sharedPlayhead').style.left=(time/replay.duration_s*100)+'%';$('sharedPlayhead').style.height=geom.height+'px';
 const key=[selected.id,width,geom.height,JSON.stringify(channels),audioOffset,waveform.length,selected.media?.bytes,replay.selected_bin,replay.selected_antenna,words.some(w=>w.start_s!=null&&w.end_s!=null)].join('|');
 if(trackCache.key!==key||trackCache.replay!==replay||trackCache.waveform!==waveform){trackCache={key,replay,waveform};const {ctx,w}=canvas('timeline',geom.height),x=t=>t/replay.duration_s*w;ctx.fillStyle='#fcfcfc';ctx.fillRect(0,0,w,geom.height);ctx.strokeStyle='#e8e8e8';ctx.fillStyle='#888';ctx.textAlign='center';const marks=Math.max(4,Math.round(w/100));for(let i=0;i<=marks;i++){const xx=w*i/marks;ctx.fillText((replay.duration_s*i/marks).toFixed(replay.duration_s<20?1:0)+'s',Math.max(16,Math.min(w-16,xx)),20);ctx.beginPath();ctx.moveTo(xx,28);ctx.lineTo(xx,geom.height);ctx.stroke();}
 $('trackLabels').style.height=geom.height+'px';$('trackLabels').innerHTML=Object.entries(trackLayout).map(([k,l])=>`<span style="top:${l.y}px;height:${l.height}px">${{audio:'Audio',words:'Words',phase:'Phase',range:'Range'}[k]}${k==='phase'?'<small>rad</small>':k==='range'?`<small>0–${replay.range_m.at(-1).toFixed(1)}m</small>`:''}</span>`).join('');
 for(const [k,l]of Object.entries(trackLayout)){ctx.strokeStyle='#e1e1e1';ctx.beginPath();ctx.moveTo(0,l.y);ctx.lineTo(w,l.y);ctx.stroke();const center=l.y+l.height/2;if(k==='audio'){if(waveform.length){ctx.strokeStyle='#6f6f6f';ctx.beginPath();waveform.forEach((v,i)=>{const xx=x(audioOffset+i/Math.max(1,waveform.length-1)*(Number.isFinite(audio.duration)?audio.duration:replay.duration_s));ctx.moveTo(xx,center-v*27);ctx.lineTo(xx,center+v*27);});ctx.stroke();}else{ctx.fillStyle='#999';ctx.textAlign='left';ctx.fillText(waveformError||(selected.media?'Loading reference waveform…':'No reference audio'),12,center+3);}}
 if(k==='audio'&&selected.processing_window?.start_s){const end=Math.max(0,audioOffset+selected.processing_window.start_s);ctx.fillStyle='#17171726';ctx.fillRect(0,l.y,Math.max(0,x(end)),l.height);if(x(end)>45){ctx.fillStyle='#555';ctx.textAlign='left';ctx.fillText('Cue',6,l.y+14);}}
 if(k==='words'&&!words.some(w=>w.start_s!=null&&w.end_s!=null)){ctx.fillStyle='#999';ctx.textAlign='left';ctx.fillText(selected.media?'Drag a word here, or select it and draw its span in Audio or Words':'Word timing is optional · select a word, then use [ and ] to mark boundaries',12,center+3);}
 if(k==='phase'){const values=replay.phase,ts=replay.signal_time_s||replay.time_s;let lo=Infinity,hi=-Infinity;for(const v of values){lo=Math.min(lo,v);hi=Math.max(hi,v);}line(ctx,values,i=>x(ts[i]),v=>l.y+l.height-8-(v-lo)/(hi-lo||1)*(l.height-16),'#666');}
 if(k==='range'){const data=replay.range_time,ts=replay.time_s;for(let i=0;i<data.length;i++){const a=x(ts[i]),b=x(ts[i+1]??replay.duration_s);for(let j=0;j<data[i].length;j++){const gray=Math.round(255-210*Math.min(1,Math.log1p(data[i][j])/(replay.log_max||1)));ctx.fillStyle=`rgb(${gray},${gray},${gray})`;ctx.fillRect(a,l.y+j/data[i].length*l.height,Math.max(1,b-a+.5),l.height/data[i].length+.5);}}}
 for(const gap of (['phase','range'].includes(k)?replay.gaps||[]:[])){const a=x(gap[0]),width=Math.max(3,x(gap[1])-a);ctx.fillStyle='#b53d3d45';ctx.fillRect(a,l.y,width,l.height);ctx.fillStyle='#a63232';ctx.fillRect(a,l.y,1,l.height);}}
 // Keep gap markers visible even when both radar tracks are hidden. A small
 // minimum width makes isolated dropped frames legible at the full-take scale.
 for(const gap of replay.gaps||[]){const a=x(gap[0]),width=Math.max(3,x(gap[1])-a);ctx.fillStyle='#a63232';ctx.fillRect(a,25,width,7);}
 }
 renderSpans();renderTranscript();renderWordDraft();renderAudioLoop();$('undoTiming').disabled=!undo.length;updateWordLabel();if(playing&&!timelineDrag)followTimeline();}
function timelineAt(e){const r=$('timelineSheet').getBoundingClientRect();return Math.max(0,Math.min(replay.duration_s,(e.clientX-r.left)/r.width*replay.duration_s));}
// Editing and playback deliberately have separate cursors. A trim never seeks.
function moveWordEdge(index,edge,t){
 const w=words[index],bounds=wordLimits(index);
 w[edge]=edge==='start_s'?Math.max(bounds.start,Math.min(w.end_s-.02,t)):Math.min(bounds.end,Math.max(w.start_s+.02,t));
 w.source='manual';dirty=true;$('reviewState').textContent='Unsaved timing · needs review';drawTimeline();
}
function moveWholeWord(index,start,original){
 const bounds=wordLimits(index),duration=original.end_s-original.start_s;
 const a=Math.max(bounds.start,Math.min(bounds.end-duration,start));
 Object.assign(words[index],{start_s:a,end_s:a+duration,source:'manual'});
 dirty=true;$('reviewState').textContent='Unsaved timing · needs review';drawTimeline();
}
function timelineLaneAt(e){
 const r=$('timelineSheet').getBoundingClientRect();
 if(e.clientX<r.left||e.clientX>r.right)return null;
 const y=e.clientY-r.top;
 return Object.entries(trackLayout).find(([,l])=>y>=l.y&&y<l.y+l.height)?.[0]||null;
}
function placementAt(index,t){
 const bounds=wordLimits(index),w=words[index],duration=Math.min(w.start_s!=null&&w.end_s!=null?w.end_s-w.start_s:.3,bounds.end-bounds.start);
 if(duration<.02||t<bounds.start||t>bounds.end)return null;
 const start=Math.max(bounds.start,Math.min(bounds.end-duration,t));
 return{start,end:start+duration};
}
function renderWordDraft(){
 const el=$('wordDraft'),w=words[wordIndex],drag=timelineDrag;
 const partial=w&&w.start_s!=null&&w.end_s==null;
 const draft=drag?.placing?{start:Math.min(drag.start,drag.end),end:Math.max(drag.start,drag.end)}:drag?.drop||null;
 if((!draft&&!partial)||!replay){el.hidden=true;return;}
 const start=draft?.start??w.start_s,end=draft?.end??start+.015,lane=trackLayout.words||trackLayout.audio;
 el.hidden=!lane;el.textContent=w?.text||'';el.style.top=(lane?.y+10)+'px';el.style.left=start/replay.duration_s*100+'%';el.style.width=Math.max(.15,(end-start)/replay.duration_s*100)+'%';
}
function beginWordEdit(e,drag){
 timelineDrag={...drag,x:e.clientX,y:e.clientY,before:JSON.stringify(words),wasDirty:dirty,reviewText:$('reviewState').textContent};
 e.preventDefault();e.currentTarget.setPointerCapture(e.pointerId);drawTimeline();
}
function rememberEdit(drag){if(!drag.undoAdded){pushUndo();drag.undoAdded=true;}}
$('timelineSheet').onpointerdown=e=>{
 if(!replay||e.button!==0)return;
 const edge=e.target.closest('[data-edge]'),body=e.target.closest('[data-word]');
 if(edge||body){
  wordIndex=Number(edge?edge.dataset.index:body.dataset.word);wordPlacement=false;
  (edge||body).focus({preventScroll:true});
  beginWordEdit(e,{index:wordIndex,edge:edge?.dataset.edge,moving:!!body,original:{...words[wordIndex]},start:timelineAt(e)});
 }else{
  const t=timelineAt(e),lane=timelineLaneAt(e),place=words[wordIndex]&&!controlTake(selected)&&['audio','words'].includes(lane);
  if(place)beginWordEdit(e,{placing:true,index:wordIndex,start:t,end:t});
  else{pause();setTime(t);beginWordEdit(e,{scrubbing:true});}
  $('timeline').focus({preventScroll:true});
 }
};
$('reviewTranscript').onpointerdown=e=>{
 const b=e.target.closest('[data-transcript]');if(!replay||!b||e.button!==0)return;
 wordIndex=Number(b.dataset.transcript);wordPlacement=words[wordIndex].start_s==null;b.focus({preventScroll:true});
 beginWordEdit(e,{fromTranscript:true,index:wordIndex});
};
let suppressWordClick=false;
$('reviewTranscript').onclick=e=>{const b=e.target.closest('[data-transcript]');if(b&&!suppressWordClick)selectTimelineWord(Number(b.dataset.transcript));};
$('wordSpans').onclick=e=>{const b=e.target.closest('[data-word]');if(b&&!suppressWordClick)selectTimelineWord(Number(b.dataset.word));};
for(const id of ['reviewTranscript','wordSpans'])$(id).ondblclick=e=>{const b=e.target.closest('[data-word],[data-transcript]');if(b)jumpToWord(Number(b.dataset.word??b.dataset.transcript));};
function updateTimelineEdit(e){
 const drag=timelineDrag;if(!drag||!replay)return;
 // Ignore hover/pointer restoration events after the physical button is up.
 if(!(e.buttons&1))return;
 const t=timelineAt(e);drag.moved=drag.moved||Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>4;
 if(drag.scrubbing){setTime(t);return;}
 if(!drag.moved)return;
 if(drag.edge){rememberEdit(drag);moveWordEdge(drag.index,drag.edge,t);}
 else if(drag.moving){rememberEdit(drag);moveWholeWord(drag.index,drag.original.start_s+t-drag.start,drag.original);}
 else if(drag.fromTranscript){drag.drop=['audio','words'].includes(timelineLaneAt(e))?placementAt(drag.index,t):null;renderWordDraft();}
 else if(drag.placing){drag.end=t;renderWordDraft();}
}
function endTimelineEdit(e){
 const drag=timelineDrag;if(!drag)return;
 if(drag.moved&&(drag.placing||drag.drop)){
  const bounds=wordLimits(drag.index),a=drag.drop?.start??Math.max(bounds.start,Math.min(drag.start,drag.end)),b=drag.drop?.end??Math.min(bounds.end,Math.max(drag.start,drag.end));
  if(b-a>=.02){rememberEdit(drag);Object.assign(words[drag.index],{start_s:a,end_s:b,source:'manual'});wordPlacement=false;dirty=true;$('reviewState').textContent='Word placed · drag to move or trim · unsaved';}
 }else if(drag.placing&&!drag.moved){pause();setTime(drag.start);}
 suppressWordClick=!!drag.moved;setTimeout(()=>{suppressWordClick=false;},0);
 timelineDrag=null;spanSignature='';transcriptSignature='';drawTimeline();
}
function cancelTimelineEdit(){
 const drag=timelineDrag;if(!drag)return;
 words=JSON.parse(drag.before);dirty=drag.wasDirty;$('reviewState').textContent=drag.reviewText;
 if(drag.undoAdded)undo.pop();timelineDrag=null;spanSignature='';transcriptSignature='';drawTimeline();
}
for(const id of ['timelineSheet','reviewTranscript']){
 $(id).onpointermove=updateTimelineEdit;$(id).onpointerup=endTimelineEdit;$(id).onpointercancel=cancelTimelineEdit;
 $(id).addEventListener('lostpointercapture',()=>{if(timelineDrag)cancelTimelineEdit();});
}
$('timelineSheet').addEventListener('keydown',e=>{
 const edge=e.target.closest('[data-edge]'),body=e.target.closest('[data-word]');
 if(!(edge||body)||!['ArrowLeft','ArrowRight'].includes(e.key))return;
 e.preventDefault();e.stopPropagation();wordIndex=Number(edge?edge.dataset.index:body.dataset.word);pushUndo();
 const delta=(e.key==='ArrowLeft'?-1:1)*(e.shiftKey?.01:.05);
 if(edge)moveWordEdge(wordIndex,edge.dataset.edge,words[wordIndex][edge.dataset.edge]+delta);
 else moveWholeWord(wordIndex,words[wordIndex].start_s+delta,{...words[wordIndex]});
});
// Loop a fixed playhead region, a whole word, or a window around a moving edge.
let audioLoop=null;
function audioLoopBounds(){
 if(!audioLoop||!replay||!selected?.media||!Number.isFinite(audio.duration))return null;
 const mode=$('loopTarget').value,w=words[wordIndex],width=Number($('loopLength').value);
 let start,end;
 if(mode==='word'){if(w?.start_s==null||w?.end_s==null)return null;start=w.start_s;end=w.end_s;}
 else{const center=mode==='start'?w?.start_s:mode==='end'?w?.end_s:audioLoop.anchor;if(center==null)return null;start=center-width/2;end=center+width/2;}
 start=Math.max(audioOffset+(selected.processing_window?.start_s||0),start);end=Math.min(replay.duration_s,audioOffset+audio.duration,end);
 return end-start>=.02?{start,end}:null;
}
function resetAudioLoop(){audioLoop=null;$('loopAudio').setAttribute('aria-pressed','false');$('loopRegion').hidden=true;}
function renderAudioLoop(){
 const bounds=audioLoopBounds(),region=$('loopRegion');$('audioLoopTools').hidden=!selected?.media;if(audioLoop&&!bounds){resetAudioLoop();}
 region.hidden=!bounds;if(bounds){region.style.left=bounds.start/replay.duration_s*100+'%';region.style.width=(bounds.end-bounds.start)/replay.duration_s*100+'%';region.title=`Loop ${bounds.start.toFixed(2)}–${bounds.end.toFixed(2)} seconds`;}
 $('loopLength').disabled=$('loopTarget').value==='word';
}
act('loopAudio',async()=>{
 if(audioLoop){resetAudioLoop();drawTimeline();return;}
 audioLoop={anchor:time};const bounds=audioLoopBounds();
 if(!bounds){resetAudioLoop();throw new Error('Select a timed word, or choose “At playhead” for the loop.');}
 $('loopAudio').setAttribute('aria-pressed','true');setTime(bounds.start);if(!playing)await play();drawTimeline();
});
$('loopTarget').onchange=()=>{if(audioLoop&&!audioLoopBounds()){resetAudioLoop();notice('Select a timed word to loop its boundaries.');}drawTimeline();};
$('loopLength').onchange=()=>drawTimeline();
document.querySelectorAll('[data-channel]').forEach(input=>input.onchange=()=>{channels[input.dataset.channel]=input.checked;drawTimeline();});
act('undoTiming',()=>{if(!undo.length)return;words=JSON.parse(undo.pop());$('confirmedText').value=words.map(w=>w.text).join(' ');spanSignature='';changed();renderUnplaced();});
audio.addEventListener('loadedmetadata',()=>{trackCache={};drawTimeline();});
