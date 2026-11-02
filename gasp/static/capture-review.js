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
function renderInputState(info){$('inputMonitor').hidden=!native||!$('referenceAudio').checked;if(info){micReady=!!info.ready;$('inputName').textContent=info.device;$('inputMeter').value=Math.min(1,Math.sqrt(info.level||0)*2);const isolation=info.microphone_mode==='voice_isolation';$('inputState').textContent=isolation?'Voice Isolation on · use Standard':micReady?'Microphone ready':'Warming microphone…';$('inputState').classList.toggle('warning',isolation);$('microphoneModeHelp').textContent=isolation?'Voice Isolation is active. It may suppress repeated syllables. Choose Standard before recording.':'Gasp voice processing is off. macOS microphone mode: '+(info.microphone_mode||'standard').replaceAll('_',' ')+'.';}if(stage==='record'&&!busy)$('recordButton').disabled=!currentStep()||!!checkedTake||($('referenceAudio').checked&&native&&!micReady);}
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
async function beginTimedTake(){if(busy||checkedTake)return;if(native&&$('referenceAudio').checked&&!micReady){notice('Wait for the microphone input meter.');return;}timedCountdown=true;countdownCancel=false;busy=true;setBusyControls(true);$('cancelButton').hidden=false;$('recordButton').disabled=true;try{for(let n=3;n>0;n--){$('recordingState').textContent='Get ready';$('captureTimer').textContent=String(n);$('durationHint').textContent='starts in';await sleep(1000);if(countdownCancel)return;}}finally{timedCountdown=false;busy=false;setBusyControls(false);if(countdownCancel)renderPrompt();}if(!countdownCancel){hold=false;await toggleRecording();}}
const originalBeginHold=beginHold;
beginHold=function(){if(timedTake(currentStep())){beginTimedTake().catch(e=>notice(e.message,true));return;}if(checkedTake||native&&$('referenceAudio').checked&&!micReady)return;originalBeginHold();};
recordButton.onpointerdown=e=>{if(timedTake(currentStep()))return;if(activeSession?.collection?.plan.task!=='reading'&&stage==='record'){e.preventDefault();recordButton.setPointerCapture(e.pointerId);beginHold();}};
recordButton.onclick=()=>{if(timedTake(currentStep()))beginTimedTake().catch(e=>notice(e.message,true));else if(activeSession?.collection?.plan.task==='reading')toggleRecording().catch(e=>notice(e.message,true));};
act('cancelButton',()=>{if(timedCountdown){countdownCancel=true;return;}return activeRecord&&api('record/'+activeRecord.id+'/cancel','POST');});
const baseAfterCapture=afterCapture;
afterCapture=async function(){const take=trials.at(-1);if(!take)return;const quality=await api(`sessions/${take.session_id}/trials/${take.id}/quality`);if(quality.warnings.length){checkedTake=take;stepOverride=take.plan_step_id;renderPrompt();$('captureCheckMessage').textContent=quality.warnings.map(w=>w.message).join(' ');$('captureCheck').hidden=false;$('recordButton').disabled=true;return;}await baseAfterCapture();};
act('retryCheckedTake',async()=>{if(!checkedTake)return;const take=checkedTake;await api(`sessions/${take.session_id}/trials/${take.id}`,'PATCH',{accepted:false,base_revision:take.annotation_revision||0});trials=await api('sessions/'+take.session_id+'/trials');checkedTake=null;stepOverride=take.plan_step_id;$('captureCheck').hidden=true;renderPrompt();});
act('reviewCheckedTake',()=>checkedTake&&reviewCapturedTake(checkedTake));
act('continueCheckedTake',()=>{checkedTake=null;stepOverride=null;$('captureCheck').hidden=true;renderPrompt();return baseAfterCapture();});
renderTranscript=function(){if(controlTake(selected)){$('reviewTranscript').textContent=selected.prompt_text||selected.label;return;}baseRenderTranscript();};
function setReviewKind(){const control=controlTake(selected);const audioTrack=document.querySelector('[data-channel="audio"]');audioTrack.disabled=!selected.media;audioTrack.closest('label').hidden=!selected.media;channels.audio=!!selected.media&&audioTrack.checked;$('recordingBadge').textContent=`${control?(selected.articulation==='rest'?'Background reference':'Movement reference'):selected.articulation==='silent'?'Silent speech':'Aloud speech'} · ${selected.review_status||'pending'}${selected.synthetic?' · SIMULATOR':''}`;$('timelineNote').textContent=selected.media?'Audio + radar · shared host-clock estimate':'Radar · no reference audio';$('referenceHeading').textContent=control?'ACTION REFERENCE':selected.articulation==='silent'?'SILENT SPEECH REFERENCE':'SPEECH REFERENCE';document.querySelector('.transcript-panel').classList.toggle('control',control);for(const id of ['annotationToolbar','reviewedTextField','speechTools','transcriptEditor'])$(id).hidden=control;document.querySelector('[data-channel="words"]').closest('label').hidden=control;channels.words=!control&&document.querySelector('[data-channel="words"]').checked;$('trimStartLabel').textContent=control?'Action start (s)':'Speech start (s)';$('trimEndLabel').textContent=control?'Action end (s)':'Speech end (s)';$('timelineKeys').textContent=control?'Space play · ← → step':selected.media?'Space play · Drag word edges · Drag the waveform to place a word':'Space play · Drag word edges · [ ] mark boundaries';if(!control&&!selected.media)$('reviewTimingHint').textContent='No reference audio. Confirm the transcript; word timing is optional.';if(control){words=[];$('confirmedText').value='';$('reviewTimingHint').textContent='Review the action and signal. No transcript needed.';}renderTranscript();drawTimeline();}
openTake=async function(sid,tid){
  await baseOpenTake(sid,tid);if(selected?.id!==tid)return;
  words=controlTake(selected)?[]:words.filter(w=>textTokens(w.text).length);wordIndex=-1;wordPlacement=false;transcriptSignature='';setReviewKind();
  const quality=await api(`sessions/${sid}/trials/${tid}/quality`);if(selected?.id!==tid)return;
  $('qualitySummary').hidden=!quality.warnings.length;
  $('qualitySummary').innerHTML=quality.warnings.map(w=>`<p>${w.code==='radar_gap'?'<i class="gap-key"></i>':''}${esc(w.message)}</p>`).join('');
  selected.processing_window=quality.processing_window;
  const cutoff=Math.max(0,(quality.processing_window?.start_s||0)+audioOffset);
  if(quality.processing_window?.start_s){
    $('timelineNote').textContent='Shaded audio = start cue excluded from processing · original audio retained'+(quality.processing_window.source==='legacy_pop_estimate'?' · older cue timing estimated':'');
    trackCache={};setTime(cutoff);
  }
  // Repair unverified machine drafts that labeled the old start sound as a word.
  // Human-edited or verified annotations are never replaced automatically.
  const cueDraft=!selected.accepted&&words.some(w=>w.source==='acoustic_estimate'&&w.start_s!=null&&w.start_s<cutoff)&&!words.some(w=>w.start_s!=null&&!['acoustic_estimate','speech_estimate'].includes(w.source));
  if(cueDraft){pushUndo();words=words.map(w=>({...w,start_s:null,end_s:null}));changed();renderTranscript();}
  if(!controlTake(selected)&&selected.articulation!=='silent'&&selected.media&&!words.some(w=>w.start_s!=null)){
    suggestTiming(true).catch(e=>{if(selected?.id!==tid)return;$('reviewTimingHint').textContent='Automatic timing unavailable: '+e.message+'. Select a word and drag across its sound to place it.';});
  }
};
async function suggestTiming(automatic=false){if(!selected?.media||controlTake(selected)||selected.articulation==='silent')return;const run=++alignmentRun,take=selected,reference=$('confirmedText').value,revisionAtStart=JSON.stringify(words);$('suggestWords').disabled=true;$('reviewTimingHint').textContent='Finding word boundaries in the reference audio…';try{let recognized=[],error='';const phonetic=(take.prompt_text||'').includes('·');let response=await api(`sessions/${take.session_id}/trials/${take.id}/suggest-timing`,'POST',{text:reference,audio_offset_s:audioOffset});if(!response.placed&&native){try{const result=await bridge('speechAlign',{sid:take.session_id,tid:take.id});recognized=result.words;if(selected?.id===take.id)selected.asr_raw_text=result.text;}catch(e){error=e.message;}response=await api(`sessions/${take.session_id}/trials/${take.id}/suggest-timing`,'POST',{text:reference,recognized,audio_offset_s:audioOffset});}if(run!==alignmentRun||selected?.id!==take.id||reference!==$('confirmedText').value||revisionAtStart!==JSON.stringify(words))return;if(response.placed){pushUndo();words=response.words;wordIndex=-1;wordPlacement=false;changed();renderTranscript();$('reviewTimingHint').textContent=`${response.placed} of ${words.length} ${phonetic?'sounds':'words'} placed · ${response.message}`;}else{$('reviewTimingHint').textContent=error?`Automatic timing unavailable: ${error}. Select a word, then drag across its sound on the waveform.`:'No reliable word matches. Select a word, then drag across its sound on the waveform. Timing is optional; never label sounds that are missing.';}}finally{if(selected?.id===take.id)$('suggestWords').disabled=!selected.media;}}
act('suggestWords',()=>suggestTiming(false));
updateWordLabel=function(){const w=words[wordIndex],control=controlTake(selected);for(const id of ['setWordStart','setWordEnd','clearWordTime'])$(id).disabled=!w||control;$('setWordEnd').disabled=!w||w.start_s==null;$('setWordStart').classList.toggle('armed',!!w&&w.start_s!=null&&w.end_s==null);$('setWordStart').textContent=w?.start_s!=null?`[ Start ${w.start_s.toFixed(2)} s`:'[ Mark start';$('setWordEnd').textContent=w?.end_s!=null?`] End ${w.end_s.toFixed(2)} s`:'] Mark end';$('selectedWordLabel').textContent=!w?(selected?.media?'Select a word, then drag across its sound on the waveform.':'Optional timing: select a word, then mark its start and end at the playhead.'):w.start_s==null?(selected?.media?`“${w.text}” selected · drag its start → end on the waveform.`:`“${w.text}” selected · move the playhead, then press [ to mark its start.`):w.end_s==null?`“${w.text}” starts at ${w.start_s.toFixed(2)} s · move to its end, then press ].`:`“${w.text}” · ${w.start_s.toFixed(2)}–${w.end_s.toFixed(2)} s${w.source==='manual'?'':' · suggested'} · drag either edge to adjust.`;};
function wordLimits(i){return{start:words.slice(0,i).filter(w=>w.end_s!=null).at(-1)?.end_s||0,end:words.slice(i+1).find(w=>w.start_s!=null)?.start_s??replay.duration_s};}
setEdge=function(edge){if(!replay||!words[wordIndex])return;const w=words[wordIndex],bounds=wordLimits(wordIndex),t=Math.max(bounds.start,Math.min(bounds.end,time));if(edge==='end_s'&&(w.start_s==null||t<=w.start_s))throw new Error('Place the end after the marked start.');if(edge==='start_s'&&t>=bounds.end)throw new Error('Place the start before the next word.');pushUndo();w[edge]=t;if(edge==='start_s'&&w.end_s!=null&&w.end_s<=t)w.end_s=null;w.source='manual';wordPlacement=w.end_s==null;changed();spanSignature='';renderTranscript();updateWordLabel();};
const baseTranscriptChanged=transcriptChanged;
transcriptChanged=function(){if(controlTake(selected)){words=[];$('confirmedText').value='';return;}baseTranscriptChanged();words=words.filter(w=>textTokens(w.text).length);};
const baseAudioChange=$('referenceAudio').onchange;
$('referenceAudio').onchange=async()=>{await baseAudioChange();if(native&&stage==='record'){if($('referenceAudio').checked)await prepareMicrophone();else{micReady=false;await bridge('audioCool');renderInputState();}}};
const baseShowTab=showTab;
showTab=function(value){baseShowTab(value);if(!native||busy)return;if(value==='capture'&&stage==='record'&&$('referenceAudio').checked)queueMicrotask(()=>{if(stage==='record'&&tab==='capture'&&!dictation)prepareMicrophone();});else{micReady=false;bridge('audioCool').catch(()=>{});}};
const baseDictationClick=$('dictationWorkspace').onclick;
$('dictationWorkspace').onclick=()=>{baseDictationClick();if(native&&!busy){micReady=false;bridge('audioCool').catch(()=>{});}};

$('frameInspector').addEventListener('toggle',()=>{if($('frameInspector').open){drawRadar();requestFrame(true);}});
