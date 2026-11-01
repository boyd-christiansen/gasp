
const icons={arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',chevron:'<path d="m8 10 4 4 4-4"/>',sidebar:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',capture:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>',chart:'<path d="M4 4v16h16M8 16v-4m5 4V7m5 9v-6"/>',mic:'<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M6 11v1a6 6 0 0 0 12 0v-1m-6 7v3m-3 0h6"/>',settings:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="white"/><circle cx="15" cy="17" r="3" fill="white"/>',check:'<path d="m5 12 4 4L19 6"/>',lock:'<rect x="6" y="10" width="12" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',calibrate:'<path d="M3 8V4h4m10 0h4v4M3 16v4h4m10 0h4v-4"/><circle cx="12" cy="10" r="4"/><path d="M6 19c1-6 11-6 12 0"/>',speech:'<path d="M3 10v4m4-7v10m5-14v18m5-14v10m4-7v4"/>',book:'<path d="M12 5v16M3 4c4-1 7 0 9 2 2-2 5-3 9-2v15c-4-1-7 0-9 2-2-2-5-3-9-2Z"/>',pose:'<circle cx="12" cy="5" r="2"/><path d="m5 9 7 2 7-2m-7 2v5m0 0-5 5m5-5 5 5"/>',plus:'<path d="M12 5v14M5 12h14"/>',pause:'<path d="M9 6v12m6-12v12"/>',stop:'<rect x="7" y="7" width="10" height="10" rx="1" fill="currentColor"/>',play:'<path d="m9 5 10 7-10 7Z"/>',refresh:'<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',close:'<path d="m6 6 12 12M6 18 18 6"/>'};
function icon(name){return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]||icons.capture}</svg>`}
const $=s=>document.querySelector(s);
document.querySelectorAll('[data-icon]').forEach(x=>x.innerHTML=icon(x.dataset.icon));
$('#libraryToggle').innerHTML=icon('sidebar');$('#radarMenuToggle').innerHTML=icon('chevron');
// This is an isolated interaction prototype. It never calls Gasp's APIs,
// opens a device, requests media permissions, or writes user recordings.
Object.assign(icons, {
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  gear: '<path d="m10 3-.6 2.2-2 .9-2-.7L3 9l1.7 1.5v2.8L3 15l2.4 3.6 2-.7 2 .9.6 2.2h4l.6-2.2 2-.9 2 .7L21 15l-1.7-1.7v-2.8L21 9l-2.4-3.6-2 .7-2-.9L14 3Z"/><circle cx="12" cy="12" r="3"/>',
  back: '<path d="M19 12H5m5-5-5 5 5 5"/>',
  stepBack: '<path d="M6 6v12m12-12-9 6 9 6Z"/>',
  stepForward: '<path d="M18 6v12M6 6l9 6-9 6Z"/>',
  radar: '<path d="M5 19a10 10 0 0 1 14-14M8 16a6 6 0 0 1 8-8m-4 4 7-7"/><circle cx="12" cy="12" r="2"/>',
});

const escapeHTML = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const steps = [
  {id:'calibration', title:'Personal calibration', time:'About 5 minutes', desc:'Find a clear signal and a comfortable position.', icon:'calibrate', detail:'A short reference for your placement, natural movement and articulation.', total:12, role:'Calibration', recipe:'12 guided checks · movement, sounds and short sentences'},
  {id:'first-speech', title:'First speech', time:'About 25–35 minutes', desc:'Short phrases, then everyday sentences.', icon:'speech', detail:'Build your first speech dataset with short phrases and natural sentences, aloud and silently.', total:220, role:'Training', recipe:'8 repeated phrases · 60 sentence pairs · 12 movement controls'},
  {id:'return-repeat', title:'Return & repeat', time:'About 15–25 minutes', desc:'A fresh sitting, with new sentences.', icon:'refresh', detail:'Return to your setup for a fresh benchmark and a new set of sentences.', total:120, role:'Development', recipe:'8 repeated phrases · 30 new sentence pairs · 12 movement controls'},
  {id:'independent-check', title:'Independent check', time:'About 15–25 minutes', desc:'Set aside a fresh sample to measure progress.', icon:'check', detail:'A fresh sitting kept apart for a future model evaluation.', total:120, role:'Final test', recipe:'8 repeated phrases · 30 new sentence pairs · 12 movement controls'},
];
const templates = [
  {id:'reader', title:'Read a book', icon:'book', description:'Long text, one passage at a time.', example:'The Odyssey', label:'Text to read', placeholder:'Paste a chapter or passage…', detail:'Read aloud, then mouth the same passage silently. Keep your place between sessions.'},
  {id:'phrases', title:'Words & phrases', icon:'speech', description:'A repeatable set of short prompts.', example:'Desk commands', label:'Prompts · one per line', placeholder:'Open the document\nMove to the next page', detail:'One phrase at a time, with an aloud reference followed by silent repetitions.'},
  {id:'sentences', title:'Sentence practice', icon:'speech', description:'Natural language in short sessions.', example:'Everyday conversations', label:'Sentences · one per line', placeholder:'Please put the blue mug beside my keyboard.', detail:'Read each sentence aloud, then silently. Review in small groups.'},
  {id:'pose', title:'Position study', icon:'pose', description:'The same speech at different positions.', example:'Desk distance study', label:'Shared prompts · one per line', placeholder:'Please put the blue mug beside my keyboard.', detail:'Repeat a shared prompt set at each measured distance. Each position is saved with its recordings.'},
  {id:'free', title:'Free capture', icon:'mic', description:'Your own words, at your own pace.', example:'Morning notes', detail:'Record aloud with a reference microphone, then review the transcript.'},
];

// Definitions are copied once into each session. User edits below apply only
// to future setup snapshots; no control mutates an existing recipe.
const makeDefinition = (id, title, template, content='') => Object.freeze({id, title, template, content, version:1});
let collections = steps.map(s => makeDefinition(s.id, s.title, 'baseline'));
let state = {done:0, screen:'home', collection:'calibration', connected:false, library:false, sessions:[], session:null, recording:false, seconds:0, previewMode:'new'};
let preferences = {person:'Boyd', location:'Home desk', distance:45, enclosure:'Desktop enclosure', mount:'Fixed stand', yaw:'', pitch:'', roll:'', source:'usb', profile:'complex', mic:'MacBook microphone'};
let clockTimer = null, previewRAF = null, reviewRAF = null, reviewModel = null, builderTemplate = null, dialogReturn = null;
const currentCollection = () => collections.find(c => c.id===state.collection);
const baselineStep = () => steps.findIndex(s => s.id===state.collection);
const templateFor = c => templates.find(t => t.id===c.template);
const collectionIcon = c => steps.find(s=>s.id===c.id)?.icon || templateFor(c)?.icon || 'speech';
const collectionDescription = c => steps.find(s=>s.id===c.id)?.detail || templateFor(c)?.detail || '';
const sessionCount = c => state.sessions.filter(s=>s.collectionId===c.id).length;
const currentSession = () => state.sessions.find(s=>s.id===state.session);

function cancelAnimations() {
  clearInterval(clockTimer);
  cancelAnimationFrame(reviewRAF);
  if (reviewModel) reviewModel.playing=false;
}
function setScreen(screen) {
  cancelAnimations(); state.recording=false; state.screen=screen;
  $('#main').scrollTop=0;
  render();
}
function breadcrumb() {
  const root='<button data-action="home">Capture</button>';
  const c=currentCollection();
  let path='Capture';
  if (state.screen==='builder') path=root+'<span class="slash">/</span><span>New type</span>';
  else if (['detail','setup','record','review','completion'].includes(state.screen)) {
    path=root+'<span class="slash">/</span><button class="type-crumb" data-action="detail">'+escapeHTML(c.title)+'</button>';
    if (['setup','record','review'].includes(state.screen)) path+='<span class="slash">/</span><span>'+({setup:'Setup',record:'Record',review:'Review'})[state.screen]+'</span>';
  } else if (['training','dictation'].includes(state.screen)) path=state.screen==='training'?'Training':'Dictation';
  $('#breadcrumbs').innerHTML=path;
  document.querySelectorAll('.rail .nav-item').forEach(b=>b.classList.toggle('current', b.dataset.action===(['training','dictation'].includes(state.screen)?state.screen:'home')));
}
function home() {
  if (state.done<4) return `<div class="intro flex home-heading between"><div><div class="eyebrow">Your baseline</div><h1>Start with a clear signal.</h1><p>Four steps to build your first dataset. Save and return anytime.</p></div><div class="baseline-progress"><small>${state.done} of 4 complete</small><div class="progress-indicator">${steps.map((_,i)=>`<span class="${i<state.done?'filled':''}"></span>`).join('')}</div></div></div>
    <div class="journey">${steps.map((s,i)=>`<button class="journey-card ${i===state.done?'active':i<state.done?'done':'locked'}" data-collection="${s.id}" ${i>state.done?'disabled':''}><span class="journey-number">${i<state.done?icon('check'):String(i+1).padStart(2,'0')}</span><span><h3>${s.title}</h3><p>${i===state.done?s.desc:s.time}</p></span><span class="start">${i===state.done?(i?'Continue':'Begin')+icon('arrow'):i<state.done?'View '+icon('chevron'):icon('lock')}</span></button>`).join('')}</div>
    <p class="baseline-note">${icon('clock')} Plan for 60–90 minutes across three sittings.</p>`;
  const custom=collections.filter(c=>c.template!=='baseline');
  return `<div class="intro flex between home-heading"><div><div class="eyebrow">Capture</div><h1>Your collections.</h1><p>Pick up where you left off, or begin something new.</p></div><button class="secondary" data-action="builder">${icon('plus')} New type</button></div>
    <div class="cards">${custom.map(c=>`<button class="type-card" data-collection="${c.id}"><div class="flex between"><span class="glyph">${icon(collectionIcon(c))}</span>${icon('arrow')}</div><span class="card-kind">${escapeHTML(templateFor(c).title)}</span><h3>${escapeHTML(c.title)}</h3><p>${sessionCount(c)} ${sessionCount(c)===1?'session':'sessions'}${c.template==='reader'?' · Your place is saved':''}</p></button>`).join('')}
    ${custom.length?'':`<button class="type-card new-type-card" data-action="builder"><span class="glyph">${icon('plus')}</span><h3>Create your first collection</h3><p>A book, a phrase list, or something of your own.</p></button>`}</div>
    <div class="baseline-archive"><h3 class="section-label">Your baseline <span class="pill">Collected</span></h3>${steps.map(s=>`<button class="baseline-row" data-collection="${s.id}"><span class="flex">${icon(s.icon)}${s.title}</span><span class="muted">${sessionCount(collections.find(c=>c.id===s.id))} session ${icon('arrow')}</span></button>`).join('')}</div>`;
}
function collectionMenu() {
  return '<div class="collection-menu"><button class="icon-button" data-action="collection-menu" aria-label="Collection actions" aria-expanded="false">'+icon('more')+'</button><div class="menu hidden" id="collectionMenu"><button data-action="definition">View collection definition</button></div></div>';
}
function detail() {
  const c=currentCollection(), index=baselineStep(), s=steps[index], sessions=state.sessions.filter(x=>x.collectionId===c.id);
  const incomplete=sessions.find(x=>x.captured<x.total);
  return `<header class="collection-heading"><div class="type-title"><div class="type-symbol">${icon(collectionIcon(c))}</div><div><div class="eyebrow muted">${s?'Baseline · '+(index+1)+' of 4':escapeHTML(templateFor(c).title)}</div><h1>${escapeHTML(c.title)}</h1><p>${escapeHTML(collectionDescription(c))}</p></div></div>${collectionMenu()}</header>
    <div class="collection-start"><button class="primary" data-action="${incomplete?'resume':'setup'}" ${incomplete?`data-resume="${incomplete.id}"`:''}>${incomplete?'Resume session':'Start session'} ${icon('arrow')}</button>${s?`<span class="muted">${s.time}</span>`:''}</div>
    <div class="sessions-heading flex between"><h3>Sessions</h3><span class="muted">${sessions.length}</span></div>
    ${sessions.length?`<div class="session-rows">${sessions.map(x=>`<div class="session-row"><div><strong>${escapeHTML(x.name)}</strong><small>${escapeHTML(x.date)} · ${escapeHTML(x.setup?.location||preferences.location)}</small></div><div class="session-meta"><span>${x.captured} ${x.captured===1?'take':'takes'}</span><small>${x.reviewed?'Reviewed':'Needs review'}</small></div><button class="secondary compact" data-session="${x.id}">Open ${icon('arrow')}</button></div>`).join('')}</div>`:'<div class="empty-state"><span class="empty-icon">'+icon('capture')+'</span><p>Your first session starts here.</p><small>Record, review, then return whenever you’re ready.</small></div>'}`;
}
function definition() {
  const c=currentCollection(), s=steps[baselineStep()], t=templateFor(c);
  const rows=s?[['Collection',s.recipe],['Purpose',s.role],['Speech',s.id==='calibration'?'Guided sounds and movement':'Aloud references and silent speech'],['Review','Short groups of takes']]:[['Template',t.title],['Speech',c.template==='free'?'Aloud with reference audio':'Aloud reference, then silent'],['Content',c.template==='free'?'Spontaneous speech':c.content.split(/\s+/).filter(Boolean).length+' words'],['Review','Between passages or groups of takes']];
  if(c.source)rows.push(['Source',c.source]);
  if(c.positions)rows.push(['Distances',c.positions+' cm']);
  dialog('Collection definition',`<p>${escapeHTML(c.title)} <span class="pill">Version ${c.version} · Read-only</span></p><dl class="definition-list">${rows.map(([k,v])=>`<div><dt>${k}</dt><dd>${escapeHTML(v)}</dd></div>`).join('')}</dl><p class="dialog-note">Every session keeps this definition. A different recipe starts a new collection type.</p>${c.content?'<details class="definition-text"><summary>Source text</summary><p>'+escapeHTML(c.content)+'</p></details>':''}<div class="actions"><button class="secondary" data-action="close-modal">Done</button></div>`);
}

const placementGraphic = `<svg viewBox="0 0 200 160" aria-hidden="true"><path d="M24 129h153M62 128V83c0-10 7-14 15-14h23m-13 0v-8m0 0c-17 0-25-11-25-28 0-20 13-30 29-24 11 4 17 13 17 26l7 9-10 3v10H87m26-7 41 5m-40-5 40 11M80 87v21h36v20m36-68 10-24 16 7-10 24-16-7Zm8 4v45m-10 0h25m-32-31h37"/><path stroke-dasharray="3 4" d="M112 93h35"/><path d="m116 90-4 3 4 3m27-6 4 3-4 3"/></svg>`;
function setup() {
  const p=preferences;
  return `<div class="intro"><div class="eyebrow">Before you record</div><h1>Make yourself comfortable.</h1><p>Confirm your usual setup, then you’re ready.</p></div><div class="setup-layout"><div class="placement">${placementGraphic}<p>Same desk. Natural posture.<br>A clear view of your face.</p><button class="secondary compact" data-action="start-preview">${icon('radar')} Start preview</button></div><div class="setup-summary"><div class="device-row"><div class="flex"><span class="dot ${state.connected?'green':'red'}"></span><div><strong>Radar</strong><small>${state.connected?'Demo radar connected':'Not connected'} · ${p.source==='usb'?'USB':'DCA1000'}</small></div></div><button class="icon-button" data-action="device" aria-label="Radar settings">${icon('gear')}</button></div><div class="device-row"><div class="flex">${icon('mic')}<div><strong>Reference microphone</strong><small>${escapeHTML(p.mic)}</small></div></div><button class="icon-button" data-action="microphone" aria-label="Microphone settings">${icon('gear')}</button></div><div class="saved-setup"><div class="flex between"><span class="eyebrow muted">Saved setup</span><button class="text-button" data-action="settings">Edit in Settings ${icon('arrow')}</button></div><div class="setup-person"><strong>${escapeHTML(p.person)}</strong><span>${escapeHTML(p.location)}</span></div><p>${escapeHTML(p.enclosure)} · ${escapeHTML(p.mount)}</p></div><label class="distance-field">Face to radar <span class="unit-input"><input id="setupDistance" type="number" value="${p.distance}" min="10" max="300" aria-label="Face to radar in centimeters"><span>cm</span></span></label></div></div>${baselineStep()>1?'<p class="return-note">For this sitting, step away and reseat before you begin.</p>':''}<div class="setup-footer"><button class="text-button" data-action="detail">${icon('back')} Back</button><button class="primary" data-action="enter-recorder">Enter recorder ${icon('arrow')}</button></div>`;
}
function settings() {
  dialog('Your setup',`<p>Used for new sessions. Existing recordings keep their original setup.</p><form id="setupForm"><div class="field-pair"><label>Person<input name="person" value="${escapeHTML(preferences.person)}" required maxlength="80"></label><label>Location<input name="location" value="${escapeHTML(preferences.location)}" required maxlength="120"></label></div><div class="field-pair"><label>Enclosure<select name="enclosure">${['Desktop enclosure','Open board','Custom enclosure'].map(x=>`<option ${x===preferences.enclosure?'selected':''}>${x}</option>`).join('')}</select></label><label>Mount<input name="mount" value="${escapeHTML(preferences.mount)}" maxlength="120"></label></div><label>Usual face-to-radar distance · cm<input name="distance" type="number" min="10" max="300" value="${preferences.distance}" required></label><details class="advanced-settings"><summary>Orientation</summary><div class="field-triple">${['yaw','pitch','roll'].map(x=>`<label>${x[0].toUpperCase()+x.slice(1)} · degrees<input name="${x}" type="number" min="-180" max="180" value="${preferences[x]}" placeholder="Unknown"></label>`).join('')}</div></details><div class="settings-links"><button type="button" data-action="device">${icon('radar')} Radar ${icon('chevron')}</button><button type="button" data-action="microphone">${icon('mic')} Reference microphone ${icon('chevron')}</button></div><div class="actions"><button type="button" class="secondary" data-action="close-modal">Cancel</button><button class="primary" type="submit">Save setup</button></div></form>`);
  $('#setupForm').onsubmit=e=>{
    e.preventDefault();
    const data=Object.fromEntries(new FormData(e.target));
    if (!data.person.trim() || !data.location.trim()) return;
    preferences={...preferences,...data,person:data.person.trim(),location:data.location.trim(),distance:Number(data.distance)};
    closeDialog(); if(state.screen==='setup')render();
  };
}
function microphone() {
  dialog('Reference microphone',`<p>Audio helps review aloud speech. Silent takes keep their intended text separately.</p><label>Input<select id="microphoneInput"><option>MacBook microphone</option><option>External microphone · example</option></select></label><p class="dialog-note">Design preview · no microphone is accessed.</p><div class="actions"><button class="primary" data-action="save-microphone">Done</button></div>`);
  $('#microphoneInput').value=preferences.mic;
}

function dialog(title,body,wide=false) {
  cancelAnimationFrame(previewRAF); previewRAF=null;
  dialogReturn=document.activeElement;
  $('#modal').classList.toggle('wide',wide);
  $('#modal').innerHTML=`<div class="dialog-heading flex between"><h2 id="dialogTitle">${title}</h2><button class="icon-button" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button></div>${body}`;
  $('#modal').setAttribute('aria-labelledby','dialogTitle');
  if (!$('#modal').open) $('#modal').showModal();
}
function closeDialog() {
  cancelAnimationFrame(previewRAF);previewRAF=null;
  $('#modal').close();
  if (dialogReturn?.isConnected) dialogReturn.focus();
}
$('#modal').addEventListener('close',()=>{cancelAnimationFrame(previewRAF);previewRAF=null;deviceView.running=false;if(state.screen==='setup')render();});

function updateConnection() {
  $('#radarStatus').innerHTML=`<span class="dot ${state.connected?'green':'red'}"></span><span>${state.connected?'Demo radar connected':'Radar disconnected'}</span>`;
  $('#radarMenu').innerHTML=`<button data-action="device">Radar settings…</button><button data-action="connect">${state.connected?'Disconnect demo radar':'Connect demo radar'}</button>`;
}
function toggleConnection() {
  state.connected=!state.connected;updateConnection();closeMenus();
  if ($('#modal').open) device(false);
  if (state.screen==='setup') render();
}
function closeMenus() {
  document.querySelectorAll('.menu').forEach(m=>m.classList.add('hidden'));
  document.querySelectorAll('[aria-expanded="true"]').forEach(b=>{if(b.id!=='libraryToggle')b.setAttribute('aria-expanded','false');});
}

function device(autoStart=false) {
  const p=preferences;
  dialog('Radar settings',`<div class="radar-settings-layout"><section class="position-preview"><div class="preview-heading flex between"><span class="eyebrow">Positioning preview</span><span class="pill">Simulated</span></div><div class="view-switch" role="group" aria-label="Position view"><button data-position-view="range" aria-pressed="true">Range</button><button data-position-view="top" aria-pressed="false">Top</button><button data-position-view="side" aria-pressed="false">Side</button><button data-position-view="spatial" aria-pressed="false">3D</button></div><div class="position-canvas"><canvas id="positionCanvas" aria-label="Simulated radar positioning display"></canvas><div id="previewCover"><span>${icon('radar')}</span><p>Check your position.</p><button class="secondary compact" data-action="toggle-preview">Start preview</button></div></div><div class="position-readout"><span id="positionHint">Range shows how far reflections are from the radar.</span><button class="text-button hidden" id="stopPreview" data-action="toggle-preview">Stop preview</button></div><p class="dialog-note">Reflections are not face detections. The dashed marker is your saved distance.</p></section><section class="device-options"><label>Connection<select id="deviceSource"><option value="usb">USB · radar to Mac</option><option value="dca">DCA1000 · capture board</option></select></label><p id="sourceHelp">USB sends radar commands and compact measurements over the cable.</p><label>Radar profile<select id="deviceProfile"><option value="complex">Complex signal · speech collection</option><option value="spatial">Spatial preview · positioning only</option></select></label><p id="profileHelp">Preserves phase changes for speech. Distance preview is available.</p><details class="advanced-settings"><summary>Connection details</summary><label>Command port<select><option>Automatic · demo port</option></select></label><p>Sends instructions to the radar. It is separate from the measurement stream.</p><label id="streamLabel">Data port<select><option>Automatic · demo data port</option></select></label><p id="streamHelp">Receives measurements. Choose ports manually only if automatic detection fails.</p></details><div class="connection-footer"><span class="flex"><span class="dot ${state.connected?'green':'red'}"></span>${state.connected?'Demo connected':'Disconnected'}</span><button class="secondary compact" data-action="connect">${state.connected?'Disconnect':'Connect demo'}</button></div></section></div>` ,true);
  $('#deviceSource').value=p.source;$('#deviceProfile').value=p.profile;
  deviceView={view:'range',running:false,start:0};
  $('#deviceSource').onchange=()=>{preferences.source=$('#deviceSource').value;updateDeviceOptions();};
  $('#deviceProfile').onchange=()=>{preferences.profile=$('#deviceProfile').value;updateDeviceOptions();};
  updateDeviceOptions();
  if(autoStart) togglePreview();
}
let deviceView={view:'range',running:false,start:0};
function updateDeviceOptions() {
  const dca=preferences.source==='dca', spatial=preferences.profile==='spatial'&&!dca;
  if(dca){preferences.profile='complex';$('#deviceProfile').value='complex';}
  $('#deviceProfile').options[1].disabled=dca;
  $('#sourceHelp').textContent=dca?'DCA1000 receives raw radar samples over Ethernet. USB still carries commands.':'USB sends radar commands and compact measurements over the cable.';
  $('#profileHelp').textContent=spatial?'Produces spatial detections for positioning. Switch back to the collection profile before recording.':dca?'Raw samples retain information for later processing. Spatial calibration is required before a live 3D view.':'Preserves phase changes for speech. Distance preview is available.';
  $('#streamLabel').innerHTML=dca?'Capture address<input value="192.168.33.180" readonly aria-label="Demo capture address">':'Data port<select><option>Automatic · demo data port</option></select>';
  $('#streamHelp').textContent=dca?'Ethernet receiver on the Mac. These are illustrative settings.':'Receives measurements. Choose ports manually only if automatic detection fails.';
  for(const b of document.querySelectorAll('[data-position-view]')) {
    b.disabled=b.dataset.positionView!=='range'&&!spatial;
    b.title=b.disabled?'Requires the spatial preview profile':'';
  }
  if(!spatial)deviceView.view='range';
  selectPositionView(deviceView.view);
}
function selectPositionView(view) {
  deviceView.view=view;
  document.querySelectorAll('[data-position-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.positionView===view)));
  $('#positionHint').textContent=view==='range'?'Range · compare the reflection peak with your measured distance.':view==='side'?'Side view · reflections above and below the radar.':view==='top'?'Top view · reflections left and right of the radar.':'3D · fixed view of spatial reflections.';
  drawPosition(0);
}
function togglePreview() {
  deviceView.running=!deviceView.running;deviceView.start=performance.now();
  $('#previewCover').hidden=deviceView.running;$('#stopPreview').classList.toggle('hidden',!deviceView.running);
  cancelAnimationFrame(previewRAF);
  if(deviceView.running) {
    function tick(now){if(!deviceView.running||!$('#modal').open)return;drawPosition((now-deviceView.start)/1000);previewRAF=requestAnimationFrame(tick);}
    previewRAF=requestAnimationFrame(tick);
  }
}

function drawingCanvas(id,height) {
  const el=$(id);if(!el)return null;
  const w=Math.max(1,el.clientWidth),h=height||el.clientHeight,dpr=window.devicePixelRatio||1;
  if(el.width!==Math.round(w*dpr)||el.height!==Math.round(h*dpr)){el.width=Math.round(w*dpr);el.height=Math.round(h*dpr);}
  const ctx=el.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);ctx.font='10px -apple-system, sans-serif';
  return {ctx,w,h};
}
function linePath(ctx,points,color='#333',width=1.3) {
  ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.stroke();
}
function drawPosition(time) {
  const surface=drawingCanvas('#positionCanvas');if(!surface)return;
  const {ctx,w,h}=surface, view=deviceView.view;
  const range=preferences.distance/100, motion=.012*Math.sin(time*2.5), actual=range+motion;
  const left=42,right=w-24,top=24,bottom=h-35;
  ctx.fillStyle='#fafafa';ctx.fillRect(0,0,w,h);
  ctx.strokeStyle='#e7e7e7';ctx.lineWidth=1;
  for(let i=0;i<=4;i++){const y=top+i*(bottom-top)/4;linePath(ctx,[[left,y],[right,y]],'#e7e7e7',1);}
  if(view==='range') {
    const maxRange=Math.max(1.2,range*1.6),x=r=>left+r/maxRange*(right-left);
    for(let i=0;i<=4;i++){ctx.fillStyle='#888';ctx.fillText((i*maxRange/4).toFixed(1)+' m',x(i*maxRange/4)-9,bottom+20);}
    const pts=Array.from({length:220},(_,i)=>{const r=i/219*maxRange,amp=.06+.65*Math.exp(-1*((r-actual)/.045)**2)+.18*Math.exp(-1*((r-.77)/.08)**2)+.018*Math.sin(i*3.4+time);return[x(r),bottom-amp*(bottom-top)];});
    ctx.setLineDash([4,4]);linePath(ctx,[[x(range),top],[x(range),bottom]],'#888',1);ctx.setLineDash([]);
    linePath(ctx,pts,'#292929',1.7);ctx.fillStyle='#666';ctx.fillText('Saved distance · '+preferences.distance+' cm',clamp(x(range)-50,8,w-145),17);
    ctx.fillText('Reflection strength',left,top+18);
  } else {
    const cx=w/2,cy=h-42,scale=Math.min(w/1.5,h/1.1),maxDepth=Math.max(.95,range*1.35);
    const project=(x,y,z)=>view==='top'?[cx+x*scale,cy-y/maxDepth*(h-72)]:view==='side'?[left+y/maxDepth*(w-75),h/2-z*scale]:[cx+(x*.85-y*.3)*scale,cy-(y*.53+z*.7)*scale];
    for(let d=.2;d<maxDepth;d+=.2){linePath(ctx,[project(-.3,d,0),project(.3,d,0)],'#ddd',1);const label=project(.32,d,0);ctx.fillStyle='#999';ctx.fillText(d.toFixed(1)+' m',label[0],label[1]);}
    for(let x=-.3;x<=.3;x+=.1)linePath(ctx,[project(x,0,0),project(x,maxDepth,0)],'#e5e5e5',1);
    ctx.setLineDash([4,4]);linePath(ctx,[project(-.18,range,0),project(.18,range,0)],'#888',1);ctx.setLineDash([]);
    for(let i=0;i<40;i++){
      const a=i*2.399,spread=.025+.045*(i%9)/9;
      const [x,y]=project(Math.cos(a)*spread+.012*Math.sin(time),actual+Math.sin(a)*spread,Math.sin(i*1.2)*spread);
      ctx.fillStyle=i%4?'#555':'#999';ctx.beginPath();ctx.arc(x,y,i%3?2:2.8,0,Math.PI*2);ctx.fill();
    }
    const origin=project(0,0,0);ctx.fillStyle='#222';ctx.fillRect(origin[0]-6,origin[1]-3,12,6);ctx.fillStyle='#777';ctx.fillText('Radar',origin[0]-15,origin[1]+19);
    ctx.fillText(view==='side'?'Height ↑   Distance →':view==='top'?'Left ←   → Right':'Lateral / distance / height',left,17);
    if(view==='side') {linePath(ctx,[[left,h/2],[right,h/2]],'#ccc',1);ctx.fillText('Radar height',left,h/2+16);}
  }
}

const calibrationCues=[
  ['Sit comfortably and stay still.','Rest',8],['Slowly open and close your jaw three times.','Movement reference',8],['Round your lips, then relax. Repeat three times.','Movement reference',8],['Say “pa, ta, ka” at a comfortable pace.','Speak aloud',8],['Say “ma, na, ng” at a comfortable pace.','Speak aloud',8],['Say “fa, sa, sha” at a comfortable pace.','Speak aloud',8],['Say “ah, ee, oo” at a comfortable pace.','Speak aloud',8],['Please put the blue mug beside my keyboard.','Speak aloud',8],['Could we move our meeting to tomorrow?','Speak aloud',8],['The package should arrive before Friday.','Speak aloud',8],['Turn your head gently left, then right.','Movement reference',8],['Swallow once, then rest.','Movement reference',6],
];
function cueFor(session) {
  const c=session.definition,n=session.cursor||0;
  if(c.id==='calibration') {const [text,mode,duration]=calibrationCues[n%calibrationCues.length];return {text,mode,duration};}
  if(c.template==='baseline') {
    const samples=['Please put the blue mug beside my keyboard.','Could we move our meeting to tomorrow?','The package should arrive before Friday.'];
    return {text:samples[Math.floor(n/2)%3],mode:n%2?'Mouth silently':'Speak aloud',duration:8};
  }
  if(c.template==='free')return{text:'Speak in your own words.',mode:'Speak aloud',duration:60};
  const lines=c.template==='reader'?c.content.match(/[^.!?]+[.!?]+|[^.!?]+$/g):c.content.split('\n').filter(Boolean);
  const cue={text:(lines[Math.floor(n/2)%lines.length]||c.content).trim(),mode:n%2?'Mouth silently':'Speak aloud',duration:c.template==='reader'?30:8};
  if(c.template==='pose'){
    const positions=c.positions.split(',').map(Number),index=Math.min(positions.length-1,Math.floor(n/(lines.length*2)));
    cue.position={distance_cm:positions[index],index:index+1,count:positions.length};
  }
  return cue;
}
function enterRecorder(resume=false) {
  if($('#setupDistance')) {
    if(!$('#setupDistance').reportValidity())return;
    preferences.distance=Number($('#setupDistance').value);
  }
  if(!resume) {
    const c=currentCollection(),s=steps[baselineStep()];
    const total=s?.total||(c.template==='free'?1:Math.max(2,(c.template==='reader'?(c.content.match(/[.!?]+/g)||['']).length:c.content.split('\n').filter(Boolean).length)*2*(c.template==='pose'?c.positions.split(',').length:1)));
    const session={id:'preview-'+Date.now(),collectionId:c.id,definition:structuredClone(c),setup:structuredClone(preferences),name:'Session '+(sessionCount(c)+1),date:'Preview · just now',captured:0,total,cursor:0,takes:[],reviewed:false};
    state.sessions.push(session);state.session=session.id;
  }
  state.recording=false;state.seconds=0;setScreen('record');
}
function record() {
  const session=currentSession();if(!session)return '';
  const cue=cueFor(session),reader=session.definition.template==='reader'||session.definition.template==='free';
  return `<header class="record-head flex between"><div><strong>${escapeHTML(currentCollection().title)}</strong><span class="muted"> · ${session.cursor+1} of ${session.total} steps</span></div><button class="text-button" data-action="detail">Finish for now</button></header><div class="record-progress"><span style="width:${session.cursor/session.total*100}%"></span></div><div class="record-studio"><img class="logo" src="../../gasp/static/brand/face-open.png" alt="Gasp"><div class="mode">${cue.mode}</div>${cue.position?`<p class="position-cue">${cue.position.distance_cm} cm from the radar · Position ${cue.position.index} of ${cue.position.count}</p>`:''}<div class="record-prompt">${escapeHTML(cue.text)}</div><p class="record-help">${reader?'Press Space to start. Press again to finish.':'Hold Space to record. Release when you finish.'}</p><div class="transport"><span id="recordDot" class="dot"></span><span id="recordTime" class="time">00:00</span><button class="record-button" id="recordButton" aria-label="${reader?'Start recording':'Hold to record'}">${icon('mic')}</button></div><p id="recordTarget" class="record-target">${reader?'Read at your own pace':'Aim for about '+cue.duration+' seconds'}</p>${session.definition.id==='calibration'&&[1,2].includes(session.cursor)?'<button class="text-button motion-cue" data-action="motion-guide">Watch the movement</button>':''}</div>`;
}
function startRecording() {
  if(state.screen!=='record'||state.recording||$('#modal').open)return;
  state.recording=true;state.seconds=0;
  $('#recordButton').classList.add('recording');$('#recordButton').innerHTML=icon('stop');$('#recordDot').classList.add('red');
  const started=performance.now(),cue=cueFor(currentSession());
  clockTimer=setInterval(()=>{state.seconds=(performance.now()-started)/1000;$('#recordTime').textContent=formatClock(state.seconds);$('#recordTarget').textContent=['reader','free'].includes(currentCollection().template)?'Read at your own pace':state.seconds>=cue.duration?'Finish whenever you’re ready.':Math.ceil(cue.duration-state.seconds)+' seconds remaining';},100);
}
function finishRecording() {
  if(!state.recording)return;
  state.recording=false;clearInterval(clockTimer);
  const session=currentSession(),cue=cueFor(session);
  const take={text:cue.text,mode:cue.mode,duration:Math.max(.6,Math.round(state.seconds*20)/20),cursor:session.cursor,reviewed:false,position:cue.position};
  session.takes=session.takes.filter(t=>t.cursor!==session.cursor);session.takes.push(take);session.captured=Math.max(session.captured,session.cursor+1);
  openReview(take,true);
}
function formatClock(t){return String(Math.floor(t/60)).padStart(2,'0')+':'+String(Math.floor(t%60)).padStart(2,'0');}
function formatTimestamp(t){const cs=Math.round(t*100);return formatClock(Math.floor(cs/100))+'.'+String(cs%100).padStart(2,'0');}

// All replay views use one timebase. Historical tracks remain still while the
// shared playhead and current-frame inspector move, as in an editing timeline.
function openReview(take,fromRecorder=false) {
  const voiced=take.mode==='Speak aloud',movement=['Movement reference','Rest'].includes(take.mode);
  const text=movement?[]:take.text.replace(/[.,?!]/g,'').split(/\s+/).filter(Boolean);
  const duration=take.duration||6,pad=Math.min(.5,duration*.1),unit=(duration-2*pad)/Math.max(1,text.length);
  reviewModel={take,fromRecorder,voiced,movement,duration,time:0,playing:false,zoom:1,speed:1,inspector:'iq',selected:-1,dirty:false,undo:[],
    words:take.words?structuredClone(take.words):text.map((word,i)=>({text:word,start:pad+i*unit,end:pad+(i+.88)*unit})),channels:{audio:true,phase:true,range:true},last:0};
  if(!take.signalWords)take.signalWords=structuredClone(reviewModel.words);
  reviewModel.signalWords=structuredClone(take.signalWords);
  setScreen('review');
}
function review() {
  const r=reviewModel;
  return `<header class="review-heading"><div><div class="eyebrow muted">${escapeHTML(currentCollection().title)}</div><h1>Review your take.</h1></div><span class="pill">${r.take.mode}</span></header>
    <div class="review-intro"><div class="transcript-panel"><span class="eyebrow muted">${r.movement?'Task':'Reviewed text'}</span><p class="review-transcript" id="reviewTranscript">${r.movement?escapeHTML(r.take.text):r.words.map((w,i)=>`<button data-word="${i}">${escapeHTML(w.text)}</button>`).join(' ')}</p><div class="review-status" id="timingStatus">${r.movement?'Use the signal to check your movement.':r.voiced?'Illustrative word timing · drag an edge to adjust.':'Silent timing must be reviewed separately from the aloud reference.'}</div></div><div class="frame-inspector"><div class="flex between"><label class="sr-only" for="frameView">Frame view</label><select id="frameView"><option value="iq">I / Q / time</option><option value="range">Range profile</option><option value="motion">Motion illustration</option></select><span id="frameTime">0.00 s</span></div><canvas id="frameCanvas" aria-label="Simulated current radar frame"></canvas><small id="frameCaption">Selected range bin · past 2 seconds</small></div></div>
    <section class="editor" aria-label="Synchronized recording editor"><div class="editor-toolbar"><div class="flex transport-controls"><button class="icon-button" data-action="rewind" aria-label="Return to start">${icon('stepBack')}</button><button class="play-control" id="playToggle" data-action="play" aria-label="Play">${icon('play')}</button><button class="icon-button" data-action="next-frame" aria-label="Next frame">${icon('stepForward')}</button><output id="playTime">00:00.00 <span>/ 00:06.00</span></output></div><div class="flex editor-options"><label class="sr-only" for="playSpeed">Playback speed</label><select id="playSpeed" aria-label="Playback speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="1.5">1.5×</option></select><label class="sr-only" for="timelineZoom">Timeline zoom</label><select id="timelineZoom"><option value="1">Fit</option><option value="2">2× zoom</option><option value="4">4× zoom</option></select><div class="channel-menu"><button class="secondary compact" data-action="channels" aria-expanded="false">Channels ${icon('chevron')}</button><div class="menu hidden" id="channelMenu">${['audio','phase','range'].map(k=>`<label><input type="checkbox" data-channel="${k}" checked>${{audio:'Reference audio',phase:'Complex phase',range:'Range–time'}[k]}</label>`).join('')}</div></div></div></div>
      <div class="channel-layout"><div class="track-labels"><div class="track-label ruler-label">Time</div><div class="track-label audio-track" data-lane="audio"><strong>Audio</strong><small>${r.voiced?'Reference':'No speech audio'}</small></div><div class="track-label words-track"><strong>${r.movement?'Task':'Words'}</strong><small>${r.movement?'Reference':'Timing'}</small></div><div class="track-label phase-track" data-lane="phase"><strong>Phase</strong><small>0.45 m · RX 1</small></div><div class="track-label range-track" data-lane="range"><strong>Range</strong><small>0.2–0.8 m</small></div></div>
      <div class="timeline-scroll" id="timelineScroll" tabindex="0" aria-label="Timeline viewport"><div class="timeline-sheet" id="timelineSheet"><div class="time-ruler" id="timeRuler" role="slider" tabindex="0" aria-label="Playback position" aria-valuemin="0" aria-valuemax="${r.duration}" aria-valuenow="0"></div><div class="track audio-track" data-lane="audio"><canvas id="audioTrack" aria-label="Simulated reference audio waveform"></canvas>${!r.voiced?'<span class="track-empty">'+(r.movement?'Movement reference · no spoken text':'Silent take · no reference speech')+'</span>':''}</div><div class="track words-track" id="wordTrack"></div><div class="track phase-track" data-lane="phase"><canvas id="phaseTrack" aria-label="Simulated complex phase over time"></canvas></div><div class="track range-track" data-lane="range"><canvas id="rangeTrack" aria-label="Simulated range amplitude over time"></canvas></div><div class="shared-playhead" id="sharedPlayhead"><span></span></div></div></div></div>
      <div class="editor-footer"><span id="wordSelection">${r.movement?'Click any track to scrub.':'Click a word to jump. Drag its edges to adjust.'}</span><button class="text-button" id="undoTiming" data-action="undo-timing" disabled>Undo</button></div></section>
      <div class="review-bottom"><span class="keyboard-hint"><kbd>Space</kbd> play / pause <span>·</span> <kbd>←</kbd><kbd>→</kbd> frame</span><div class="flex"><button class="secondary" data-action="retake">Retake</button><button class="primary" data-action="keep">${r.fromRecorder?'Keep & next':'Keep take'} ${icon('check')}</button></div></div>`;
}
function bindReview() {
  const r=reviewModel;
  $('#timelineZoom').onchange=()=>{
    r.zoom=Number($('#timelineZoom').value);$('#timelineSheet').style.width=(r.zoom*100)+'%';
    drawTracks();updatePlayhead(true);
  };
  $('#playSpeed').onchange=()=>r.speed=Number($('#playSpeed').value);
  $('#frameView').onchange=()=>{r.inspector=$('#frameView').value;drawFrame();};
  $('#timelineSheet').onpointerdown=timelinePointer;
  $('#timelineSheet').onkeydown=timelineKeyboard;
  $('#timelineSheet').onpointermove=timelineMove;
  $('#timelineSheet').onpointerup=endTimelineDrag;
  $('#timelineSheet').onpointercancel=endTimelineDrag;
  renderWordSpans();drawTracks();updatePlayhead();
}
function renderWordSpans() {
  const r=reviewModel;
  $('#wordTrack').innerHTML=r.movement?`<div class="task-span">${escapeHTML(r.take.text)}</div>`:r.words.map((w,i)=>`<div class="word-span" data-span="${i}" style="left:${w.start/r.duration*100}%;width:${(w.end-w.start)/r.duration*100}%"><button class="word-edge start" data-edge="start" data-index="${i}" aria-label="Start of ${escapeHTML(w.text)}, ${w.start.toFixed(2)} seconds"></button><button class="word-body" data-word="${i}" title="${escapeHTML(w.text)} · ${w.start.toFixed(2)}–${w.end.toFixed(2)} s">${escapeHTML(w.text)}</button><button class="word-edge end" data-edge="end" data-index="${i}" aria-label="End of ${escapeHTML(w.text)}, ${w.end.toFixed(2)} seconds"></button></div>`).join('');
  updatePlayhead();
}
function phaseAt(t) {return .45*Math.sin(t*3.4)+.14*Math.sin(t*10.8)+.07*Math.cos(t*22);}
function signalEnvelope(t) {
  const r=reviewModel;
  if(r.movement)return .15+.6*Math.sin(t*1.8)**2;
  return .025+r.signalWords.reduce((v,w)=>v+Math.exp(-1*((t-(w.start+w.end)/2)/((w.end-w.start)*.32))**2)*.65,0);
}
function drawTracks() {
  if(state.screen!=='review'||!reviewModel)return;
  const r=reviewModel, ticks=Math.max(1,Math.min(24,Math.round(r.duration*2)));
  $('#timeRuler').innerHTML=Array.from({length:ticks+1},(_,i)=>`<span style="left:${i/ticks*100}%">${(i/ticks*r.duration).toFixed(1)}<i></i></span>`).join('');
  for(const [name,id] of [['audio','#audioTrack'],['phase','#phaseTrack'],['range','#rangeTrack']]) {
    if(!r.channels[name])continue;
    const surface=drawingCanvas(id);if(!surface)continue;const{ctx,w,h}=surface;
    ctx.fillStyle=name==='range'?'#f5f5f5':'#fcfcfc';ctx.fillRect(0,0,w,h);
    for(let t=0;t<=r.duration;t+=.5)linePath(ctx,[[t/r.duration*w,0],[t/r.duration*w,h]],'#e9e9e9',1);
    if(name==='audio'&&r.voiced) {
      ctx.strokeStyle='#535353';ctx.lineWidth=1;
      ctx.beginPath();for(let i=0;i<w;i+=2){const t=i/w*r.duration,amp=(.25+.75*Math.abs(Math.sin(t*101)))*signalEnvelope(t)*h*.42;ctx.moveTo(i,h/2-amp);ctx.lineTo(i,h/2+amp);}ctx.stroke();
    } else if(name==='phase') {
      linePath(ctx,Array.from({length:Math.ceil(w)},(_,i)=>[i,h/2-phaseAt(i/w*r.duration)*h*.52]),'#414141',1.2);
    } else if(name==='range') {
      const rows=40,cols=Math.ceil(w/4);
      for(let i=0;i<cols;i++){const t=i/cols*r.duration,centre=.45+.015*phaseAt(t);for(let j=0;j<rows;j++){const distance=.2+j/rows*.6;const value=.72*Math.exp(-1*((distance-centre)/.027)**2)*(.5+.5*signalEnvelope(t))+.12*Math.exp(-1*((distance-.63)/.06)**2)+.025*(1+Math.sin(j*1.7+i*.7));const gray=Math.round(250-215*value);ctx.fillStyle=`rgb(${gray},${gray},${gray})`;ctx.fillRect(i*w/cols,j*h/rows,w/cols+1,h/rows+1);}}
    }
  }
  drawFrame();
}
function drawFrame() {
  if(state.screen!=='review'||!reviewModel)return;
  const surface=drawingCanvas('#frameCanvas');if(!surface)return;
  const {ctx,w,h}=surface,r=reviewModel,t=r.time;
  ctx.fillStyle='#fafafa';ctx.fillRect(0,0,w,h);ctx.fillStyle='#8a8a8a';
  if(r.inspector==='iq') {
    const project=(i,q,dt)=>[w*.55+(i*.72-dt*.35)*w*.27,h*.57-(q*.7+dt*.2)*h*.36];
    const o=project(0,0,0);
    for(const [point,label] of [[[1.3,0,0],'I'],[[0,1.3,0],'Q'],[[0,0,1.8],'Time']]){const end=project(...point);linePath(ctx,[o,end],'#ccc',1);ctx.fillText(label,end[0]+4,end[1]);}
    const start=Math.max(0,t-2),pts=Array.from({length:90},(_,i)=>{const ts=start+(t-start)*i/89,a=phaseAt(ts)*2.5;return project(Math.cos(a)*(.65+.15*Math.sin(ts*5)),Math.sin(a)*.8,(ts-t)/2);});
    linePath(ctx,pts,'#454545',1.5);ctx.fillStyle='#111';ctx.beginPath();ctx.arc(...pts.at(-1),4,0,Math.PI*2);ctx.fill();
    $('#frameCaption').textContent='Selected range bin · past 2 seconds';
  } else if(r.inspector==='range') {
    const left=24,bottom=h-23,right=w-17;
    linePath(ctx,[[left,15],[left,bottom],[right,bottom]],'#ddd',1);
    const pts=Array.from({length:160},(_,i)=>{const range=i/159,amp=.04+.73*Math.exp(-1*((range-(.45+.015*phaseAt(t)))/.025)**2)*(.5+.5*signalEnvelope(t))+.11*Math.exp(-1*((range-.63)/.06)**2);return[left+(right-left)*range,bottom-amp*(h-40)];});
    linePath(ctx,pts,'#333',1.5);ctx.fillText('0 m',left,bottom+15);ctx.fillText('1 m',right-15,bottom+15);
    $('#frameCaption').textContent='Reflection strength at this instant';
  } else {
    drawFace(ctx,w,h,.15+.85*signalEnvelope(t));
    $('#frameCaption').textContent='Illustration · not a reconstructed face';
  }
  $('#frameTime').textContent=t.toFixed(2)+' s';
}
function drawFace(ctx,w,h,opening) {
  const cx=w/2,cy=h*.47,s=Math.min(w*.3,h*.45),jaw=opening*9;
  ctx.strokeStyle='#666';ctx.lineWidth=1;
  const points=[[-.65,-.6],[-.45,-.95],[.45,-.95],[.65,-.6],[.7,.15],[.45,.65+jaw/s],[0,.85+jaw/s],[-.45,.65+jaw/s],[-.7,.15],[-.65,-.6]].map(([x,y])=>[cx+x*s,cy+y*s]);
  linePath(ctx,points,'#666',1);
  for(const row of [[[-.65,-.6],[0,-.45],[.65,-.6]],[[-.7,.15],[-.2,.1],[0,-.45],[.2,.1],[.7,.15]],[[-.7,.15],[-.24,.45],[0,.85+jaw/s],[.24,.45],[.7,.15]],[[-.45,-.95],[-.2,.1],[.45,.65+jaw/s]],[[.45,-.95],[.2,.1],[-.45,.65+jaw/s]]])linePath(ctx,row.map(([x,y])=>[cx+x*s,cy+y*s]),'#bbb',.8);
  linePath(ctx,[[-.48,-.3],[-.3,-.35],[-.18,-.28]].map(([x,y])=>[cx+x*s,cy+y*s]),'#555',1);
  linePath(ctx,[[.48,-.3],[.3,-.35],[.18,-.28]].map(([x,y])=>[cx+x*s,cy+y*s]),'#555',1);
  ctx.strokeStyle='#444';ctx.beginPath();ctx.ellipse(cx,cy+.43*s,.22*s,Math.max(1.5,opening*.12*s),0,0,Math.PI*2);ctx.stroke();
}
function motionGuide() {
  const cue=cueFor(currentSession());
  dialog('Movement guide',`<p>${escapeHTML(cue.text)}</p><canvas id="motionGuide" aria-label="Illustrated mouth opening and closing"></canvas><p class="dialog-note">Illustration · use a comfortable, natural movement.</p><div class="actions"><button class="secondary" data-action="replay-guide">Replay</button><button class="primary" data-action="close-modal">Ready</button></div>`);
  animateGuide();
}
function animateGuide() {
  cancelAnimationFrame(previewRAF);const start=performance.now();
  function tick(now) {
    if(!$('#modal').open||!$('#motionGuide'))return;
    const {ctx,w,h}=drawingCanvas('#motionGuide'),elapsed=Math.min(6,(now-start)/1000);
    drawFace(ctx,w,h,.08+.85*(.5-.5*Math.cos(elapsed*Math.PI)));
    if(elapsed<6)previewRAF=requestAnimationFrame(tick);
  }
  previewRAF=requestAnimationFrame(tick);
}
function setPlaybackTime(t,follow=false) {
  const r=reviewModel;if(!r)return;r.time=clamp(t,0,r.duration);updatePlayhead(follow);
}
function updatePlayhead(follow=false) {
  if(!$('#sharedPlayhead')||!reviewModel)return;
  const r=reviewModel,percent=r.time/r.duration*100;
  $('#sharedPlayhead').style.left=`clamp(0px, ${percent}%, calc(100% - 1px))`;
  $('#playTime').innerHTML=formatTimestamp(r.time)+' <span>/ '+formatTimestamp(r.duration)+'</span>';
  $('#timeRuler').setAttribute('aria-valuenow',r.time.toFixed(2));$('#timeRuler').setAttribute('aria-valuetext',r.time.toFixed(2)+' seconds');
  document.querySelectorAll('[data-span]').forEach(el=>{const i=Number(el.dataset.span),word=r.words[i];el.classList.toggle('active',r.time>=word.start&&r.time<=word.end);el.classList.toggle('selected',i===r.selected);});
  document.querySelectorAll('#reviewTranscript [data-word]').forEach(el=>{const word=r.words[Number(el.dataset.word)];el.classList.toggle('active',r.time>=word.start&&r.time<=word.end);});
  if(follow&&r.zoom>1){const scroller=$('#timelineScroll'),x=r.time/r.duration*$('#timelineSheet').clientWidth;if(x<scroller.scrollLeft||x>scroller.scrollLeft+scroller.clientWidth-18)scroller.scrollLeft=clamp(x-scroller.clientWidth*.25,0,scroller.scrollWidth-scroller.clientWidth);}
  const selected=r.words[r.selected];
  $('#wordSelection').textContent=selected?`${selected.text} · ${selected.start.toFixed(2)}–${selected.end.toFixed(2)} s · Drag edges or use ← →`:(r.movement?'Click any track to scrub.':'Click a word to jump. Drag its edges to adjust.');
  $('#undoTiming').disabled=!r.undo.length;
  drawFrame();
}
function pausePlayback() {
  if(!reviewModel)return;reviewModel.playing=false;cancelAnimationFrame(reviewRAF);
  if($('#playToggle')){$('#playToggle').innerHTML=icon('play');$('#playToggle').setAttribute('aria-label','Play');}
}
function togglePlayback() {
  const r=reviewModel;if(!r)return;
  if(r.playing){pausePlayback();return;}
  if(r.time>=r.duration)setPlaybackTime(0);
  r.playing=true;r.last=performance.now();$('#playToggle').innerHTML=icon('pause');$('#playToggle').setAttribute('aria-label','Pause');
  function tick(now){if(!r.playing||state.screen!=='review')return;const elapsed=Math.min(.15,(now-r.last)/1000);r.last=now;setPlaybackTime(r.time+elapsed*r.speed,true);if(r.time>=r.duration)pausePlayback();else reviewRAF=requestAnimationFrame(tick);}
  reviewRAF=requestAnimationFrame(tick);
}
let timelineDrag=null;
function timelineTime(e){const rect=$('#timelineSheet').getBoundingClientRect();return clamp((e.clientX-rect.left)/rect.width*reviewModel.duration,0,reviewModel.duration);}
function timelinePointer(e) {
  if(e.button!==0)return;
  pausePlayback();const edge=e.target.closest('[data-edge]'),word=e.target.closest('[data-word]');
  if(edge){const i=Number(edge.dataset.index);reviewModel.selected=i;reviewModel.undo.push(structuredClone(reviewModel.words));timelineDrag={edge:edge.dataset.edge,index:i};e.preventDefault();edge.focus();}
  else if(word){reviewModel.selected=Number(word.dataset.word);setPlaybackTime(reviewModel.words[reviewModel.selected].start);return;}
  else{timelineDrag={};setPlaybackTime(timelineTime(e));$('#timeRuler').focus();e.preventDefault();}
  $('#timelineSheet').setPointerCapture(e.pointerId);
}
function moveEdge(index,edge,time) {
  const r=reviewModel,w=r.words[index],lo=index?r.words[index-1].end:0,hi=index<r.words.length-1?r.words[index+1].start:r.duration;
  const minimumWidth=Math.min(.04,(w.end-w.start)/2);
  w[edge]=clamp(Math.round((time+Number.EPSILON)*100)/100,edge==='start'?lo:w.start+minimumWidth,edge==='start'?w.end-minimumWidth:hi);
  r.dirty=true;const span=$(`[data-span="${index}"]`);
  span.style.left=w.start/r.duration*100+'%';span.style.width=(w.end-w.start)/r.duration*100+'%';
  const handle=span.querySelector('[data-edge="'+edge+'"]');handle.setAttribute('aria-label',(edge==='start'?'Start':'End')+' of '+w.text+', '+w[edge].toFixed(2)+' seconds');
  span.querySelector('.word-body').title=w.text+' · '+w.start.toFixed(2)+'–'+w.end.toFixed(2)+' s';
  $('#timingStatus').textContent='Timing adjusted · saved when you keep this take.';
  setPlaybackTime(w[edge]);
}
function timelineMove(e) {
  if(!timelineDrag)return;
  if(timelineDrag.edge)moveEdge(timelineDrag.index,timelineDrag.edge,timelineTime(e));else setPlaybackTime(timelineTime(e));
}
function endTimelineDrag(){timelineDrag=null;}
function timelineKeyboard(e) {
  const edge=e.target.closest('[data-edge]');
  if(edge&&['ArrowLeft','ArrowRight'].includes(e.key)) {
    e.preventDefault();e.stopPropagation();pausePlayback();const i=Number(edge.dataset.index),field=edge.dataset.edge;
    reviewModel.selected=i;reviewModel.undo.push(structuredClone(reviewModel.words));moveEdge(i,field,reviewModel.words[i][field]+(e.key==='ArrowLeft'?-1:1)*(e.shiftKey?.01:.05));
  }
}
function keepTake() {
  const r=reviewModel,session=currentSession();if(!session)return;
  r.take.words=structuredClone(r.words);r.take.reviewed=true;session.reviewed=session.takes.every(t=>t.reviewed)&&session.captured>=session.total;
  if(r.fromRecorder) {
    session.cursor++;
    if(session.cursor>=session.total){const index=baselineStep();if(index===state.done)state.done++;setScreen('completion');}
    else setScreen('record');
  } else setScreen('detail');
}
function completion() {
  return `<div class="completion"><div class="type-symbol">${icon('check')}</div><div class="eyebrow muted">Session complete</div><h1>All set for now.</h1><p>${state.done<4?'Your next step is '+steps[state.done].title.toLowerCase()+'.':'Your session is ready to revisit in your collection.'}</p><div class="actions"><button class="primary" data-action="home">Back to Capture ${icon('arrow')}</button></div></div>`;
}

function builder() {
  return `<div class="intro"><div class="eyebrow">New collection type</div><h1>What would you like to collect?</h1><p>Choose a template, then make it yours.</p></div><div class="builder-list">${templates.map(t=>`<button data-build="${t.id}">${icon(t.icon)}<span><strong>${t.title}</strong><small>${t.description}</small></span><span class="builder-arrow">${icon('arrow')}</span></button>`).join('')}</div>`;
}
function configureTemplate(id) {
  builderTemplate=templates.find(t=>t.id===id);const t=builderTemplate;
  dialog(t.title,`<p>${t.detail}</p><form id="builderForm"><label>Collection name<input id="customName" name="title" required maxlength="100" placeholder="${t.example}"></label>${t.id!=='free'?`<label>${t.label}<textarea name="content" id="customText" rows="5" required maxlength="200000" placeholder="${t.placeholder}"></textarea></label>`:''}${t.id==='reader'?'<label>Text source<input name="source" placeholder="Author, edition or source link" maxlength="300"></label>':''}${t.id==='pose'?'<label>Distances · cm<input name="positions" value="35, 45, 55" required pattern="[0-9, ]+"><small>The same prompt set is recorded at each distance.</small></label>':''}<p class="dialog-note">The recipe is fixed once created. Sessions keep their own setup and recordings.</p><div class="actions"><button class="secondary" type="button" data-action="close-modal">Cancel</button><button class="primary" type="submit">Create collection ${icon('arrow')}</button></div></form>`);
  $('#builderForm').onsubmit=e=>{
    e.preventDefault();const data=Object.fromEntries(new FormData(e.target));
    if(!data.title.trim()||(t.id!=='free'&&!data.content.trim()))return;
    if(t.id==='pose'){
      const input=e.target.elements.positions,positions=data.positions.split(',').map(v=>Number(v.trim()));
      if(positions.some(v=>!Number.isFinite(v)||v<10||v>300)){input.setCustomValidity('Use distances between 10 and 300 cm, separated by commas.');input.reportValidity();input.oninput=()=>input.setCustomValidity('');return;}
      data.positions=positions.join(', ');
    }
    const definition=Object.freeze({...makeDefinition('collection-'+Date.now(),data.title.trim(),t.id,(data.content||'').trim()),source:data.source||'',positions:data.positions||''});
    collections.push(definition);state.collection=definition.id;closeDialog();setScreen('detail');
  };
}
function updateLibrary() {
  const q=$('#search').value.trim().toLowerCase(),filter=$('#sessionFilter').value;
  $('#libraryList').innerHTML=collections.map(c=>{
    const sessions=state.sessions.filter(s=>s.collectionId===c.id&&(s.name+' '+c.title).toLowerCase().includes(q)&&(filter==='all'||(filter==='complete'&&s.reviewed)||(filter==='review'&&!s.reviewed)));
    if(!sessions.length)return '';
    return `<details open><summary>${escapeHTML(c.title)} <small>· ${sessions.length}</small></summary>${sessions.map(s=>`<button class="session-link ${s.id===state.session?'selected':''}" data-session="${s.id}">${escapeHTML(s.name)}<small>${escapeHTML(s.date)}</small><small>${s.captured} ${s.captured===1?'take':'takes'} · ${s.reviewed?'Reviewed':'Needs review'}</small></button>`).join('')}</details>`;
  }).join('')||'<p class="library-empty">No matching sessions.</p>';
}
function openSession(id) {
  const session=state.sessions.find(s=>s.id===id);if(!session)return;
  state.session=id;state.collection=session.collectionId;
  const take=session.takes.find(t=>!t.reviewed)||session.takes[0];
  if(take)openReview(take);else setScreen('detail');
}
function render() {
  breadcrumb();updateLibrary();
  $('#content').classList.toggle('review-content',state.screen==='review');
  $('#content').innerHTML=({home,detail,setup,record,review,completion,builder}[state.screen]||(()=>`<div class="intro"><div class="eyebrow">Design preview</div><h1>${state.screen==='training'?'Training':'Dictation'}</h1><p>This pass focuses on collection. The installed app is unchanged.</p><div class="actions"><button class="secondary" data-action="home">Return to Capture ${icon('arrow')}</button></div></div>`))();
  if(state.screen==='review') bindReview();
  if(state.screen==='record') {
    const b=$('#recordButton'),reader=['reader','free'].includes(currentCollection().template);
    if(reader)b.onclick=()=>state.recording?finishRecording():startRecording();
    else {
      b.onpointerdown=e=>{e.preventDefault();b.setPointerCapture(e.pointerId);startRecording();};b.onpointerup=finishRecording;
      b.onpointercancel=()=>{state.recording=false;cancelAnimations();render();};
    }
  }
}
function preview(mode) {
  cancelAnimations();closeDialog();state.done=mode==='complete'?4:mode==='progress'?1:0;
  state.previewMode=mode;state.recording=false;state.session=null;state.collection=steps[Math.min(state.done,3)].id;
  state.sessions=[];
  const completed=mode==='complete'?4:mode==='progress'?1:0;
  for(let i=0;i<completed;i++) {
    const c=collections.find(c=>c.id===steps[i].id),s=steps[i],cue=i?'Please put the blue mug beside my keyboard.':calibrationCues[1][0];
    state.sessions.push({id:'baseline-'+i,collectionId:c.id,definition:structuredClone(c),setup:structuredClone(preferences),name:'Session 1',date:['Monday · 9:14 AM','Monday · 9:28 AM','Tuesday · 11:20 AM','Today · 9:40 AM'][i],captured:s.total,total:s.total,cursor:s.total,reviewed:true,takes:[{text:cue,mode:i?'Speak aloud':'Movement reference',duration:6,reviewed:true,cursor:1}]});
  }
  if(mode==='progress') {
    const c=collections.find(c=>c.id==='first-speech');
    state.sessions.push({id:'speech-progress',collectionId:c.id,definition:structuredClone(c),setup:structuredClone(preferences),name:'Session 1',date:'Today · 9:28 AM',captured:32,total:220,cursor:32,reviewed:false,takes:[{text:'Please put the blue mug beside my keyboard.',mode:'Speak aloud',duration:6,cursor:31,reviewed:false}]});
  }
  if(mode==='complete') {
    if(!collections.some(c=>c.id==='odyssey'))collections.push(makeDefinition('odyssey','The Odyssey','reader','Tell me, Muse, of the man of many ways. He wandered far after the fall of Troy.'));
    if(!collections.some(c=>c.id==='desk-phrases'))collections.push(makeDefinition('desk-phrases','At my desk','phrases','Open the document.\nMove to the next page.\nSave my changes.'));
    const c=collections.find(c=>c.id==='odyssey');
    state.sessions.push({id:'book-example',collectionId:c.id,definition:structuredClone(c),setup:structuredClone(preferences),name:'Book I · Session 1',date:'Today · 10:42 AM',captured:1,total:4,cursor:1,reviewed:false,takes:[{text:'Tell me, Muse, of the man of many ways.',mode:'Speak aloud',duration:6,cursor:0,reviewed:false}]});
  }
  document.querySelectorAll('[data-preview]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.preview===mode)));
  setScreen('home');
}

$('#radarStatus').onclick=()=>device();
$('#radarMenuToggle').onclick=e=>{e.stopPropagation();const menu=$('#radarMenu'),open=menu.classList.contains('hidden');closeMenus();menu.classList.toggle('hidden',!open);e.currentTarget.setAttribute('aria-expanded',String(open));};
$('#libraryToggle').onclick=()=>{state.library=!state.library;$('#workspace').classList.toggle('library-open',state.library);$('#library').inert=!state.library;$('#libraryToggle').setAttribute('aria-expanded',String(state.library));$('#libraryToggle').setAttribute('aria-label',state.library?'Hide recording sidebar':'Show recording sidebar');};
$('#search').oninput=updateLibrary;$('#sessionFilter').onchange=updateLibrary;
document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b){if(!e.target.closest('.menu'))closeMenus();return;}
  if(b.disabled)return;
  if(b.dataset.preview)return preview(b.dataset.preview);
  if(b.dataset.collection){state.collection=b.dataset.collection;return setScreen('detail');}
  if(b.dataset.session)return openSession(b.dataset.session);
  if(b.dataset.build)return configureTemplate(b.dataset.build);
  if(b.dataset.positionView)return selectPositionView(b.dataset.positionView);
  if(b.dataset.word!==undefined){pausePlayback();reviewModel.selected=Number(b.dataset.word);return setPlaybackTime(reviewModel.words[reviewModel.selected].start,true);}
  const action=b.dataset.action;if(!action)return;
  if(['collection-menu','channels'].includes(action)) {
    const menu=$(action==='channels'?'#channelMenu':'#collectionMenu'),open=menu.classList.contains('hidden');closeMenus();menu.classList.toggle('hidden',!open);b.setAttribute('aria-expanded',String(open));return;
  }
  closeMenus();
  if(['home','detail','setup','builder','training','dictation'].includes(action))return setScreen(action);
  if(action==='definition')return definition();
  if(action==='motion-guide')return motionGuide();
  if(action==='replay-guide')return animateGuide();
  if(action==='settings')return settings();
  if(action==='device')return device();
  if(action==='start-preview')return device(true);
  if(action==='toggle-preview')return togglePreview();
  if(action==='connect')return toggleConnection();
  if(action==='microphone')return microphone();
  if(action==='save-microphone'){preferences.mic=$('#microphoneInput').value;closeDialog();if(state.screen==='setup')render();return;}
  if(action==='close-modal')return closeDialog();
  if(action==='enter-recorder'){preferences.profile='complex';return enterRecorder();}
  if(action==='resume'){state.session=b.dataset.resume;return enterRecorder(true);}
  if(action==='retake'){currentSession().cursor=reviewModel.take.cursor;return setScreen('record');}
  if(action==='keep')return keepTake();
  if(action==='play')return togglePlayback();
  if(action==='rewind'){pausePlayback();return setPlaybackTime(0,true);}
  if(action==='next-frame'){pausePlayback();return setPlaybackTime(reviewModel.time+.05,true);}
  if(action==='undo-timing'&&reviewModel.undo.length){reviewModel.words=reviewModel.undo.pop();renderWordSpans();}
});
document.addEventListener('change',e=>{
  const channel=e.target.dataset.channel;if(!channel)return;
  reviewModel.channels[channel]=e.target.checked;
  document.querySelectorAll('[data-lane="'+channel+'"]').forEach(el=>el.hidden=!e.target.checked);
  drawTracks();
});
document.addEventListener('keydown',e=>{
  if(e.key==='Escape')closeMenus();
  if($('#modal').open||e.target.closest('input,textarea,select,[contenteditable=true]'))return;
  if(e.code==='Space'&&['record','review'].includes(state.screen)) {
    if(e.target.closest('button')&&!e.target.closest('#recordButton'))return;
    e.preventDefault();if(e.repeat)return;
    if(state.screen==='review')togglePlayback();
    else if(['reader','free'].includes(currentCollection().template)){state.recording?finishRecording():startRecording();}
    else startRecording();
  }
  if(state.screen==='review'&&['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) {
    e.preventDefault();pausePlayback();setPlaybackTime(e.key==='Home'?0:e.key==='End'?reviewModel.duration:reviewModel.time+(e.key==='ArrowLeft'?-1:1)*(e.shiftKey?.5:.05),true);
  }
});
document.addEventListener('keyup',e=>{if(e.code==='Space'&&state.recording&&!['reader','free'].includes(currentCollection().template)){e.preventDefault();finishRecording();}});
window.addEventListener('blur',()=>{if(state.recording){state.recording=false;cancelAnimations();render();}pausePlayback();});
document.addEventListener('visibilitychange',()=>{if(document.hidden){pausePlayback();if(state.recording){state.recording=false;cancelAnimations();render();}}});
new ResizeObserver(()=>{if(state.screen==='review')drawTracks();if($('#modal').open&&$('#positionCanvas'))drawPosition(deviceView.running?(performance.now()-deviceView.start)/1000:0);}).observe($('#content'));
render();
