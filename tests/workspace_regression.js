// Runs only in the isolated preview harness. Never mount this in the installed app.
document.getElementById('audit').onclick=async()=>{
 const button=document.getElementById('audit'),out=document.getElementById('result');button.disabled=true;
 const auditFrame=document.getElementById('workspace');auditFrame.src='/training?audit='+Date.now();await new Promise(r=>auditFrame.addEventListener('load',r,{once:true}));
 const w=auditFrame.contentWindow,d=w.document,original=w.fetch.bind(w),passed=[];
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const wait=async(fn,message)=>{const end=Date.now()+20000;while(!fn()){if(Date.now()>end)throw Error(message);await sleep(25);}};
 const assert=(ok,message)=>{if(!ok)throw Error(message);passed.push(message);out.textContent=`Passed ${passed.length}: ${message}`;};
 const click=s=>{const e=d.querySelector(s);if(!e)throw Error('Missing control '+s);e.click();};
 const request=async(path,method='GET',body)=>{const r=await original('/api/'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw Error(await r.text());return r.json();};
 const home=async()=>{click('[data-tab="capture"]');await wait(()=>!d.getElementById('captureWelcome').hidden,'Capture did not return home');};
 const training=async()=>{click('[data-tab="train"]');await wait(()=>!d.getElementById('trainingPage').hidden&&!!d.querySelector('[data-learn="dataset"]'),'Training did not open');};
 const openTake=async(t)=>{if(d.getElementById('captureLayout').classList.contains('collapsed'))click('#toggleLibrary');d.querySelectorAll('#recordingList details').forEach(e=>e.open=true);click(`[data-tid="${t.id}"]`);await wait(()=>d.getElementById('confirmedText').value===(t.confirmed_text||t.label)&&!d.getElementById('replayStage').hidden,'Recording did not open');};
 const note=value=>{const e=d.getElementById('reviewNotes');e.value=value;e.dispatchEvent(new w.Event('input',{bubbles:true}));};
 let release=null;
 const delay=(path,method='GET')=>{let seen=false;w.fetch=async(url,opts={})=>{const response=await original(url,opts);if(!seen&&String(url)===path&&(opts.method||'GET')===method){seen=true;await new Promise(r=>release=r);}return response;};return()=>seen;};
 try{
  await wait(()=>!!d.querySelector('#journeyHome [data-collection]'),'Workspace did not load');
  await request('disconnect','POST');await wait(()=>d.getElementById('connectionText').textContent.match(/^Radar (disconnected|USB detected)$/),'Fixture did not disconnect');
  const rect=()=>{const r=d.querySelector('.connection').getBoundingClientRect();return [r.x,r.y,r.width,r.height].join(',');},before=rect();
  click('#dictationWorkspace');await wait(()=>!d.getElementById('dictationPage').hidden,'Dictation did not open');
  assert(rect()===before,'Radar control stays anchored across workspaces');click('#radarWorkspace');
  click('#journeyHome [data-collection]');await wait(()=>!d.getElementById('collectionDetail').hidden,'Collection did not open');await home();
  assert(d.getElementById('sceneHome').hidden&&d.getElementById('sceneBreadcrumb').hidden,'Overview has no dead Capture breadcrumb');
  const card=d.querySelector('#journeyHome [data-collection]'),collectionDelayed=delay('/api/collections/'+card.dataset.collection);card.click();await wait(collectionDelayed,'Collection request missing');await home();release();release=null;w.fetch=original;await sleep(100);
  assert(!d.getElementById('captureWelcome').hidden,'A late collection response cannot reopen a dismissed page');
  click('#connectionStatus');click('#togglePreview');
  assert(!!d.querySelector('#settingsDialog .dialog-notice[role="alert"]'),'Settings failures appear inside the dialog');
  click('[data-settings="setup"]');const subject=d.getElementById('subject'),oldSubject=subject.value;subject.value='Unsaved synthetic setup';subject.dispatchEvent(new w.Event('input',{bubbles:true}));
  click('[data-settings="radar"]');click('[data-settings="setup"]');assert(subject.value==='Unsaved synthetic setup','Settings tabs preserve unsaved setup fields');
  click('#closeSettings');click('#settingsButton');assert(subject.value==='Unsaved synthetic setup','Closing and reopening Settings retains its draft');click('#discardSetupDraft');assert(subject.value===oldSubject,'Discard setup explicitly restores saved values');click('#closeSettings');
  const takes=(await request('recordings')).filter(t=>t.articulation==='silent'),first=takes[0],second=takes.find(t=>(t.confirmed_text||t.label)!==(first.confirmed_text||first.label));
  if(!second)throw Error('Need two distinct synthetic phrases');
  const delayed=delay(`/api/sessions/${first.session_id}/trials/${first.id}`);
  if(d.getElementById('captureLayout').classList.contains('collapsed'))click('#toggleLibrary');d.querySelectorAll('#recordingList details').forEach(e=>e.open=true);
  click(`[data-tid="${first.id}"]`);await wait(delayed,'First take request missing');await openTake(second);release();release=null;await sleep(100);w.fetch=original;
  assert(d.getElementById('confirmedText').value===(second.confirmed_text||second.label),'A late recording response cannot replace the selected take');
  const takePath=`sessions/${second.session_id}/trials/${second.id}`,savedFirst=delay('/api/'+takePath,'PATCH');
  note('First synthetic draft');click('#saveAnnotations');await wait(savedFirst,'Draft save did not start');
  note('Newer synthetic edit');click('[data-tab="capture"]');release();release=null;w.fetch=original;
  await wait(()=>!d.getElementById('captureWelcome').hidden,'Draft navigation did not finish');
  assert((await request(takePath)).notes==='Newer synthetic edit','Edits made during a save are persisted before navigation');
  await openTake(second);note('Synthetic quit draft');await w.gaspPrepareToQuit();
  assert((await request(takePath)).notes==='Synthetic quit draft','Quit preflight saves the open review draft');
  // Mark an interval through the actual keyboard handler, then exercise its real button.
  click('#reviewTranscript [data-transcript="0"]');d.getElementById('timeline').focus();
  for(const key of ['[','ArrowRight','ArrowRight',']'])d.getElementById('timeline').dispatchEvent(new w.KeyboardEvent('keydown',{key,bubbles:true}));
  await wait(()=>!!d.querySelector('#wordSpans [data-word="0"]'),'Word span was not placed');
  const edge=d.querySelector('#wordSpans [data-edge="end_s"]');edge.focus();edge.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));await sleep(50);
  assert(d.activeElement===edge,'Keyboard boundary edits retain focus');
  click('#stepForward');const retainedTime=d.getElementById('timeline').getAttribute('aria-valuenow');click('#wordSpans [data-word="0"]');
  assert(d.getElementById('timeline').getAttribute('aria-valuenow')===retainedTime,'Timeline word selection preserves the playhead');
  const gapTake=(await request('recordings')).find(t=>t.label==='Synthetic gap review');
  await openTake(gapTake);await wait(()=>!!d.querySelector('#qualitySummary [data-gap]'),'Gap review controls did not load');
  assert(d.getElementById('qualitySummary').textContent.includes('50 ms'),'Gap review explains the size of the missing data');
  for(const name of ['phase','range'])click(`[data-channel="${name}"]`);
  const gapCanvas=d.getElementById('timeline'),gapCtx=gapCanvas.getContext('2d');
  const pixel=gapCtx.getImageData(Math.round(2/6*gapCanvas.width),Math.round(28*gapCanvas.height/parseFloat(gapCanvas.style.height)),1,1).data;
  assert(pixel[0]>pixel[1]*2&&pixel[0]>pixel[2]*2,'Gap ruler remains visible with radar tracks hidden');
  click('#qualitySummary [data-gap="0"]');
  assert(Math.abs(Number(d.getElementById('timeline').getAttribute('aria-valuenow'))-1.95)<.001,'Show gap seeks the shared playhead to the actual missing-frame interval');
  for(const name of ['phase','range'])click(`[data-channel="${name}"]`);
  await home();await training();
  const inspectDelayed=delay('/api/learning/inspect','POST');click('[data-learn="dataset"]');await wait(inspectDelayed,'Dataset request missing');
  click('[data-learn="curriculum"]');release();release=null;await sleep(100);w.fetch=original;
  assert(d.getElementById('learningWorkspace').textContent.includes('One useful session at a time.'),'A late dataset response cannot replace Curriculum');
  await home();click('#connectionStatus');
  w.fetch=(url,opts={})=>String(url)==='/api/connect'?Promise.resolve(new w.Response(JSON.stringify({detail:'Synthetic connection failure'}),{status:400,headers:{'Content-Type':'application/json'}})):original(url,opts);
  click('#connectButton');await wait(()=>d.querySelector('.dialog-notice')?.textContent.includes('Synthetic connection failure'),'Connect error was not visible');
  assert(!d.getElementById('connectButton').disabled&&!d.getElementById('source').disabled,'Failed connection restores usable settings controls');w.fetch=original;click('#closeSettings');
  w.fetch=(url,opts)=>String(url)==='/api/live'?Promise.reject(Error('Synthetic offline')):original(url,opts);
  await wait(()=>d.getElementById('connectionText').textContent==='Engine unavailable','Offline status stayed stale');
  assert(d.getElementById('connectionText').textContent==='Engine unavailable','Lost backend connectivity is not shown as a connected radar');w.fetch=original;
  await wait(()=>d.getElementById('connectionText').textContent.match(/^Radar (disconnected|USB detected)$/),'Status did not recover');
  // Enter a real synthetic calibration, then check shortcuts from a different screen and a modal.
  click('#journeyHome [data-collection]');await wait(()=>!d.getElementById('collectionDetail').hidden,'Calibration did not open');if(d.getElementById('startFreshSession')){d.querySelector('#collectionDetail .collection-menu').open=true;click('#startFreshSession');}else click('#startCollection');await wait(()=>!d.getElementById('captureSetup').hidden,'Setup did not open');
  await request('connect','POST',{source:'simulator',profile:'usb-phase-20hz'});await wait(()=>!d.getElementById('setupNext').disabled,'Simulator did not become ready');
  click('#setupNext');await wait(()=>!d.getElementById('recordStage').hidden,'Recorder did not open');await training();
  const timer=d.getElementById('captureTimer').textContent;w.dispatchEvent(new w.Event('gasp-toggle'));await sleep(100);
  assert(d.getElementById('captureTimer').textContent===timer&&d.getElementById('recordingState').textContent!=='Get ready','Global shortcut cannot start a timed take from Training');
  click('#radarWorkspace'); // Restores Training, not a hidden recorder.
  assert(!d.getElementById('trainingPage').hidden,'Radar data restores the selected radar tab');
  await home();click('#journeyHome [data-collection]');await wait(()=>!d.getElementById('collectionDetail').hidden,'Collection missing');click('#startCollection');await wait(()=>!d.getElementById('captureSetup').hidden,'Resume setup missing');click('#setupNext');await wait(()=>!d.getElementById('recordStage').hidden,'Resume missing');
  click('#settingsButton');w.dispatchEvent(new w.Event('gasp-toggle'));await sleep(100);
  assert(d.getElementById('recordingState').textContent!=='Get ready','Global shortcut cannot record through an open settings dialog');click('#closeSettings');
  // Timed references, cancellation, and self-paced Enter hold/release use the real simulator.
  const beforeCapture=(await request('recordings')).length;click('#recordButton');
  await wait(()=>d.getElementById('recordingState').textContent==='Get ready','Countdown did not start');
  let quitBlocked=false;try{await w.gaspPrepareToQuit();}catch{quitBlocked=true;}
  assert(quitBlocked,'Quit is blocked while capture is active');w.dispatchEvent(new w.Event('gasp-cancel'));
  await wait(()=>d.getElementById('recordingState').textContent==='Ready','Countdown did not cancel');
  assert((await request('recordings')).length===beforeCapture,'Cancelling a countdown creates no recording');
  click('#recordButton');await wait(()=>d.getElementById('captureMode').textContent==='MOVEMENT REFERENCE','Timed reference did not save and advance');
  assert((await request('recordings')).length===beforeCapture+1,'Timed reference saves before advancing to movement');
  const record=d.getElementById('recordButton');await wait(()=>!record.disabled,'Movement recording did not become ready');record.focus();record.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));
  await wait(()=>d.getElementById('recordingState').textContent==='Recording','Enter did not begin a self-paced take');await sleep(900);
  record.dispatchEvent(new w.KeyboardEvent('keyup',{key:'Enter',code:'Enter',bubbles:true}));
  await wait(()=>d.getElementById('promptText').textContent.includes('Purse your lips'),'Movement did not finish on release');
  assert((await request('recordings')).length===beforeCapture+2,'Enter hold/release records a self-paced movement');
  const sessionId=(await request('live')).session.id;
  const reconnect=async profile=>{click('#connectionStatus');const source=d.getElementById('source');source.value='simulator';source.dispatchEvent(new w.Event('change'));const select=d.getElementById('profile');select.value=profile;select.dispatchEvent(new w.Event('change'));click('#connectButton');await wait(()=>!d.getElementById('connectButton').disabled&&d.querySelector('.dialog-notice')?.textContent==='Source connected','Apply and reconnect did not complete');click('#closeSettings');};
  await reconnect('usb-phase-10hz');
  await wait(()=>record.disabled&&d.getElementById('captureAvailability').textContent.includes('20 fps'),'Wrong profile did not block capture');
  assert(record.disabled,'An incompatible radar profile cannot record into the current session');
  await reconnect('usb-phase-20hz');await wait(()=>!record.disabled,'Compatible reconnect did not become ready');
  record.focus();record.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));await wait(()=>d.getElementById('recordingState').textContent==='Recording','Reconnected recording did not begin');await sleep(900);record.dispatchEvent(new w.KeyboardEvent('keyup',{key:'Enter',code:'Enter',bubbles:true}));
  await wait(()=>d.getElementById('promptText').textContent.includes('pa pa pa'),'Reconnected movement did not finish');
  assert((await request('live')).session.id===sessionId&&(await request('recordings')).length===beforeCapture+3,'Reconnecting resumes the same session before the next take');
  await home();await wait(()=>d.getElementById('journeyHome').textContent.includes('3 of 12 recorded · 0 reviewed'),'Recorded progress disappeared before review');
  assert(d.querySelector('.journey-card.current .journey-meter .recorded').style.width==='25%','Baseline bar includes captured prompts before review');
  await home();await training();click('[data-learn="prepare"]');await wait(()=>!!d.getElementById('learnStart'),'Training confirmation missing');click('#learnStart');
  await wait(()=>!!d.getElementById('learningPredictions'),'Local training did not finish');
  assert(d.getElementById('learningWorkspace').textContent.includes('DEVELOPMENT SET'),'Local phrase training reaches a measured development result');
  click('[data-learn="take"]');await wait(()=>!d.getElementById('returnTraining').hidden,'Training return path missing');click('#returnTraining');
  await wait(()=>!d.getElementById('trainingPage').hidden&&!!d.getElementById('learningPredictions'),'Training result did not restore');
  assert(!!d.getElementById('learningPredictionFilter'),'Recording review returns to its training result');
  click('[data-learn="final"]');await wait(()=>!!d.getElementById('learnFinal'),'Final confirmation missing');click('#learnFinal');
  await wait(()=>d.getElementById('learningWorkspace').textContent.includes('Reserved final-test result'),'Final evaluation did not finish');
  assert(!d.getElementById('learningWorkspace').textContent.includes('Compared with'),'Final-test results are not compared against development scores');
  await home();if(d.getElementById('captureLayout').classList.contains('collapsed'))click('#toggleLibrary');d.querySelectorAll('#recordingList details').forEach(e=>e.open=true);
  click('#recordingList [data-delete-session]');await wait(()=>d.getElementById('discardDialog').open,'Delete warning missing');
  assert(d.getElementById('discardDescription').textContent.includes('cannot be undone'),'Delete clearly warns before any removal');click('#cancelDiscard');
  assert((await request('recordings')).length===beforeCapture+3,'Cancelling deletion retains all recordings');
  await home();
  out.textContent=`Passed ${passed.length} interaction regression checks`;out.dataset.results=JSON.stringify(passed);
 }catch(error){out.textContent=`FAILED after ${passed.length}: ${error.message}`;out.dataset.results=JSON.stringify(passed);throw error;}
 finally{if(release)release();w.fetch=original;button.disabled=false;}
};

// Reload the real workspace with a test-only native permission bridge.
const micCheck=document.createElement('button');micCheck.textContent='Check microphone resume';document.querySelector('header').append(micCheck);
micCheck.onclick=async()=>{
 const out=document.getElementById('result'),frame=document.getElementById('workspace');micCheck.disabled=true;
 const request=async(path,method='GET',body)=>{const r=await fetch('/api/'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw Error(await r.text());return r.json();};
 const wait=async(fn,message)=>{const end=Date.now()+15000;while(!fn()){if(Date.now()>end)throw Error(message);await new Promise(r=>setTimeout(r,40));}};
 const assert=(ok,message)=>{if(!ok)throw Error(message);};
 try{
  const preferences=await request('preferences');await request('preferences','PUT',{...preferences,reference_audio:true});
  await request('disconnect','POST');
  await request('connect','POST',{source:'simulator',profile:'usb-phase-20hz'});
  const before=await request('recordings');
  frame.src='/native-preview';await new Promise(resolve=>frame.onload=resolve);
  const d=frame.contentDocument;
  await wait(()=>!!d.querySelector('#journeyHome [data-collection]'),'Restored workspace missing');
  assert(d.getElementById('referenceAudio').checked,'Saved microphone preference was silently turned off on restart');
  d.querySelector('#journeyHome [data-collection]').click();await wait(()=>!!d.getElementById('startCollection'),'Collection missing');
  assert(d.getElementById('startCollection').textContent.includes('Resume'),'Saved session was not resumable');
  d.getElementById('startCollection').click();await wait(()=>!d.getElementById('captureSetup').hidden,'Resume setup missing');
  assert(d.getElementById('setupAudioStatus').textContent==='Permission needed','Permission state is not explained');
  assert(!d.getElementById('setupNext').disabled,'Missing permission stranded the Resume button');
  d.getElementById('setupNext').click();await wait(()=>!d.getElementById('setupError').hidden,'Permission denial was not visible');
  assert(!d.getElementById('captureSetup').hidden&&!d.getElementById('setupNext').disabled,'Denied permission cannot be retried');
  assert((await request('preferences')).reference_audio,'Permission denial overwrote saved intent');
  d.getElementById('setupNext').click();await wait(()=>!d.getElementById('recordStage').hidden&&d.getElementById('inputState').textContent==='Microphone ready','Allowed microphone did not resume recording');
  assert(d.getElementById('stepCount').textContent.startsWith('3 / 12 captured'),'Resume lost captured progress');
  assert(d.getElementById('promptText').textContent.startsWith('pa pa pa'),'Resume did not select the next unrecorded prompt');
  assert((await request('recordings')).length===before.length,'Resuming created unintended takes');
  out.textContent='Passed: restart retains 3 captures and microphone preference; permission denial, retry, readiness, and next prompt verified (mock native bridge).';
 }catch(error){out.textContent='FAILED microphone resume: '+error.message;throw error;}
 finally{micCheck.disabled=false;}
};

const timingCheck=document.createElement('button');timingCheck.textContent='Check timing fallback';document.querySelector('header').append(timingCheck);
timingCheck.onclick=async()=>{
 const out=document.getElementById('result'),frame=document.getElementById('workspace');timingCheck.disabled=true;
 const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
 const wait=async(fn,message)=>{const until=Date.now()+15000;while(!fn()){if(Date.now()>until)throw Error(message);await sleep(30);}};
 let passed=0;const assert=(condition,message)=>{if(!condition)throw Error(message);out.textContent=`Passed ${++passed} timing checks: ${message}`;};
 try{
  frame.src='/native-preview?timing-check='+Date.now();
  await new Promise(resolve=>frame.addEventListener('load',resolve,{once:true}));
  const w=frame.contentWindow,d=w.document,click=s=>d.querySelector(s).click();
  await wait(()=>!!d.querySelector('#journeyHome [data-collection]'),'Workspace did not load');
  const takes=await (await w.fetch('/api/recordings')).json();
  const open=async label=>{
   const item=takes.find(t=>t.label===label);if(!item)throw Error('Missing fixture '+label);
   const t=await (await w.fetch(`/api/sessions/${item.session_id}/trials/${item.id}`)).json();
   if(d.getElementById('captureLayout').classList.contains('collapsed'))click('#toggleLibrary');
   d.querySelectorAll('#recordingList details').forEach(e=>e.open=true);click(`[data-tid="${t.id}"]`);
   await wait(()=>d.getElementById('confirmedText').value===t.target_text&&!d.getElementById('replayStage').hidden,'Take did not open');return t;
  };
  await open('Synthetic syllables');
  await wait(()=>d.getElementById('reviewTimingHint').textContent.includes('9 of 9 sounds placed'),'No acoustic draft');
  assert(w.mockSpeechCalls===0,'Syllable drafts never call Apple recognition');
  assert(d.querySelectorAll('#wordSpans .word-span').length===9,'Draft boundaries appear on the shared timeline');
  assert(d.getElementById('reviewState').textContent.includes('needs review'),'Drafts remain unverified');
  await open('Synthetic incomplete syllables');
  await wait(()=>d.getElementById('reviewTimingHint').textContent.includes('could not be separated reliably'),'No ambiguous-audio hint');
  assert(w.mockSpeechCalls===0&&d.querySelectorAll('#wordSpans .word-span').length===0,'Missing sounds are not fabricated or sent to ASR');
  assert(!d.getElementById('keepTake').disabled,'Uncertain timing does not block transcript review');
  const sentence=await open('Synthetic sentence');
  await wait(()=>d.getElementById('reviewTimingHint').textContent.includes('Automatic sentence timing is unavailable'),'No speech-service fallback');
  assert(w.mockSpeechCalls===1,'Sentences can use the optional native recognizer');
  assert(!d.getElementById('timingAssistance').hidden&&d.getElementById('timingAssistanceDetail').textContent.includes('Siri and Dictation'),'Speech-service details are available without a recording-error banner');
  click('#keepTake');
  await wait(()=>d.getElementById('reviewState').textContent==='verified','Untimed transcript could not be verified');
  const saved=await (await w.fetch(`/api/sessions/${sentence.session_id}/trials/${sentence.id}`)).json();
  assert(saved.accepted&&saved.confirmed_text===sentence.target_text&&saved.words.every(w=>w.start_s==null),'Whole-utterance training keeps verified text without fabricated timestamps');
  await open('Synthetic syllables');await open('Synthetic sentence');await sleep(200);
  assert(w.mockSpeechCalls===1,'Reopening a verified take does not regenerate annotations');
  out.textContent=`Passed ${passed} timing checks · acoustic drafts, uncertain audio, unavailable ASR, and untimed transcript review`;
 }catch(e){out.textContent='FAILED timing: '+e.message;throw e;}finally{timingCheck.disabled=false;}
};

const timelineCheck=document.createElement('button');timelineCheck.textContent='Check timeline editing';document.querySelector('header').append(timelineCheck);
timelineCheck.onclick=async()=>{
 const out=document.getElementById('result'),frame=document.getElementById('workspace');timelineCheck.disabled=true;
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const wait=async(fn,message)=>{const until=Date.now()+15000;while(!fn()){if(Date.now()>until)throw Error(message);await sleep(30);}};
 let passed=0;const assert=(ok,message)=>{if(!ok)throw Error(message);out.textContent=`Passed ${++passed} timeline checks: ${message}`;};
 try{
  frame.src='/native-preview?timeline-check='+Date.now();await new Promise(r=>frame.addEventListener('load',r,{once:true}));
  const w=frame.contentWindow,d=w.document,$=id=>d.getElementById(id),click=s=>d.querySelector(s).click();
  await wait(()=>!!d.querySelector('#journeyHome [data-collection]'),'Workspace did not load');
  const takes=await(await w.fetch('/api/recordings')).json(),take=takes.find(t=>t.label==='Synthetic timeline sentence');
  if($('captureLayout').classList.contains('collapsed'))click('#toggleLibrary');d.querySelectorAll('#recordingList details').forEach(e=>e.open=true);click(`[data-tid="${take.id}"]`);
  await wait(()=>!$('replayStage').hidden&&$('confirmedText').value==='Please open the window.','Sentence did not open');
  assert($('keepTakeLabel')?.parentElement===$('keepTake'),'Opening a take preserves its explicit button label');
  await wait(()=>!$('suggestWords').disabled,'Timing did not finish');
  const player=$('referencePlayer');await wait(()=>Number.isFinite(player.duration),'Audio did not load');
  const time=()=>Number($('timeline').getAttribute('aria-valuenow'));
  player.load();w.setTime(.8);await w.play();
  assert(player.currentTime>=.79&&player.currentTime<1.2,'Playback honors a seek made before audio metadata was ready');w.pause();
  const rect=()=>$('timelineSheet').getBoundingClientRect(),duration=Number($('playTime').textContent.split('/')[1].replace('s',''));
  const point=(t,lane='words')=>({clientX:rect().left+t/duration*rect().width,clientY:rect().top+(lane==='audio'?55:105)});
  const event=(target,t,lane='words',container=$('timelineSheet'))=>({target,currentTarget:container,button:0,buttons:1,pointerId:1,...point(t,lane),preventDefault(){}});
  // Synthetic pointer events cannot own a browser pointer. Stub only capture;
  // exercise the production handlers, DOM hit targets, layout, storage and audio.
  let capturedBy;
  w.Element.prototype.setPointerCapture=function(){capturedBy=this;};
  const drag=(target,a,b,lane='words',cancel=false)=>{const el=$('timelineSheet');el.onpointerdown(event(target,a,lane));el.onpointermove(event(target,b,lane));(cancel?el.onpointercancel:el.onpointerup)(event(target,b,lane));};
  const span=i=>d.querySelector(`[data-span="${i}"]`),start=i=>parseFloat(span(i).style.left)/100*duration,end=i=>start(i)+parseFloat(span(i).style.width)/100*duration;
  // Clear only synthetic fixture timings for repeatable checks.
  for(let i=0;i<4;i++){click(`[data-transcript="${i}"]`);click('#clearWordTime');}
  $('timelineSheet').onpointerdown(event($('timeline'),4,'ruler'));
  $('timelineSheet').onpointerup(event($('timeline'),4,'ruler'));
  // Place the playhead via ruler coordinates, away from editable tracks.
  const ruler={...event($('timeline'),4),clientY:rect().top+15};$('timelineSheet').onpointerdown(ruler);$('timelineSheet').onpointerup(ruler);
  const anchor=time();click('[data-transcript="0"]');assert(time()===anchor,'Selecting a word preserves the listening position');
  drag($('timeline'),1,1.5,'words');assert(Math.abs(start(0)-1)<.01&&Math.abs(end(0)-1.5)<.01,'Draw an interval directly in the Words track');assert(time()===anchor,'Drawing a word does not seek');
  await sleep(1);const body=d.querySelector('[data-word="0"]');drag(body,1.2,1.5);assert(Math.abs(start(0)-1.3)<.01&&Math.abs(end(0)-1.8)<.01,'Drag a whole word without changing duration');assert(time()===anchor,'Moving a word preserves the playhead');
  assert(capturedBy===body,'Word pointer capture preserves the word as the click target');
  drag(d.querySelector('[data-edge="end_s"][data-index="0"]'),1.8,2);assert(Math.abs(end(0)-2)<.01&&time()===anchor,'Trimming preserves the playhead');
  const hoverStart=start(0),hoverTarget=d.querySelector('[data-word="0"]'),sheet=$('timelineSheet');sheet.onpointerdown(event(hoverTarget,1.4));sheet.onpointermove({...event(hoverTarget,4),buttons:0});sheet.onpointerup(event(hoverTarget,1.4));assert(Math.abs(start(0)-hoverStart)<.001,'Pointer movement after button release cannot move a word');
  const old=start(0);drag(d.querySelector('[data-word="0"]'),1.4,1.7,'words',true);assert(Math.abs(start(0)-old)<.001,'Cancelling a drag restores the interval');
  await sleep(1);const transcript=d.querySelector('[data-transcript="1"]'),tr=transcript.getBoundingClientRect(),container=$('reviewTranscript');
  container.onpointerdown({...event(transcript,2.2,'words',container),clientX:tr.x+5,clientY:tr.y+5});container.onpointermove(event(transcript,2.2,'words',container));container.onpointerup(event(transcript,2.2,'words',container));
  assert(capturedBy===transcript,'Transcript pointer capture preserves the word as the click target');
  assert(Math.abs(start(1)-2.2)<.01&&end(1)>start(1),'Drag an unplaced transcript word into the timeline');assert(time()===anchor,'Dropping a word preserves the playhead');
  drag(d.querySelector('[data-word="0"]'),1.4,6);assert(end(0)<=start(1)+.001,'Whole-word movement cannot cross the next word');
  await sleep(1);click('[data-transcript="1"]');click('#playButton');await wait(()=>$('playButton').getAttribute('aria-label')==='Pause recording','Audio playback did not start');
  const runningTime=time();drag(d.querySelector('[data-edge="end_s"][data-index="1"]'),end(1),end(1)+.1);
  assert(!player.paused&&time()>=runningTime&&Math.abs(time()-runningTime)<.4,'Word trimming works during audio playback without seeking');click('#playButton');
  $('loopTarget').value='end';$('loopTarget').dispatchEvent(new w.Event('change'));click('#loopAudio');await wait(()=>$('loopAudio').getAttribute('aria-pressed')==='true'&&!player.paused,'Loop did not start');
  await sleep(1200);assert(time()>=end(1)-.26&&time()<=end(1)+.3,'Half-second boundary loop repeats inside its window');
  drag(d.querySelector('[data-edge="end_s"][data-index="1"]'),end(1),end(1)+.2);await sleep(650);
  assert(time()>=end(1)-.26&&time()<=end(1)+.3&&!player.paused,`Boundary loop follows a trim without stopping (time=${time()}, edge=${end(1)}, paused=${player.paused}, region=${$('loopRegion').title})`);click('#loopAudio');click('#playButton');
  await sleep(1);const before=start(1);d.querySelector('[data-word="1"]').dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',shiftKey:true,bubbles:true}));assert(Math.abs(start(1)-before-.01)<.002,'Shift-arrow nudges the whole word by 10 milliseconds');
  const preserve=start(1);click('#retryTiming');await wait(()=>!$('retryTiming').disabled,'Retry did not finish');assert(Math.abs(start(1)-preserve)<.001,'Unavailable recognition leaves manual edits intact');
  click('#saveAnnotations');await wait(()=>$('reviewState').textContent==='Draft saved','Draft did not save');
  const saved=await(await w.fetch(`/api/sessions/${take.session_id}/trials/${take.id}`)).json();assert(saved.words[0].source==='manual'&&saved.words[1].start_s>saved.words[0].end_s,'Edited intervals persist as manual, ordered annotations');
  const button=$('keepTake'),label=$('keepTakeLabel'),originalLabel=label.textContent;
  for(const copy of ['Verify & keep','Keep & next →','Keep & continue →']){label.textContent=copy;for(const width of [900,700,560]){frame.width=width;await sleep(80);const range=d.createRange();range.selectNodeContents(label);const b=button.getBoundingClientRect(),text=range.getBoundingClientRect();assert(text.left>=b.left&&text.right<=b.right&&button.scrollWidth<=button.clientWidth+1,`${copy} fits at ${width}px`);}}
  label.textContent=originalLabel;
  frame.width=1280;frame.height=800;
  out.textContent=`Passed ${passed} timeline checks · selection, drawing, moving, trimming, cancellation, playback, loops, saving, and button layout`;
 }catch(e){out.textContent='FAILED timeline: '+e.message;throw e;}finally{timelineCheck.disabled=false;}
};
