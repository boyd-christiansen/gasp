// Test-only script loaded after the production app in an isolated fixture page.
(async()=>{
 const out=document.createElement('output');out.id='failureResults';out.style='position:fixed;top:0;right:0;background:white;z-index:1000;padding:10px;max-width:600px';document.body.append(out);
 const passed=[], originalFetch=window.fetch, originalStart=startAudio, originalClock=clock, originalRecorder=window.MediaRecorder;
 const wait=async(fn,message)=>{const end=Date.now()+15000;while(!fn()){if(Date.now()>end)throw Error(message);await sleep(30);}};
 const assert=(ok,message)=>{if(!ok)throw Error(message);passed.push(message);out.textContent=`Passed ${passed.length}: ${message}`;};
 let release;
 try{
  await wait(()=>journeyReady&&!!preferences&&!!document.querySelector('#journeyHome [data-collection]'),'App did not load');
  await openCollection('calibration');const priorSessions=sessions,cohort=journeyData.progress.cohort_id;
  const completed={id:'latest-fixture',created_ns:2000,subject:preferences.setup.subject,step_count:12,completed_steps:12,verified_steps:7,pending_count:5,trial_count:12,collection:{type_id:'calibration',cohort_id:cohort}};
  sessions=[{...completed,id:'old-fixture',created_ns:1000,completed_steps:5},completed];renderDetail();
  assert($('startCollection').textContent.includes('Review 5 takes'),'The collection entry reviews the latest completed capture instead of resuming an older session');
  const reviewHandler=reviewSession;let reviewedId=null;reviewSession=async id=>{reviewedId=id;};await $('startCollection').onclick();reviewSession=reviewHandler;
  assert(reviewedId===completed.id,'The primary collection action opens the intended session');sessions=priorSessions;await sceneHome();
  const take=recordings.find(t=>t.label==='Synthetic timeline sentence');await openTake(take.session_id,take.id);
  words=textTokens($('confirmedText').value).map(text=>({text,start_s:null,end_s:null,source:'manual'}));
  wordIndex=0;setTime(.5);setEdge('start_s');await sceneHome();
  const saved=await api(`sessions/${take.session_id}/trials/${take.id}`);
  assert(saved.words[0].start_s===.5&&saved.words[0].end_s==null,'Navigation saves an unfinished boundary');
  await openTake(take.session_id,take.id);wordIndex=0;drawTimeline();
  assert(!$('wordDraft').hidden,'Reopened partial boundary remains visible');
  assert(wordLimits(1).start===.5,'Neighboring words respect unfinished boundaries');
  const suggested=mergeTimingSuggestions(words,words.map((w,i)=>({...w,start_s:.1*i,end_s:.1*i+.1})));
  assert(suggested[1].start_s==null,'Automatic timing cannot overlap a partial manual boundary');
  let blocked=false;try{await saveReview(true);}catch(e){blocked=e.message.includes('Finish or clear');}
  assert(blocked,'Keep explains the unfinished boundary');
  setTime(.8);setEdge('end_s');setTime(1);let reverseBlocked=false;try{setEdge('start_s');}catch{reverseBlocked=true;}
  assert(reverseBlocked&&words[0].start_s===.5,'Boundary shortcuts cannot create reversed intervals');
  $('clearWordTime').click();await saveReview();
  let patchSeen=false;
  window.fetch=async(url,opts={})=>{const response=await originalFetch(url,opts);if(opts.method==='PATCH'&&!patchSeen){patchSeen=true;await new Promise(r=>release=r);}return response;};
  reviewCollectionId=take.session_id;const decision=reviewDecision(true);await wait(()=>patchSeen,'Keep request missing');
  document.querySelector('[data-tab="train"]').click();release();release=null;await decision;await wait(()=>tab==='train','Navigation did not complete');
  assert(!$('trainingPage').hidden&&$('doneStage').hidden,'Late Keep response cannot steal Training navigation');window.fetch=originalFetch;
  await sceneHome();await openTake(take.session_id,take.id);await saveReview();
  patchSeen=false;window.fetch=async(url,opts={})=>{const response=await originalFetch(url,opts);if(opts.method==='PATCH'&&!patchSeen){patchSeen=true;await new Promise(r=>release=r);}return response;};
  const newNote='Newer review edit '+Date.now(),newer=reviewDecision(true);await wait(()=>patchSeen,'Second Keep missing');$('reviewNotes').value=newNote;$('reviewNotes').dispatchEvent(new Event('input'));release();release=null;await newer;window.fetch=originalFetch;
  assert(stage==='replay'&&dirty&&$('reviewNotes').value===newNote,'Edits made during Keep remain open for review');await saveIfDirty();
  // Fail the clock while microphone startup is still pending.
  await api('disconnect','POST');await api('connect','POST',{source:'simulator',profile:'usb-phase-20hz'});await sleep(250);await poll();
  activeSession=await api('collections/calibration/sessions','POST',{setup:{subject:'synthetic-fixture'}});trials=[];stepOverride=activeSession.collection.plan.steps.find(s=>s.prompt_id==='jaw').step_id;
  showTab('capture');setStage('record');$('referenceAudio').checked=false;
  startAudio=async()=>{await sleep(80);audioActive=true;audioStopped=false;};clock=async()=>{throw Error('Synthetic clock outage');};
  const countBefore=(await api('recordings')).length;await toggleRecording();
  assert(!audioActive&&!busy&&!activeRecord,'Failed clock waits for microphone startup and cleans it up');
  assert((await api('recordings')).length===countBefore,'Failed preparation creates no partial take');startAudio=originalStart;clock=originalClock;
  let createdRecorder=false,clockFinished;
  window.MediaRecorder=class {constructor(){createdRecorder=true;this.state='inactive';this.mimeType='audio/wav';}start(){this.state='recording';}stop(){this.state='inactive';this.onstop();}};
  browserAudio={};$('referenceAudio').checked=true;
  const browserStart=startAudio(new Promise(r=>clockFinished=r));await sleep(40);
  assert(!createdRecorder,'Browser microphone waits for its clock estimate before starting');clockFinished();await browserStart;await discardAudio();
  window.MediaRecorder=originalRecorder;browserAudio=null;$('referenceAudio').checked=false;
  audioActive=true;audioStopped=true;browserBlob=Promise.resolve(new Blob(['synthetic audio'],{type:'audio/wav'}));
  window.fetch=async(url,opts)=>String(url).endsWith('/media')?new Response('{}',{status:503}):originalFetch(url,opts);
  try{await attachAudio('fixture','take');}catch{}
  assert(!!pendingReference&&audioActive,'Failed audio attachment retains the reference for retry');
  assert(!canStartCapture(),'Pending unsaved audio prevents another take from overwriting it');
  window.fetch=async(url,opts)=>String(url).endsWith('/media')?new Response('{}',{status:200}):originalFetch(url,opts);
  await attachAudio('fixture','take');assert(!pendingReference&&!audioActive,'Successful retry clears the pending reference');window.fetch=originalFetch;
  trials=[take];window.fetch=async(url,opts)=>String(url).endsWith('/quality')?new Response(JSON.stringify({warnings:[{code:'radar_gap',requires_action:false,message:'Synthetic small gap'}],radar_gaps:[]}),{status:200}):originalFetch(url,opts);
  await afterCapture();assert(!checkedTake&&$('captureCheck').hidden,'A minor gap remains advisory without blocking collection');
  window.fetch=async(url,opts)=>String(url).endsWith('/quality')?new Response(JSON.stringify({warnings:[{code:'audio_gap',requires_action:true,message:'Synthetic interrupted microphone'}],radar_gaps:[]}),{status:200}):originalFetch(url,opts);
  await afterCapture();assert(!!checkedTake&&!$('captureCheck').hidden,'An interrupted microphone still requests immediate attention');
  window.fetch=originalFetch;trials=[];checkedTake=null;$('captureCheck').hidden=true;
  stepOverride=null;renderPrompt();const countdown=beginTimedTake();await wait(()=>timedCountdown,'Countdown did not start');await api('disconnect','POST');await poll();await countdown;
  assert(!busy&&!timedCountdown&&$('recordingState').textContent!=='Get ready','Lost radar during countdown resets the recorder');
  assert((await api('recordings')).length===countBefore,'Lost radar countdown creates no take');
  // A source can still own its port after a reader error.
  await api('connect','POST',{source:'simulator',profile:'usb-phase-20hz'});await poll();state.status='error';updateConnection();
  assert(!$('disconnectButton').disabled,'An errored radar can be explicitly disconnected');
  const calls=[];window.fetch=async(url,opts)=>{if(['/api/connect','/api/disconnect'].includes(String(url)))calls.push(String(url));return originalFetch(url,opts);};
  $('source').value='simulator';sourceChanged();$('profile').value='usb-phase-20hz';await connectRadar();window.fetch=originalFetch;
  assert(calls.join(',')==='/api/disconnect,/api/connect','Reconnect releases an errored source before opening it');
  assert(state.status==='connected','Reconnect restores a usable source');await sceneHome();
  out.textContent=`Passed ${passed.length} failure-path checks`;out.dataset.results=JSON.stringify(passed);
 }catch(e){out.textContent=`FAILED after ${passed.length}: ${e.message}`;out.dataset.results=JSON.stringify(passed);throw e;}
 finally{if(release)release();window.fetch=originalFetch;startAudio=originalStart;clock=originalClock;window.MediaRecorder=originalRecorder;}
})();
