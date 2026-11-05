// Isolated UI fixture only. Exercise restart with saved intent and no OS grant.
let permissionAttempts=0,permissionAllowed=false;
window.mockSpeechCalls=0;
window.webkit={messageHandlers:{gasp:{postMessage(message){queueMicrotask(()=>{
 let result={},error=null;
 switch(message.action){
 case 'info':result={audioAuthorized:false,keyCode:61,shortcutMessage:'MOCK native bridge · no real microphone'};break;
 case 'audioPermission':permissionAllowed=++permissionAttempts>1;if(!permissionAllowed)error='Synthetic permission denied. Retry to simulate allowing access.';break;
 case 'audioPrepare':if(!permissionAllowed)error='Synthetic microphone not authorized';break;
 case 'audioStatus':result={ready:permissionAllowed,device:'Synthetic microphone',level:0,microphone_mode:'standard'};break;
 case 'audioRecover':result={recovered:0,pending:0};break;
 case 'audioCool':case 'status':break;
 case 'speechAlign':window.mockSpeechCalls++;error='Siri and Dictation are disabled';break;
 default:error='Unsupported mock native action: '+message.action;
 }
 window.nativeReply(message.id,result,error);
});}}}};
