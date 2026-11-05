// Controlled responses test review behavior; Python and native checks exercise the model.
(async()=>{
 const out=document.createElement('output');out.id='alignmentResults';out.style='position:fixed;top:0;right:0;background:white;z-index:1000;padding:12px;max-width:500px';document.body.append(out);
 const originalFetch=window.fetch,passed=[];let release,calls=0,mode='normal';
 const wait=async(fn,message)=>{const end=Date.now()+15000;while(!fn()){if(Date.now()>end)throw Error(message);await sleep(20);}};
 const assert=(ok,message)=>{if(!ok)throw Error(message);passed.push(message);out.textContent=`Passed ${passed.length}: ${message}`;};
 try{
  await wait(()=>journeyReady&&!!preferences&&!!document.querySelector('#journeyHome [data-collection]'),'Workspace unavailable');
  const take=recordings.find(t=>t.label==='Synthetic sentence');
  const url=`sessions/${take.session_id}/trials/${take.id}`;
  const manual={text:'Please',start_s:1,end_s:1.3,source:'manual'};
  await api(url,'PATCH',{accepted:false,confirmed_text:'Please open the window.',words:[manual,...['open','the','window.'].map(text=>({text}))]});
  window.fetch=async(path,options)=>{
   if(!String(path).endsWith('/suggest-timing'))return originalFetch(path,options);
   calls++;if(mode==='slow')await new Promise(r=>release=r);
   const words=['Please','open','the','window.'].map((text,i)=>({text,start_s:1+i*.7,end_s:1.3+i*.7,source:'forced_alignment'}));
   return new Response(JSON.stringify(mode==='failure'?{kind:'speech',placed:0,message:'The local word-timing model is missing. Reinstall Gasp to restore it.'}:{kind:'speech',placed:4,words,message:'Draft timing from local audio alignment.'}),{status:200});
  };
  await openTake(take.session_id,take.id);await wait(()=>!alignmentPending,'Automatic placement did not finish');
  assert(calls===1&&words.every(w=>w.start_s!=null),'Opening a partially annotated take places all missing words automatically');
  assert(JSON.stringify(words[0])===JSON.stringify(manual),'Existing manual boundaries and source are preserved');
  assert(document.querySelectorAll('#wordSpans .word-span').length===4,'All word blocks immediately appear on the timeline');
  assert(!selected.accepted&&dirty,'Generated timing stays an unverified draft');
  assert($('retryTiming').hidden,'Complete timing has no redundant retry action');
  await saveReview();await sceneHome();await openTake(take.session_id,take.id);
  assert(calls===1&&words.every(w=>w.start_s!=null),'Saved draft timing survives reopening without regeneration');
  words[1]={text:'open'};changed();updateWordLabel();mode='failure';await suggestTiming();
  const style=getComputedStyle($('retryTiming'));
  assert(!$('retryTiming').hidden&&!$('retryTiming').disabled&&parseFloat(style.borderTopWidth)>=1&&$('retryTiming').getBoundingClientRect().height>=36,'Retry is an enabled, bordered button');
  assert($('reviewTimingHint').textContent.includes('model is missing'),'Failure explains the actual cause');
  mode='normal';$('retryTiming').click();await wait(()=>!alignmentPending,'Retry did not finish');
  assert(words[1].start_s!=null&&words[0].start_s===1,'Retry fills the missing interval without moving existing words');
  words[2]={text:'the'};changed();mode='slow';const pending=suggestTiming();await wait(()=>!!release,'Slow request missing');
  words[2]={text:'the',start_s:2.45,end_s:2.65,source:'manual'};changed();release();release=null;await pending;
  assert(words[2].start_s===2.45&&words[2].source==='manual','Manual edits during inference discard the late result');
  words[3]={text:'window.'};changed();const leaving=suggestTiming();await wait(()=>!!release,'Navigation request missing');
  await sceneHome();release();release=null;await leaving;
  assert(stage!=='replay','A late result cannot reopen review after navigation');
  mode='normal';await openTake(take.session_id,take.id);await wait(()=>!alignmentPending,'Reopen timing pending');
  await saveReview(true);const verifiedCalls=calls;await sceneHome();await openTake(take.session_id,take.id);
  assert(calls===verifiedCalls&&selected.accepted,'Verified takes are never aligned automatically');
  out.textContent=`Passed ${passed.length} alignment checks · automatic partial fill, retry, persistence, and stale-result protection`;
 }catch(e){out.textContent='FAILED alignment: '+e.message;throw e;}
 finally{if(release)release();window.fetch=originalFetch;}
})();
