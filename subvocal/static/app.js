'use strict';
const $ = id => document.getElementById(id);
let state = {}, profiles = [], plan = [], planIndex = 0, busy = false, pollBusy = false;
let stream = null, recorder = null, currentTrial = null, clockOffset = 0, clockUncertainty = 0;
let activeRecording = null, connecting = false;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, method='GET', data) {
  const response = await fetch('/api/' + path, {method, headers: data === undefined ? {} : {'Content-Type':'application/json'}, body:data === undefined ? undefined : JSON.stringify(data)});
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body));
  return body;
}
function notice(message, error=false) { $('notice').textContent=message; $('notice').className=error?'error':''; $('notice').hidden=false; }
function action(id, fn) { $(id).addEventListener('click', async event => { event.preventDefault(); try { await fn(); } catch(error) { notice(error.message,true); } }); }
function wait(ms) { return new Promise(resolve => setTimeout(resolve,ms)); }
function chart(id, values, color='#087e78', zero=false) {
  const canvas=$(id), rect=canvas.getBoundingClientRect(); if(!rect.width) return;
  const ratio=window.devicePixelRatio || 1, width=rect.width, height=190;
  canvas.width=width*ratio; canvas.height=height*ratio;
  const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);ctx.clearRect(0,0,width,height);
  ctx.font='9px ui-monospace,monospace';ctx.strokeStyle='#e7eeeb';ctx.fillStyle='#83958d';
  const finite=values.filter(Number.isFinite); let min=finite.length?Math.min(...finite):0,max=finite.length?Math.max(...finite):1;
  if(zero) min=Math.min(0,min); if(max-min<1e-6){max+=.5;min-=.5;}
  const pad=(max-min)*.12; min-=pad;max+=pad;
  for(let i=0;i<4;i++){const y=12+i*50;ctx.beginPath();ctx.moveTo(36,y);ctx.lineTo(width-5,y);ctx.stroke();ctx.fillText((max-(y-12)/150*(max-min)).toFixed(1),0,y+3);}
  if(values.length<2){ctx.fillStyle='#95a49d';ctx.fillText('Waiting for data',width/2-45,95);return;}
  ctx.beginPath();values.forEach((v,i)=>{const x=36+i/(values.length-1)*(width-43),y=12+(max-v)/(max-min)*150;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});
  ctx.strokeStyle=color;ctx.lineWidth=1.7;ctx.stroke();
}
function showPage(page) {
  document.querySelectorAll('.page').forEach(x=>x.hidden=x.id!=='page-'+page);
  document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.page===page));
  if(page==='review') loadDataset().catch(e=>notice(e.message,true));
  if(page==='train') loadTraining().catch(e=>notice(e.message,true));
}
document.querySelectorAll('.nav').forEach(button=>button.onclick=()=>showPage(button.dataset.page));
async function refreshPorts(){
  const found=await api('ports');
  for(const id of ['cliPort','dataPort']) { const previous=$(id).value; $(id).innerHTML='<option value="">Choose a port…</option>'+found.map(p=>`<option value="${esc(p.device)}">${esc(p.device)} · ${esc(p.interface||p.description)}</option>`).join(''); $(id).value=previous; }
  if(!found.length) notice('No serial devices found. Connect the board with a data-capable USB cable; its driver may need installation.');
}
function selectProfile(){
  const p=profiles.find(x=>x.name===$('profile').value); if(!p)return;
  $('configText').value=p.text;$('budget').textContent=p.lvds_adc?`${p.frame_hz} radar frames/s · ${p.loops} loops/frame · ${(p.adc_bytes_s/1e6).toFixed(2)} MB/s ADC · ${(p.burst_duration_ms).toFixed(2)} ms bursts`:`${p.frame_hz} Hz · ${p.range_bins} bins · ${(p.range_step_m*100).toFixed(2)} cm/bin · estimated ${Math.round(p.uart_utilization*100)}% UART`;
}
$('profile').onchange=selectProfile;
function selectSource(){
  const kind=$('source').value,dca=kind==='dca1000';
  $('serialFields').hidden=kind==='simulator';$('dataPortField').hidden=dca;$('dcaFields').hidden=!dca;
  $('duration').max=dca?'25':'30';if(Number($('duration').value)>Number($('duration').max))$('duration').value=$('duration').max;
  $('profile').innerHTML=profiles.filter(p=>p.lvds_adc===dca).map(p=>`<option value="${p.name}">${p.lvds_adc?'DCA raw ADC':p.name.replace('usb-phase-','USB phase · ')} · experimental</option>`).join('');
  selectProfile();
  $('connectionNote').textContent=dca?'USB commands + raw Ethernet. Arm the source, create a session, then record a take.':kind==='simulator'?'Simulation tests the software pipeline. It does not measure speech recognition.':'Select both observed USB port roles. Compatible SDK 3.x OOB AOP firmware is required.';
  if(kind!=='simulator')refreshPorts().catch(e=>notice(e.message,true));
}
$('source').onchange=selectSource;
action('refreshPorts',refreshPorts);
action('connect',async()=>{
  connecting=true;$('connect').disabled=true;
  try{if($('source').value==='dca1000'&&!$('confirmLayout').checked)throw new Error('Select the supported two-lane complex16 ADC decoder before arming DCA.');
    await api('connect','POST',{source:$('source').value,profile:$('profile').value,config_text:$('configText').value,cli_port:$('cliPort').value||null,data_port:$('dataPort').value||null,host_ip:$('hostIp').value.trim(),board_ip:$('boardIp').value.trim(),confirm_layout:$('confirmLayout').checked});
    notice($('source').value==='simulator'?'Simulator connected. All recordings and metrics will be marked synthetic.':$('source').value==='dca1000'?'DCA acknowledged and radar configured. Create a session; raw capture starts with each prompted take.':'Configuration acknowledged. Checking the incoming USB stream…');
  }finally{connecting=false;await poll();}
});
action('disconnect',async()=>{await api('disconnect','POST');notice('Source disconnected. Your saved recordings remain available.');await poll();});
$('sessionForm').onsubmit=async event=>{event.preventDefault();try{
  const session=await api('sessions','POST',{name:$('sessionName').value.trim(),subject:$('subject').value.trim(),notes:$('sessionNotes').value});
  $('activeSession').textContent=`Active: ${session.name} · ${session.id}`;notice('Session created. Shuffle your phrase deck and record a trial.');await poll();
}catch(e){notice(e.message,true);}};
function shufflePlan(){
  if(busy)throw new Error('Wait for the current recording to finish.');
  const phrases=$('phrases').value.split('\n').map(s=>s.trim()).filter(Boolean),reps=Number($('reps').value);
  if(!phrases.length||phrases.length>50||!Number.isInteger(reps)||reps<1||reps>100)throw new Error('Use 1–50 phrases and 1–100 repetitions.');
  plan=phrases.flatMap(label=>Array(reps).fill(label));
  for(let i=plan.length-1;i>0;i--){let j=Math.floor(Math.random()*(i+1));[plan[i],plan[j]]=[plan[j],plan[i]];}
  planIndex=0;updatePrompt();
}
function updatePrompt(){ $('prompt').textContent=plan[planIndex]||'Session deck complete';$('planProgress').textContent=plan.length?`${planIndex} / ${plan.length} RECORDED`:'READY WHEN YOU ARE'; }
action('makePlan',shufflePlan);
async function syncClock(){const t0=performance.now(),remote=await api('clock'),t1=performance.now();clockOffset=remote.monotonic_ns/1e6-(t0+t1)/2;clockUncertainty=(t1-t0)/2;}
action('enableCamera',async()=>{
  if(!window.MediaRecorder||!navigator.mediaDevices)throw new Error('Browser media capture is unavailable. Use Chrome on localhost.');
  stream=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480,frameRate:30},audio:true});
  $('cameraPreview').srcObject=stream;$('cameraPreview').hidden=false;$('cameraPlaceholder').hidden=true;await $('cameraPreview').play();
  $('enableCamera').hidden=true;$('disableCamera').hidden=false;await syncClock();notice('Reference camera and microphone enabled. Media is saved locally with each trial.');
});
function disableCamera(){if(recorder?.state==='recording')throw new Error('Wait for the trial to finish.');stream?.getTracks().forEach(t=>t.stop());stream=null;$('cameraPreview').srcObject=null;$('cameraPreview').hidden=true;$('cameraPlaceholder').hidden=false;$('enableCamera').hidden=false;$('disableCamera').hidden=true;}
action('disableCamera',disableCamera);
async function startReference(){
  if(!stream)return null;await syncClock();
  const types=['video/webm;codecs=vp8,opus','video/webm','video/mp4'];const mimeType=types.find(t=>MediaRecorder.isTypeSupported(t));
  recorder=new MediaRecorder(stream,mimeType?{mimeType}:undefined);
  let chunks=[],startServer=0;const current=recorder;
  const finished=new Promise((resolve,reject)=>{current.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};current.onstop=()=>resolve(new Blob(chunks,{type:current.mimeType}));current.onerror=e=>reject(new Error(e.error?.message||'Reference recording failed'));});
  await new Promise((resolve,reject)=>{current.onstart=()=>{startServer=(performance.now()+clockOffset)*1e6;resolve();};current.addEventListener('error',e=>reject(new Error(e.error?.message||'Media recorder failed to start')),{once:true});current.start();});
  return {stop:async()=>{if(current.state==='recording')current.stop();return {blob:await finished,startServer,uncertainty:clockUncertainty};}};
}
action('record',async()=>{
  if(busy)return;if(!plan.length)shufflePlan();if(planIndex>=plan.length)throw new Error('Shuffle a new plan to record more trials.');
  const duration=Number($('duration').value),maxDuration=state.source==='dca1000'?25:30;if(!(duration>=.5&&duration<=maxDuration))throw new Error(`Duration must be between 0.5 and ${maxDuration} seconds.`);
  busy=true;$('record').disabled=true;$('enableCamera').disabled=true;$('disableCamera').disabled=true;
  let reference=null,media=null;
  try{
    for(let n=3;n>0;n--){$('promptState').textContent=`STARTING IN ${n}`;await wait(1000);}
    reference=await startReference();
    const label=plan[planIndex],articulation=label.toLowerCase()==='rest'?'rest':$('articulation').value;
    const rec=await api('record','POST',{label,duration_s:duration,articulation,notes:''});
    activeRecording=rec.id;$('cancelRecord').hidden=state.source!=='dca1000';$('cancelRecord').disabled=false;
    let result=rec,started=null;
    while(['arming','recording','processing','cancelling'].includes(result.status)){
      if(result.status==='recording'){
        if(started===null)started=performance.now();
        $('promptState').textContent='RECORDING';document.body.classList.add('recording');
        $('recordProgress').style.width=Math.min(100,(performance.now()-started)/(duration*1000)*100)+'%';
      }else{$('promptState').textContent=result.status==='arming'?'ARMING DCA · WAIT':result.status==='processing'?'DECODING RAW ADC': 'STOPPING CAPTURE';document.body.classList.remove('recording');}
      $('cancelRecord').disabled=['processing','cancelling'].includes(result.status);
      await wait(150);result=await api('record/'+rec.id);
    }
    if(reference){media=await reference.stop();reference=null;}
    if(result.status==='cancelled'){notice('DCA capture cancelled. Partial raw files are retained; no training trial was added.');return;}
    if(result.status!=='complete')throw new Error(result.error||'Trial failed');
    if(media){
      const response=await fetch(`/api/sessions/${result.session_id}/trials/${result.trial.id}/media`,{method:'PUT',headers:{'Content-Type':media.blob.type,'X-Media-Start-Server-Ns':String(Math.round(media.startServer)),'X-Clock-Uncertainty-Ms':String(media.uncertainty)},body:media.blob});
      if(!response.ok){const e=await response.json();notice(`Radar trial saved, but reference media failed: ${e.detail}`,true);}else notice(`Saved “${label}” with radar and reference media.`);
    }else notice(`Saved “${label}” · ${result.trial.frames} complex ${state.source==='dca1000'?'samples':'frames'}${state.synthetic?' · SYNTHETIC':''}.`);
    planIndex++;updatePrompt();
  }finally{
    if(reference)await reference.stop().catch(()=>{});activeRecording=null;$('cancelRecord').hidden=true;busy=false;document.body.classList.remove('recording');$('recordProgress').style.width='0';$('promptState').textContent='NEXT PHRASE';$('enableCamera').disabled=false;$('disableCamera').disabled=false;await poll();
  }
});
action('cancelRecord',async()=>{if(activeRecording){$('cancelRecord').disabled=true;await api('record/'+activeRecording+'/cancel','POST');}});
async function poll(){
  if(pollBusy)return;pollBusy=true;
  try{
    state=await api(`live?selected_bin=${Number($('rangeBin').value)||0}&antenna=${Number($('antenna').value)||0}`);
    const connected=state.status==='connected',stale=state.packet_age_s===null||state.packet_age_s>2,dca=state.source==='dca1000';
    $('modeBadge').textContent=state.source?(state.synthetic?'SIMULATOR · SYNTHETIC':dca?'DCA1000 · RAW ADC':'USB · HARDWARE'):'Disconnected';$('modeBadge').className='badge '+(state.source?(state.synthetic?'sim':'real'):'');
    $('liveStatus').textContent=state.error?'Capture error':!connected?'Waiting for a source':dca?`DCA ${state.dca.status} · plots after capture`:stale?'Connected · no recent packets':state.complex_available?'Complex signal available':'Packets received · no complex TLV';
    $('fpsTitle').textContent=dca?'RADAR FRAMES / SEC':'FRAMES / SEC';$('fpsDetail').textContent=dca?'configured · burst acquisition':'measured at host';
    $('framesTitle').textContent=dca?'DECODED COMPLEX SAMPLES':'COMPLEX FRAMES';
    $('fps').textContent=dca?state.profile.frame_hz.toFixed(1):state.measured_hz?state.measured_hz.toFixed(1):'—';$('frames').textContent=(state.complex_frames||0).toLocaleString();$('gaps').textContent=state.frame_gaps;
    $('parserInfo').textContent=dca?'Raw ADC frames discarded after packet loss':`${state.bad_packets} malformed · ${state.discarded_bytes} discarded bytes`;
    $('signalKind').textContent=dca?'Range FFT per chirp loop · last take':state.complex_available?'Frame-averaged complex IQ':state.tlv_types.length?'TLVs: '+state.tlv_types.join(', '):'No stream';
    $('bandwidthTitle').textContent=dca?'RAW ETHERNET INPUT':'UART BUDGET';$('bandwidthDetail').textContent=dca?'estimated ADC bytes / sec':'estimated, 8N1';
    $('uart').textContent=state.profile?(dca?(state.profile.adc_bytes_s/1e6).toFixed(2)+' MB/s':Math.round(state.profile.uart_utilization*100)+'%'):'—';
    $('dcaStatus').hidden=!dca;
    if(dca){const raw=state.dca,last=raw.last_capture;$('dcaStage').textContent=raw.status.toUpperCase();$('dcaProgress').textContent=`${raw.packets.toLocaleString()} UDP packets · ${(raw.bytes/1e6).toFixed(2)} MB · ${raw.duplicates||0} duplicates · ${raw.out_of_order||0} out of order`+(last?` · last capture: ${last.missing_bytes||0} known missing bytes; tail completeness unknown`:'');}
    $('connect').disabled=connecting||!!state.source||busy;$('disconnect').disabled=!state.source||busy||!!state.recording;$('record').disabled=busy||!!state.recording||!state.session||!state.capture_ready||!connected||plan.length>0&&planIndex>=plan.length;
    $('newSession').disabled=!connected||busy||!!state.recording;
    for(const id of ['source','profile','configText','hostIp','boardIp','confirmLayout','cliPort','dataPort'])$(id).disabled=connecting||!!state.source;
    $('decode').disabled=state.live_decode_available===false;
    $('predictLast').disabled=!dca||!state.last_trial||busy||!!state.recording;
    $('activeSession').textContent=state.session?`Active: ${state.session.name} · ${state.session.id}`:'No active session. Create a new one after repositioning or returning another day.';
    $('rangeBin').max=state.profile?state.profile.range_bins-1:63;$('antenna').max=state.antenna_count?state.antenna_count-1:11;
    const step=state.profile?.range_step_m||0;$('rangeLabel').textContent=step?`0–${((state.profile.range_bins-1)*step).toFixed(2)} m · selected ${(Number($('rangeBin').value)*step).toFixed(2)} m`:'—';
    chart('rangePlot',state.range_magnitude||[],'#087e78',true);chart('phasePlot',state.phase||[],'#55829a');
    if(state.error)notice(state.error,true);
    if(connected&&!dca&&!state.synthetic&&!stale&&!state.complex_available)$('connectionNote').textContent='No complex heatmap yet. People Counting/vital-sign firmware uses a different protocol. This app expects SDK 3.x OOB AOP firmware.';
  }catch(e){$('liveStatus').textContent='Server unavailable';}finally{pollBusy=false;}
}
async function loadDataset(){
  const sessions=await api('sessions');const container=$('datasetList');container.innerHTML='';
  if(!sessions.length){container.innerHTML='<p class="empty">No recordings yet. Connect a source, create a session, and record a trial.</p>';return;}
  for(const session of sessions){
    const details=document.createElement('details');details.className='dataset-session';
    details.innerHTML=`<summary>${esc(session.name)} <span class="badge ${session.synthetic?'sim':'real'}">${session.synthetic?'SYNTHETIC':esc(session.source)}</span> <small>${session.trial_count} trials · ${esc(session.subject)}</small></summary><div class="trial-list"></div>`;
    details.addEventListener('toggle',async()=>{if(!details.open)return;try{
      const trials=await api(`sessions/${session.id}/trials`);const list=details.querySelector('.trial-list');list.innerHTML='';
      if(!trials.length)list.innerHTML='<p class="hint">No trials in this session yet.</p>';
      for(const trial of trials){const row=document.createElement('div');row.className='trial-row'+(trial.accepted?'':' excluded');row.innerHTML=`<span>${esc(trial.label)}</span><small>${trial.frames} ${trial.source==='dca1000'?'samples':'frames'} · ${trial.duration_s.toFixed(1)}s</small><small>${trial.frame_gaps} gaps</small><button class="text-button">Review ↗</button>`;row.querySelector('button').onclick=()=>openTrial(session.id,trial);list.append(row);}
    }catch(e){notice(e.message,true);}});container.append(details);
  }
}
async function openTrial(sid,trial){
  currentTrial={sid,trial};const signal=await api(`sessions/${sid}/trials/${trial.id}/signal`);
  $('trialDetail').hidden=false;$('trialTitle').textContent=trial.label;$('correctLabel').value=trial.label;
  $('trialFacts').textContent=`${trial.frames} frames · ${trial.measured_hz.toFixed(1)} Hz · ${trial.frame_gaps} gaps · ${trial.articulation||'unspecified'} · ${trial.synthetic?'SYNTHETIC':'hardware'} · checksum recorded`;
  $('rawDownloads').hidden=trial.source!=='dca1000';
  if(trial.source==='dca1000'){
    $('trialFacts').textContent=`${trial.frames} complex chirp-loop samples · ${trial.adc_quality.kept_frames} ADC frames · ${trial.adc_quality.dropped_frames} frames dropped · ${trial.raw_quality?.missing_bytes||0} known missing bytes · burst timing retained · tail completeness unknown`;
    for(const [id,name] of [['downloadAdc','adc.bin'],['downloadManifest','manifest.json'],['downloadConfig','radar.cfg']])$(id).href=`/api/sessions/${sid}/trials/${trial.id}/raw/${name}`;
  }
  $('toggleAccept').textContent=trial.accepted?'Exclude trial':'Include trial';$('downloadTrial').href=`/api/sessions/${sid}/trials/${trial.id}/download`;
  $('reviewVideo').hidden=!trial.media;if(trial.media)$('reviewVideo').src=`/api/sessions/${sid}/trials/${trial.id}/media`;else{$('reviewVideo').pause();$('reviewVideo').removeAttribute('src');}
  chart('reviewPlot',signal.phase,'#55829a');$('trialDetail').scrollIntoView({behavior:'smooth',block:'nearest'});
  const compatible=await api('models?session_id='+encodeURIComponent(sid));
  $('trialModelSelect').innerHTML=compatible.length?compatible.map(m=>`<option value="${esc(m.id)}">${esc(m.id)} · ${esc(m.source)}${m.synthetic?' · SYNTHETIC':''}</option>`).join(''):'<option value="">No compatible model — train on separate sessions first</option>';
  $('predictTrial').disabled=!compatible.length;
  $('trialPrediction').textContent='Radar is the only model input. Predictions on training takes are marked as playback checks.';
}
function savedPredictionText(result){
  const use=result.evaluation_use==='training'?'TRAINING TAKE · playback check':result.evaluation_use==='held_out'?'HELD-OUT TAKE · already in the model report':`NEW TAKE${result.session_seen?' · session previously used by this model':''}`;
  return `${result.synthetic?'SYNTHETIC · ':''}${result.source} · ${use}. ${result.rejected?'Rejected; best candidate: '+result.candidate:result.label} · score ${result.score.toFixed(2)} (uncalibrated). Reference label: ${result.expected_label}.`;
}
action('predictTrial',async()=>{
  if(!currentTrial||!$('trialModelSelect').value)throw new Error('Choose a compatible model first.');
  const result=await api('predict-trial','POST',{model_id:$('trialModelSelect').value,session_id:currentTrial.sid,trial_id:currentTrial.trial.id,threshold:.65});
  $('trialPrediction').textContent=savedPredictionText(result);
});
action('refreshDataset',loadDataset);
action('saveLabel',async()=>{if(!currentTrial)return;const {sid,trial}=currentTrial;const updated=await api(`sessions/${sid}/trials/${trial.id}`,'PATCH',{label:$('correctLabel').value.trim()});await openTrial(sid,updated);await loadDataset();notice('Label updated. Existing model reports retain their original dataset snapshot.');});
action('toggleAccept',async()=>{if(!currentTrial)return;const {sid,trial}=currentTrial;const updated=await api(`sessions/${sid}/trials/${trial.id}`,'PATCH',{accepted:!trial.accepted});await openTrial(sid,updated);await loadDataset();});
async function loadTraining(){
  const sessions=await api('sessions');$('trainSessions').innerHTML=sessions.length?sessions.map(s=>`<div class="train-row"><div>${esc(s.name)} <small>${s.accepted_count} accepted · ${esc(s.subject)} · ${s.synthetic?'SYNTHETIC':esc(s.source)} · ${s.profile.sha256.slice(0,8)}</small></div><label><input type="radio" name="split-${s.id}" data-sid="${s.id}" value="train">Train</label><label><input type="radio" name="split-${s.id}" data-sid="${s.id}" value="test">Test</label></div>`).join(''):'<p class="empty">Record at least two separate sessions first.</p>';
  await loadModels();
}
async function loadModels(){
  const models=await api('models');$('modelSelect').innerHTML=models.map(m=>`<option value="${esc(m.id)}">${esc(m.id)} · ${m.synthetic?'SYNTHETIC':esc(m.source)} · ${Math.round(m.accuracy*100)}%</option>`).join('');
  $('modelReports').innerHTML=models.slice(0,3).map(m=>`<article class="card"><div class="card-title"><h3>${m.synthetic?'Synthetic pipeline check':'Held-out session evaluation'}</h3><span>${esc(m.id)}</span></div>${m.synthetic?'<p class="hint">These generated signals encode their labels. This score only checks the software pipeline; it is not evidence of silent-speech accuracy.</p>':''}<div class="report-metrics"><div><strong>${(m.accuracy*100).toFixed(1)}%</strong><span>Accuracy</span></div><div><strong>${m.macro_f1.toFixed(2)}</strong><span>Macro F1</span></div><div><strong>${m.test_examples}</strong><span>Held-out trials</span></div></div><div style="overflow:auto"><table class="confusion"><caption>Confusion matrix · actual rows / predicted columns</caption><thead><tr><th>Actual ↓</th>${m.labels.map(l=>`<th>${esc(l)}</th>`).join('')}</tr></thead><tbody>${m.confusion_matrix.map((row,i)=>`<tr><th>${esc(m.labels[i])}</th>${row.map(n=>`<td>${n}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="hint">Train: ${m.train_examples} · test: ${m.test_examples} · majority baseline: ${Math.round(m.majority_baseline*100)}% · ${m.rejected_trials.length} trials rejected by quality checks.<br>Held out: ${m.test_session_ids.map(esc).join(', ')}</p></article>`).join('');
}
action('train',async()=>{
  const choices=[...document.querySelectorAll('#trainSessions input:checked')],session_ids=choices.map(c=>c.dataset.sid),test_session_ids=choices.filter(c=>c.value==='test').map(c=>c.dataset.sid);
  if(!test_session_ids.length||!choices.some(c=>c.value==='train'))throw new Error('Select separate train and test sessions.');
  $('train').disabled=true;$('trainStatus').textContent='Training queued…';
  try{const task=await api('train','POST',{session_ids,test_session_ids,range_min_m:Number($('gateMin').value),range_max_m:Number($('gateMax').value)});let job;
    do{await wait(400);job=await api('jobs/'+task.id);$('trainStatus').textContent=`Baseline job ${job.status}…`;}while(['queued','running'].includes(job.status));
    if(job.status!=='complete')throw new Error(job.error);$('trainStatus').textContent=`Saved model ${job.report.id}. ${job.report.synthetic?'Synthetic verification only.':'Whole-session holdout complete.'}`;await loadModels();
  }finally{$('train').disabled=false;}
});
action('decode',async()=>{if(!$('modelSelect').value)throw new Error('Train a model first.');const result=await api('decode','POST',{model_id:$('modelSelect').value,seconds:3,threshold:.65});$('prediction').textContent=`${result.synthetic?'SYNTHETIC · ':''}${result.rejected?'Rejected; best candidate: '+result.candidate:result.label} · score ${result.score.toFixed(2)} (uncalibrated)`;if(!result.rejected)$('annotation').value+=($('annotation').value?'\n':'')+result.label;});
action('predictLast',async()=>{
  if(!$('modelSelect').value||!state.last_trial)throw new Error('Record a DCA take and choose a matching model first.');
  const result=await api('predict-trial','POST',{model_id:$('modelSelect').value,...state.last_trial,threshold:.65});
  $('prediction').textContent=savedPredictionText(result);
  if(!result.rejected)$('annotation').value+=($('annotation').value?'\n':'')+result.label;
});
action('copyText',async()=>{await navigator.clipboard.writeText($('annotation').value);notice('Scratchpad copied.');});
window.addEventListener('beforeunload',()=>stream?.getTracks().forEach(t=>t.stop()));
async function init(){try{profiles=await api('profiles');selectSource();const health=await api('health');$('dataLocation').textContent='Local data: '+health.data_root;shufflePlan();await poll();setInterval(poll,350);}catch(e){notice(e.message,true);}}
init();
