'use strict';
// Recording checks and annotation assistance share the actual stored sensor times.
const controlTake=t=>['rest','negative'].includes(t?.articulation);
const timedTake=t=>t?.capture_mode==='timed'||(!t?.capture_mode&&(t?.articulation==='rest'||t?.target_text==='[typing]'));
const captureLimit=t=>controlTake(t)&&!timedTake(t)?(state.source==='dca1000'?25:60):(t?.duration_s||0);
const textTokens=text=>text.trim().split(/\s+/).filter(t=>/[\p{L}\p{N}]/u.test(t));
let micReady=false,micPreparing=null,micRequest=0,checkedTake=null,timedCountdown=false,countdownCancel=false,alignmentRun=0,wordPlacement=false;
const baseSetStage=setStage,baseRenderPrompt=renderPrompt,baseFeedback=updateCaptureFeedback,baseOpenTake=openTake,baseRenderTranscript=renderTranscript;
setStage=function(value){baseSetStage(value);$('captureCheck').hidden=true;checkedTake=null;wordPlacement=false;alignmentRun++;if(native){if(value==='record'&&$('referenceAudio').checked)queueMicrotask(()=>{if(stage==='record'&&tab==='capture'&&!dictation)prepareMicrophone();});else if(!busy){micReady=false;bridge('audioCool').catch(()=>{});}}document.querySelector('main').scrollTop=0;};
async function prepareMicrophone(){if(!native||!$('referenceAudio').checked||stage!=='record'||tab!=='capture'||dictation||micPreparing)return;const run=++micRequest;micReady=false;renderInputState();micPreparing=bridge('audioPrepare');try{await micPreparing;if(stage!=='record'||tab!=='capture'||dictation){await bridge('audioCool');return;}await refreshInput();}catch(e){if(run===micRequest)notice(e.message,true);}finally{if(run===micRequest)micPreparing=null;}}
function renderInputState(info){$('inputMonitor').hidden=!native||!$('referenceAudio').checked;if(info){micReady=!!info.ready;$('inputName').textContent=info.device;$('inputMeter').value=Math.min(1,Math.sqrt(info.level||0)*2);const isolation=info.microphone_mode==='voice_isolation';$('inputState').textContent=isolation?'Voice Isolation on · use Standard':micReady?'Microphone ready':'Warming microphone…';$('inputState').classList.toggle('warning',isolation);$('microphoneModeHelp').textContent=isolation?'Voice Isolation is active. It may suppress repeated syllables. Choose Standard before recording.':'Gasp voice processing is off. macOS microphone mode: '+(info.microphone_mode||'standard').replaceAll('_',' ')+'.';}if(stage==='record'&&!busy)$('recordButton').disabled=!!pendingReference||!currentStep()||!!checkedTake||!compatible(activeSession)||!state.capture_ready||($('referenceAudio').checked&&native&&!micReady);$('captureAvailability').textContent=pendingReference?'Recover audio in microphone settings before starting the next take.':!activeSession?'':!compatible(activeSession)?'Reconnect '+settingsMessage(activeSession)+' to continue this session.':!state.capture_ready?'Waiting for fresh radar data…':'';$('captureAvailability').hidden=!$('captureAvailability').textContent;}
async function refreshInput(){if(native&&stage==='record'&&tab==='capture'&&!dictation&&$('referenceAudio').checked){const info=await bridge('audioStatus');if(stage!=='record'||tab!=='capture'||dictation)return;renderInputState(info);if(info.needs_restart&&!busy&&!micPreparing)await prepareMicrophone();}}
setInterval(()=>refreshInput().catch(()=>{}),350);
act('microphoneModes',()=>native?bridge('microphoneModes'):notice('Select Standard microphone mode in your system sound settings.'));
renderPrompt=function(){
  baseRenderPrompt();const step=currentStep();
  if(controlTake(step)){
    const timed=timedTake(step);
    if(!busy)$('recordButton').textContent=timed?`Start ${step.duration_s}-second capture`:'Hold Space to record';
    $('captureMode').textContent=step.articulation==='rest'?'BACKGROUND REFERENCE':'MOVEMENT REFERENCE';
    $('recordHelp').textContent=timed?`Press Space once. Get ready for 3 seconds, then record for ${step.duration_s} seconds. Stops automatically.`:'Hold Space. Begin after the cue; release when the movement is finished. No words to speak.';
    if(!busy){$('captureTimer').textContent=timed?durationText(step.duration_s):'00:00';$('durationHint').textContent=timed?`${step.duration_s} s baseline`:'Take your time';}
  }
  if(checkedTake)$('recordButton').disabled=true;else renderInputState();
};
updateCaptureFeedback=function(phase,elapsed,limit){
  baseFeedback(phase,elapsed,limit);
  if(timedTake(currentStep())){
    $('captureTimer').textContent=durationText(Math.max(0,limit-elapsed));
    $('durationHint').textContent=phase==='recording'?'remaining · stops automatically':`${limit} s baseline`;
    $('recordingState').textContent=phase==='recording'?'Keep going…':phase==='idle'?'Ready':({arming:'Preparing…',processing:'Saving…',complete:'Saving…',failed:'Couldn’t finish',cancelled:'Cancelled',cancelling:'Cancelling…'}[phase]||phase);
    if(phase==='recording')$('recordButton').textContent='Recording · stops automatically';
  }else if(controlTake(currentStep())){
    $('captureTimer').textContent=durationText(elapsed);
    $('durationHint').textContent=phase==='recording'?(limit-elapsed<=10?`${Math.ceil(limit-elapsed)} s to capture limit`:'Release when finished'):'Take your time';
    $('takeProgress').style.width='0%';
  }
};
function canStartCapture(){return !pendingReference&&!busy&&!connecting&&!checkedTake&&!dictation&&tab==='capture'&&stage==='record'&&!!currentStep()&&compatible(activeSession)&&state.capture_ready&&!document.querySelector('dialog[open]');}
async function beginTimedTake(){if(!canStartCapture())return;if(native&&$('referenceAudio').checked&&!micReady){notice('Wait for the microphone input meter.');return;}timedCountdown=true;countdownCancel=false;busy=true;setBusyControls(true);$('cancelButton').hidden=false;$('recordButton').disabled=true;try{for(let n=3;n>0;n--){$('recordingState').textContent='Get ready';$('captureTimer').textContent=String(n);$('durationHint').textContent='starts in';await sleep(1000);if(countdownCancel)return;}}finally{timedCountdown=false;busy=false;setBusyControls(false);renderPrompt();}if(!countdownCancel){hold=false;if(!canStartCapture()){notice('Radar data is unavailable. Reconnect, then start this step again.',true);return;}await toggleRecording();}}
const originalBeginHold=beginHold;
beginHold=function(){if(!canStartCapture())return;if(timedTake(currentStep())){beginTimedTake().catch(e=>notice(e.message,true));return;}if(checkedTake||native&&$('referenceAudio').checked&&!micReady)return;originalBeginHold();};
recordButton.onpointerdown=e=>{if(timedTake(currentStep()))return;if(activeSession?.collection?.plan.task!=='reading'&&stage==='record'){e.preventDefault();recordButton.setPointerCapture(e.pointerId);beginHold();}};
recordButton.onclick=e=>{if(e.detail===0&&activeSession?.collection?.plan.task!=='reading'&&!timedTake(currentStep()))return;if(timedTake(currentStep()))beginTimedTake().catch(e=>notice(e.message,true));else if(activeSession?.collection?.plan.task==='reading')toggleRecording().catch(e=>notice(e.message,true));};
act('cancelButton',()=>{if(timedCountdown){countdownCancel=true;return;}return activeRecord&&api('record/'+activeRecord.id+'/cancel','POST');});
const baseAfterCapture=afterCapture;
afterCapture=async function(){const take=trials.at(-1);if(!take)return;const quality=await api(`sessions/${take.session_id}/trials/${take.id}/quality`);if(quality.warnings.some(w=>w.requires_action!==false)){const recoverable=quality.warnings.some(w=>w.code==='missing_audio')&&(native||!!pendingReference);$('recoverCheckedAudio').hidden=!recoverable;$('retryCheckedTake').classList.toggle('primary',!recoverable);checkedTake=take;stepOverride=take.plan_step_id;renderPrompt();const gap=quality.radar_gaps?.[0];$('captureCheckMessage').textContent=quality.warnings.map(w=>w.message).join(' ')+(gap?` Gap ${quality.radar_gaps.length>1?'first seen ':''}between ${gap.start_s.toFixed(2)} and ${gap.end_s.toFixed(2)} s. Open review to inspect it on the timeline.`:'');$('captureCheck').hidden=false;$('recordButton').disabled=true;return;}if(quality.warnings.length)showSavedToast(take,'Saved for review · '+quality.warnings.map(w=>w.message).join(' '));await baseAfterCapture();};
act('recoverCheckedAudio',async()=>{$('recoverCheckedAudio').disabled=true;try{await recoverReferenceAudio();checkedTake=null;stepOverride=null;$('captureCheck').hidden=true;await afterCapture();if(stage==='record')renderPrompt();}finally{$('recoverCheckedAudio').disabled=false;}});
act('retryCheckedTake',async()=>{if(!checkedTake)return;const take=checkedTake;await api(`sessions/${take.session_id}/trials/${take.id}`,'PATCH',{accepted:false,base_revision:take.annotation_revision||0});trials=await api('sessions/'+take.session_id+'/trials');checkedTake=null;stepOverride=take.plan_step_id;$('captureCheck').hidden=true;renderPrompt();});
act('reviewCheckedTake',()=>checkedTake&&reviewCapturedTake(checkedTake));
act('continueCheckedTake',()=>{checkedTake=null;stepOverride=null;$('captureCheck').hidden=true;renderPrompt();return baseAfterCapture();});
renderTranscript=function(){if(controlTake(selected)){$('reviewTranscript').textContent=selected.prompt_text||selected.label;return;}baseRenderTranscript();};
function setReviewKind(){alignmentPending=false;resetAudioLoop();$('retryTiming').hidden=true;$('timingAssistance').hidden=true;$('timingAssistance').open=false;$('suggestWords').disabled=!selected.media||controlTake(selected)||selected.articulation==='silent';const control=controlTake(selected);$('retryTiming').hidden=!selected.media||control||selected.articulation==='silent';const audioTrack=document.querySelector('[data-channel="audio"]');audioTrack.disabled=!selected.media;audioTrack.closest('label').hidden=!selected.media;channels.audio=!!selected.media&&audioTrack.checked;$('recordingBadge').textContent=`${control?(selected.articulation==='rest'?'Background reference':'Movement reference'):selected.articulation==='silent'?'Silent speech':'Aloud speech'} · ${selected.review_status||'pending'}${selected.synthetic?' · SIMULATOR':''}`;$('timelineNote').textContent=selected.media?'Audio + radar · shared host-clock estimate':'Radar · no reference audio';$('referenceHeading').textContent=control?'ACTION REFERENCE':selected.articulation==='silent'?'SILENT SPEECH REFERENCE':'SPEECH REFERENCE';document.querySelector('.transcript-panel').classList.toggle('control',control);for(const id of ['annotationToolbar','reviewedTextField','speechTools','transcriptEditor'])$(id).hidden=control;document.querySelector('[data-channel="words"]').closest('label').hidden=control;channels.words=!control&&document.querySelector('[data-channel="words"]').checked;$('trimStartLabel').textContent=control?'Action start (s)':'Speech start (s)';$('trimEndLabel').textContent=control?'Action end (s)':'Speech end (s)';$('timelineKeys').textContent=control?'Space play · ← → step':selected.media?'Space play · Drag words to move · Drag edges to trim · Double-click a word to seek':'Space play · Drag word edges · [ ] mark boundaries';if(!control&&!selected.media)$('reviewTimingHint').textContent='No reference audio. Confirm the transcript; word timing is optional.';if(control){words=[];$('confirmedText').value='';$('reviewTimingHint').textContent='Review the action and signal. No transcript needed.';}renderTranscript();drawTimeline();timingAction();}
openTake=async function(sid,tid){
  await baseOpenTake(sid,tid);if(selected?.id!==tid||stage!=='replay'||tab!=='capture'||dictation)return;
  words=controlTake(selected)?[]:words.filter(w=>textTokens(w.text).length);wordIndex=-1;wordPlacement=false;transcriptSignature='';setReviewKind();
  const quality=await api(`sessions/${sid}/trials/${tid}/quality`);if(selected?.id!==tid||stage!=='replay'||tab!=='capture'||dictation)return;
  $('qualitySummary').hidden=!quality.warnings.length;
  $('qualitySummary').innerHTML=quality.warnings.map(w=>`<p>${w.code==='radar_gap'?'<i class="gap-key"></i>':''}${esc(w.message)}</p>`).join('');
  if(quality.radar_gaps?.length){
    const gaps=quality.radar_gaps;
    $('qualitySummary').insertAdjacentHTML('beforeend',`<p>Red markers locate gaps on the ruler; shaded bands bracket them on radar tracks.</p><div class="gap-actions">${gaps.slice(0,8).map((g,i)=>`<button type="button" data-gap="${i}">Show gap · ${g.start_s.toFixed(2)}–${g.end_s.toFixed(2)} s</button>`).join('')}${gaps.length>8?`<span>${gaps.length-8} more on the timeline</span>`:''}</div>`);
    $('qualitySummary').querySelectorAll('[data-gap]').forEach(button=>button.onclick=()=>{pause();setTime(gaps[Number(button.dataset.gap)].start_s);followTimeline();requestFrame(true);$('timeline').focus();});
  }
  selected.processing_window=quality.processing_window;
  const cutoff=Math.max(0,(quality.processing_window?.start_s||0)+audioOffset);
  if(quality.processing_window?.start_s){
    $('timelineNote').textContent='Shaded audio = start cue excluded from processing · original audio retained'+(quality.processing_window.source==='legacy_pop_estimate'?' · older cue timing estimated':'');
    trackCache={};if(!playing&&time===0&&wordIndex<0)setTime(cutoff);
  }
  // Repair unverified machine drafts that labeled the old start sound as a word.
  // Human-edited or verified annotations are never replaced automatically.
  const cueDraft=!selected.accepted&&words.some(w=>w.source==='acoustic_estimate'&&w.start_s!=null&&w.start_s<cutoff)&&!words.some(w=>w.start_s!=null&&!['acoustic_estimate','speech_estimate'].includes(w.source));
  if(cueDraft){pushUndo();words=words.map(w=>({...w,start_s:null,end_s:null}));changed();renderTranscript();}
  if(!selected.accepted&&!controlTake(selected)&&selected.articulation!=='silent'&&selected.media&&words.some(w=>w.start_s==null||w.end_s==null)){
    suggestTiming(true);
  }
};
let alignmentPending=false;
function timingAction(){
  const missing=words.some(w=>w.start_s==null||w.end_s==null),allowed=!!selected?.media&&!controlTake(selected)&&selected.articulation!=='silent';
  $('retryTiming').hidden=!allowed||(!missing&&!alignmentPending);
  $('retryTiming').disabled=alignmentPending;
  $('retryTiming').setAttribute('aria-busy',String(alignmentPending));
  $('retryTiming').textContent=alignmentPending?'Placing words…':'Auto-place missing words';
  $('suggestWords').disabled=!allowed||alignmentPending||!missing;
}
function timingUnavailable(syllables,error=''){
  $('reviewTimingHint').textContent=syllables
    ? 'These sounds could not be separated reliably. Listen and confirm the take; individual sound timings are optional.'
    : error||'Words could not be placed. Check the reference audio and transcript, then retry.';
  $('timingAssistance').hidden=false;
  $('timingAssistanceDetail').textContent=syllables
    ? 'Gasp uses recorded sound bursts for syllable exercises. It leaves uncertain boundaries unplaced. Select a sound and drag across the waveform to add its timing.'
    : 'Gasp aligns the supplied English transcript to the recorded audio locally. It excludes the start cue and preserves your edits. No Siri or Dictation permission is needed. Suggestions remain drafts until you review them.';
}
async function suggestTiming(automatic=false){
  if(!selected?.media||controlTake(selected)||selected.articulation==='silent')return;
  if(automatic&&(selected.accepted||!words.some(w=>w.start_s==null||w.end_s==null)))return;
  const run=++alignmentRun,take=selected,reference=$('confirmedText').value,offset=audioOffset,revisionAtStart=JSON.stringify(words);
  const current=()=>run===alignmentRun&&selected?.id===take.id&&stage==='replay'&&tab==='capture'&&!dictation&&(!automatic||!selected.accepted)&&offset===audioOffset&&reference===$('confirmedText').value&&revisionAtStart===JSON.stringify(words);
  alignmentPending=true;timingAction();$('timingAssistance').hidden=true;
  $('reviewTimingHint').textContent='Placing words from the reference audio…';
  let syllables=false;
  try{
    const response=await api(`sessions/${take.session_id}/trials/${take.id}/suggest-timing`,'POST',{text:reference,audio_offset_s:offset});
    if(!current())return;
    syllables=response.kind==='syllables';
    if(response.placed){
      pushUndo();words=mergeTimingSuggestions(words,response.words);wordIndex=-1;wordPlacement=false;
      changed();renderTranscript();updateWordLabel();
      const placed=words.filter(w=>w.start_s!=null&&w.end_s!=null).length;
      $('reviewTimingHint').textContent=`${placed} of ${words.length} ${syllables?'sounds':'words'} placed · ${response.message}`+(placed<words.length?' Some suggestions conflict with existing boundaries; those words were left unchanged.':'');
    }else timingUnavailable(syllables,response.message);
  }catch(e){if(current())timingUnavailable(syllables,e.message);}
  finally{if(run===alignmentRun){alignmentPending=false;timingAction();if(selected?.id===take.id&&stage==='replay'&&$('reviewTimingHint').textContent==='Placing words from the reference audio…')$('reviewTimingHint').textContent='Your edits are preserved. Auto-place can fill any remaining words.';}}
}
// Retrying fills only empty intervals; human edits and existing drafts survive.
function mergeTimingSuggestions(existing,suggested){
 const result=existing.map(w=>({...w}));
 for(let i=0;i<result.length;i++){
  if(result[i].start_s!=null||result[i].end_s!=null)continue;
  const w=suggested[i];if(!w||w.text!==result[i].text||w.start_s==null||w.end_s==null)continue;
  const {start:lo,end:hi}=wordLimits(i,result);
  if(w.start_s>=lo&&w.end_s<=hi&&w.end_s>w.start_s)result[i]={...w};
 }
 return result;
}
act('suggestWords',()=>suggestTiming(false));
act('retryTiming',()=>suggestTiming(false));
updateWordLabel=function(){const w=words[wordIndex],control=controlTake(selected);for(const id of ['setWordStart','setWordEnd','clearWordTime'])$(id).disabled=!w||control;$('setWordEnd').disabled=!w||w.start_s==null;$('setWordStart').classList.toggle('armed',!!w&&w.start_s!=null&&w.end_s==null);$('setWordStart').textContent=w?.start_s!=null?`[ Start ${w.start_s.toFixed(2)} s`:'[ Mark start';$('setWordEnd').textContent=w?.end_s!=null?`] End ${w.end_s.toFixed(2)} s`:'] Mark end';$('selectedWordLabel').textContent=!w?(selected?.media?'Drag a word into Audio or Words, or select it and draw its span.':'Optional timing: select a word, then mark its start and end at the playhead.'):w.start_s==null?(selected?.media?`“${w.text}” selected · drag its span in Audio or Words, or drag this word into the timeline.`:`“${w.text}” selected · move the playhead, then press [ to mark its start.`):w.end_s==null?`“${w.text}” starts at ${w.start_s.toFixed(2)} s · move to its end, then press ].`:`“${w.text}” · ${w.start_s.toFixed(2)}–${w.end_s.toFixed(2)} s${w.source==='manual'?'':' · suggested'} · drag to move · drag edges to trim.`;timingAction();};
function wordLimits(i,items=words){return{start:items.slice(0,i).map(w=>w.end_s??w.start_s).filter(t=>t!=null).at(-1)??0,end:items.slice(i+1).map(w=>w.start_s??w.end_s).find(t=>t!=null)??replay.duration_s};}
const baseTranscriptChanged=transcriptChanged;
transcriptChanged=function(){if(controlTake(selected)){words=[];$('confirmedText').value='';return;}baseTranscriptChanged();words=words.filter(w=>textTokens(w.text).length);};
const baseAudioChange=$('referenceAudio').onchange;
$('referenceAudio').onchange=async()=>{await baseAudioChange();if(native&&stage==='record'){if($('referenceAudio').checked)await prepareMicrophone();else{micReady=false;await bridge('audioCool');renderInputState();}}};
const baseShowTab=showTab;
showTab=function(value){baseShowTab(value);if(!native||busy)return;if(value==='capture'&&stage==='record'&&$('referenceAudio').checked)queueMicrotask(()=>{if(stage==='record'&&tab==='capture'&&!dictation)prepareMicrophone();});else{micReady=false;bridge('audioCool').catch(()=>{});}};
const baseDictationClick=$('dictationWorkspace').onclick;
$('dictationWorkspace').onclick=async e=>{await baseDictationClick(e);if(native&&!busy&&dictation){micReady=false;bridge('audioCool').catch(()=>{});}};

$('frameInspector').addEventListener('toggle',()=>{if($('frameInspector').open){drawRadar();requestFrame(true);}});
