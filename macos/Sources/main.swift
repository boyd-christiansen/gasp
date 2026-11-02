import AppKit
import WebKit
import AVFoundation
import Speech
import SwiftUI

final class AudioReference {
    private var engine = AVAudioEngine()
    private let lock = NSLock()
    private var file: AVAudioFile?
    private var location: URL?
    private var firstHost: UInt64?
    private var firstSample: AVAudioFramePosition?
    private var expectedSample: AVAudioFramePosition?
    private var frames: Int64 = 0
    private var discontinuities = 0
    private var writeError: String?
    private var sampleRate: Double = 0
    private var channels: UInt32 = 0
    private var speechRequest: SFSpeechAudioBufferRecognitionRequest?
    private var cueTiming: [String:Any] = [:]
    private var ring: [(AVAudioPCMBuffer, AVAudioTime)] = []
    private var ringFrames: UInt32 = 0
    private var preRollSeconds: Double = 0
    private var warmed = false
    private var level: Float = 0
    private var lastBuffer: Double = 0
    private(set) var stopped = true

    func prepare() throws {
        guard AVCaptureDevice.authorizationStatus(for: .audio) == .authorized else { throw failure("Enable reference audio in Settings.") }
        if warmed && engine.isRunning { return }
        if warmed { cool() }
        // A stopped engine can retain a stale output format after the default
        // input changes (for example 48 kHz → 24 kHz). Recreate it between visits.
        engine = AVAudioEngine()
        try GaspAudioInput.start(engine) { [weak self] buffer, when in
            guard let self else { return }
            self.lock.lock(); defer { self.lock.unlock() }
            if self.file != nil && (buffer.format.sampleRate != self.sampleRate || buffer.format.channelCount != self.channels) {
                self.writeError="The microphone format changed during this take. Record it again."
                self.discontinuities += 1
                return
            }
            if self.file == nil && (buffer.format.sampleRate != self.sampleRate || buffer.format.channelCount != self.channels) {
                self.ring=[];self.ringFrames=0
                self.sampleRate=buffer.format.sampleRate;self.channels=buffer.format.channelCount
            }
            self.lastBuffer=ProcessInfo.processInfo.systemUptime
            if let data=buffer.floatChannelData {
                var sum:Float=0
                for i in 0..<Int(buffer.frameLength) { sum += data[0][i]*data[0][i] }
                self.level=sqrt(sum/Float(max(1,buffer.frameLength)))
            }
            if self.file != nil { self.append(buffer, when) }
            // A short in-memory pre-roll catches speech begun with the key press.
            // No file is created until a take starts; discard this memory on exit.
            if let copy=AVAudioPCMBuffer(pcmFormat:buffer.format,frameCapacity:buffer.frameLength),
               let src=buffer.floatChannelData,let dst=copy.floatChannelData {
                copy.frameLength=buffer.frameLength
                for c in 0..<Int(buffer.format.channelCount) {
                    memcpy(dst[c],src[c],Int(buffer.frameLength)*MemoryLayout<Float>.size)
                }
                self.ring.append((copy,when));self.ringFrames += copy.frameLength
                while self.ring.count>1 && self.ringFrames > UInt32(self.sampleRate * 0.3) {
                    self.ringFrames -= self.ring.removeFirst().0.frameLength
                }
            }
        }
        warmed=true
    }
    private func append(_ buffer:AVAudioPCMBuffer,_ when:AVAudioTime) {
        guard let f=file else { return }
        if firstHost == nil && when.isHostTimeValid { firstHost=UInt64(AVAudioTime.seconds(forHostTime:when.hostTime)*1e9) }
        if when.isSampleTimeValid {
            if firstSample == nil { firstSample=when.sampleTime }
            if let expected=expectedSample,when.sampleTime != expected { discontinuities += 1 }
            expectedSample=when.sampleTime+Int64(buffer.frameLength)
        }
        if let request=speechRequest, let ready=cueTiming["processing_start_host_ns"] as? UInt64, when.isHostTimeValid {
            let start=AVAudioTime.seconds(forHostTime:when.hostTime)
            let skip=min(Int(buffer.frameLength),max(0,Int(ceil((Double(ready)/1e9-start)*sampleRate))))
            if skip == 0 { request.append(buffer) }
            else if skip < Int(buffer.frameLength), let part=AVAudioPCMBuffer(pcmFormat:buffer.format,frameCapacity:buffer.frameLength-UInt32(skip)),
                    let src=buffer.floatChannelData, let dst=part.floatChannelData {
                part.frameLength=buffer.frameLength-UInt32(skip)
                for c in 0..<Int(buffer.format.channelCount) { memcpy(dst[c],src[c]+skip,Int(part.frameLength)*MemoryLayout<Float>.size) }
                request.append(part)
            }
        }
        do { try f.write(from:buffer);frames += Int64(buffer.frameLength) }
        catch { writeError=error.localizedDescription }
    }
    func start(speech:SFSpeechAudioBufferRecognitionRequest?=nil) throws {
        guard stopped,location == nil else { throw failure("Finish the previous audio reference first.") }
        try prepare()
        guard status()["ready"] as? Bool == true else { throw failure("Microphone is warming up. Wait for the input meter, then try again.") }
        lock.lock();defer { lock.unlock() }
        let url=FileManager.default.temporaryDirectory.appendingPathComponent("gasp-audio-\(UUID().uuidString).wav")
        let settings:[String:Any]=[AVFormatIDKey:kAudioFormatLinearPCM,AVSampleRateKey:sampleRate,
            AVNumberOfChannelsKey:channels,AVLinearPCMBitDepthKey:32,AVLinearPCMIsFloatKey:true,AVLinearPCMIsNonInterleaved:false]
        let output=try AVAudioFile(forWriting:url,settings:settings,commonFormat:.pcmFormatFloat32,interleaved:false)
        file=output;location=url;firstHost=nil;firstSample=nil;expectedSample=nil
        frames=0;discontinuities=0;writeError=nil;speechRequest=speech;stopped=false
        cueTiming=["cue_protocol":"short-tone-v1"]
        preRollSeconds=Double(ringFrames)/sampleRate
        for (buffer,time) in ring { append(buffer,time) }
    }
    func stop() {
        lock.lock();let request=speechRequest;speechRequest=nil;file=nil;stopped=true;lock.unlock()
        request?.endAudio()
    }
    func markCue(_ timing:[String:Any]) { lock.lock();cueTiming=timing;lock.unlock() }
    func cool() {
        stop()
        if warmed { GaspAudioInput.stop(engine);warmed=false }
        lock.lock();ring=[];ringFrames=0;level=0;lastBuffer=0;lock.unlock()
    }
    func status() -> [String:Any] {
        lock.lock()
        let rms=level, rate=sampleRate, recent=ProcessInfo.processInfo.systemUptime-lastBuffer < 0.6
        lock.unlock()
        return ["ready":warmed && engine.isRunning && recent,
            "needs_restart":warmed && !engine.isRunning,
            "level":rms,"sample_rate_hz":rate,"microphone_mode":mode(),
            "device":AVCaptureDevice.default(for:.audio)?.localizedName ?? "Mac sound input",
            "voice_processing":engine.inputNode.isVoiceProcessingEnabled]
    }
    private func mode() -> String {
        switch AVCaptureDevice.activeMicrophoneMode {
        case .voiceIsolation:return "voice_isolation"
        case .wideSpectrum:return "wide_spectrum"
        default:return "standard"
        }
    }
    func reference() throws -> (URL,[String:Any]) {
        stop();lock.lock();defer { lock.unlock() }
        guard let url=location,frames>0 else { throw failure("No microphone samples were recorded.") }
        if let error=writeError { throw failure("Audio write failed: \(error)") }
        return (url,["clock":"mach_absolute_time / AVAudioTime hostTime; same host clock as Python monotonic",
            "first_sample_host_ns":firstHost.map{$0 as Any} ?? NSNull(),
            "first_sample_position":firstSample.map{$0 as Any} ?? NSNull(),
            "sample_rate_hz":sampleRate,"channels":channels,"frames":frames,
            "sample_discontinuities":discontinuities,"duration_s":Double(frames)/sampleRate,
            "microphone_mode":mode(),"voice_processing":engine.inputNode.isVoiceProcessingEnabled,
            "device":AVCaptureDevice.default(for:.audio)?.localizedName ?? "Mac sound input",
            "pre_roll_s":preRollSeconds,"alignment":"Host-clock audio anchor; radar transport latency remains unmeasured."].merging(cueTiming) { _,new in new })
    }
    func discard() { stop();if let url=location { try? FileManager.default.removeItem(at:url) };location=nil }
}
func failure(_ message: String) -> NSError { NSError(domain:"Gasp",code:1,userInfo:[NSLocalizedDescriptionKey:message]) }

final class OverlayState: ObservableObject {
    @Published var title = "Ready"
    @Published var detail = ""
    @Published var active = false
    @Published var elapsed: Double = 0
    @Published var limit: Double = 0
}
struct CaptureOverlay: View {
    @ObservedObject var state: OverlayState
    var body: some View {
        HStack(spacing:10) {
            FaceMark(active:state.active)
            VStack(alignment:.leading,spacing:5) {
                HStack {
                    Text(state.title).font(.system(size:12,weight:.medium))
                    Spacer()
                    if state.active && state.limit > 0 {
                        Text(String(format:"%02d:%02d",Int(state.elapsed)/60,Int(state.elapsed)%60))
                            .font(.system(size:12,weight:.medium,design:.monospaced))
                    }
                }.foregroundColor(.white)
                Text(state.detail).font(.system(size:11)).foregroundColor(.white.opacity(0.6)).lineLimit(1)
                if state.active && state.limit > 0 {
                    ProgressView(value:min(state.elapsed,state.limit),total:state.limit).tint(.white).scaleEffect(y:0.6)
                }
            }
        }.padding(.horizontal,16).frame(width:370,height:82).background(Color(white:0.08)).cornerRadius(17)
    }
}

final class Application: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var statusItem: NSStatusItem!
    let overlayState = OverlayState()
    var panel: NSPanel!
    let audio = AudioReference()
    let speech = SpeechReference()
    let startCue = StartCue()
    var worker: Process?
    var workerLog: FileHandle?
    var readyFile: URL!
    var baseURL: URL?
    let token = UUID().uuidString + UUID().uuidString
    var eventTap: CFMachPort?
    var tapSource: CFRunLoopSource?
    var gesture = RecordingGesture()
    var recording = false
    var quitting = false
    var startupTimer: Timer?
    var startupChecks = 0
    var hideOverlay: DispatchWorkItem?
    var support: URL!

    func applicationDidFinishLaunching(_ notification: Notification) {
        support = FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("Gasp",isDirectory:true)
        do { try FileManager.default.createDirectory(at:support,withIntermediateDirectories:true) }
        catch { fatalAlert(error.localizedDescription); return }
        gesture.keyCode = UInt16(UserDefaults.standard.integer(forKey:"recordingKey").nonzero ?? 61)
        makeWindow(); makeMenu(); makeOverlay()
        startMonitor(request:false)
        do { try startWorker() } catch { fatalAlert(error.localizedDescription) }
    }
    func makeWindow() {
        let content = WKUserContentController(); content.add(self,name:"gasp")
        let configuration = WKWebViewConfiguration(); configuration.userContentController = content
        web = WKWebView(frame:.zero,configuration:configuration); web.navigationDelegate = self
        web.setValue(false,forKey:"drawsBackground")
        window = NSWindow(contentRect:NSRect(x:0,y:0,width:1230,height:870),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
        window.title = "Gasp"; window.titlebarAppearsTransparent = true
        window.backgroundColor = NSColor.white
        window.appearance = NSAppearance(named:.aqua)
        window.minSize = NSSize(width:860,height:650); window.contentView = web
        window.center(); window.setFrameAutosaveName("TrainingStudio"); window.makeKeyAndOrderFront(nil)
        web.loadHTMLString("<body style='font:16px -apple-system;background:#fff;color:#171717;padding:80px'><h1>gasp</h1><p>Starting…</p></body>",baseURL:nil)
        NSApp.activate(ignoringOtherApps:true)
    }
    func makeMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength:NSStatusItem.variableLength)
        if let url = Bundle.main.url(forResource:"face-open",withExtension:"png"), let image = NSImage(contentsOf:url) {
            image.size = NSSize(width:22,height:22); image.isTemplate = true; statusItem.button?.image = image
        }
        statusItem.button?.toolTip = "Gasp"
        let menu = NSMenu()
        menu.addItem(withTitle:"Open Gasp",action:#selector(showWindow),keyEquivalent:"").target = self
        menu.addItem(withTitle:"Record / finish take",action:#selector(toggle),keyEquivalent:"").target = self
        menu.addItem(withTitle:"Cancel take",action:#selector(cancel),keyEquivalent:"").target = self
        menu.addItem(.separator())
        menu.addItem(withTitle:"Show local recordings",action:#selector(showData),keyEquivalent:"").target = self
        menu.addItem(.separator())
        menu.addItem(withTitle:"Quit Gasp",action:#selector(quit),keyEquivalent:"q").target = self
        statusItem.menu = menu
        let appMenu = NSMenu(); let root = NSMenuItem(); root.submenu = menu; appMenu.addItem(root)
        let editRoot = NSMenuItem(title:"Edit",action:nil,keyEquivalent:""); let edit = NSMenu(title:"Edit")
        for (name,selector,key) in [("Undo",Selector(("undo:")),"z"),("Cut",#selector(NSText.cut(_:)),"x"),("Copy",#selector(NSText.copy(_:)),"c"),("Paste",#selector(NSText.paste(_:)),"v"),("Select All",#selector(NSText.selectAll(_:)),"a")] { edit.addItem(withTitle:name,action:selector,keyEquivalent:key) }
        editRoot.submenu = edit; appMenu.addItem(editRoot); NSApp.mainMenu = appMenu
    }
    func makeOverlay() {
        panel = NSPanel(contentRect:NSRect(x:0,y:0,width:370,height:82),styleMask:[.borderless,.nonactivatingPanel],backing:.buffered,defer:false)
        panel.level = .floating; panel.isOpaque = false; panel.backgroundColor = .clear
        panel.hasShadow = true; panel.ignoresMouseEvents = true
        panel.collectionBehavior = [.canJoinAllSpaces,.fullScreenAuxiliary]
        panel.contentView = NSHostingView(rootView:CaptureOverlay(state:overlayState))
    }
    func startWorker() throws {
        guard let resource = Bundle.main.resourceURL else { throw failure("App resources are missing.") }
        let executable = resource.appendingPathComponent("capture/gasp-capture")
        guard FileManager.default.isExecutableFile(atPath:executable.path) else { throw failure("The bundled capture engine is missing. Rebuild the app.") }
        let logs = support.appendingPathComponent("Logs",isDirectory:true)
        try FileManager.default.createDirectory(at:logs,withIntermediateDirectories:true)
        let logURL = logs.appendingPathComponent("capture.log")
        if !FileManager.default.fileExists(atPath:logURL.path) { FileManager.default.createFile(atPath:logURL.path,contents:nil) }
        workerLog = try FileHandle(forWritingTo:logURL); try workerLog?.truncate(atOffset:0)
        readyFile = FileManager.default.temporaryDirectory.appendingPathComponent("gasp-ready-\(UUID().uuidString).json")
        let process = Process(); process.executableURL = executable
        process.arguments = ["--data",support.appendingPathComponent("Recordings").path,"--ready-file",readyFile.path,
            "--parent-pid",String(ProcessInfo.processInfo.processIdentifier)]
        var env = ProcessInfo.processInfo.environment; env["GASP_APP_TOKEN"] = token
        env["PYTHONNOUSERSITE"] = "1"; process.environment = env
        process.standardOutput = workerLog; process.standardError = workerLog
        process.terminationHandler = { [weak self] _ in DispatchQueue.main.async {
            guard let self, !self.quitting else { return }
            self.fatalAlert("The capture engine stopped. Your saved takes are preserved. Details: \(logURL.path)")
        }}
        worker = process; try process.run()
        startupTimer = Timer.scheduledTimer(withTimeInterval:0.2,repeats:true) { [weak self] _ in self?.checkWorker() }
    }
    func checkWorker() {
        startupChecks += 1
        if let data = try? Data(contentsOf:readyFile),let ready = try? JSONSerialization.jsonObject(with:data) as? [String:Any],let port = ready["port"] as? Int {
            startupTimer?.invalidate(); baseURL = URL(string:"http://127.0.0.1:\(port)")!
            web.load(URLRequest(url:URL(string:"/desktop?token=\(token)",relativeTo:baseURL)!.absoluteURL))
        } else if startupChecks > 150 { startupTimer?.invalidate(); fatalAlert("The local capture engine did not become ready. Check the capture log in Application Support/Gasp/Logs.") }
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy)->Void) {
        if let url = navigationAction.request.url, url.scheme == "about" || (url.host == "127.0.0.1" && url.port == baseURL?.port) { decisionHandler(.allow) }
        else { decisionHandler(.cancel) }
    }
    func userContentController(_ userContentController: WKUserContentController,didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, let base = baseURL,
              message.frameInfo.securityOrigin.host == "127.0.0.1", message.frameInfo.securityOrigin.port == base.port,
              let body = message.body as? [String:Any], let id = body["id"] as? String, let action = body["action"] as? String else { return }
        Task { @MainActor in
            do {
                var result: Any = ["ok":true]
                switch action {
                case "info": result = ["audioAuthorized":AVCaptureDevice.authorizationStatus(for: .audio) == .authorized,"keyCode":Int(gesture.keyCode),"shortcutEnabled":eventTap != nil,"shortcutMessage":eventTap != nil ? "Shortcut enabled · radar capture" : "Input Monitoring permission required · radar capture"]
                case "enableShortcut":
                    setKey(body); startMonitor(request:true)
                    result = ["enabled":eventTap != nil,"message":eventTap != nil ? "Shortcut enabled · radar capture" : "Allow Gasp in System Settings → Privacy & Security → Input Monitoring, then click Enable again."]
                case "setShortcut": setKey(body)
                case "audioPermission":
                    let allowed = await AVCaptureDevice.requestAccess(for:.audio)
                    if !allowed { throw failure("Allow Gasp in System Settings → Privacy & Security → Microphone.") }
                case "speechPermission": try await speech.permission()
                case "audioStart":
                    if body["followSpeech"] as? Bool == true {
                        try await speech.permission()
                        let request = try speech.live { [weak self] payload in
                            guard let data = try? JSONSerialization.data(withJSONObject:payload),let json = String(data:data,encoding:.utf8) else { return }
                            self?.web.evaluateJavaScript("window.nativeSpeech(\(json))",completionHandler:nil)
                        }
                        do { try audio.start(speech:request) } catch { speech.cancel(); throw error }
                    } else { try audio.start() }
                case "speechAlign":
                    guard let sid = body["sid"] as? String,let tid = body["tid"] as? String,
                          sid.range(of:"^[a-zA-Z0-9_-]{1,80}$",options:.regularExpression) != nil,
                          tid.range(of:"^[a-zA-Z0-9_-]{1,80}$",options:.regularExpression) != nil else { throw failure("Invalid recording identifier.") }
                    var request = URLRequest(url:URL(string:"/api/sessions/\(sid)/trials/\(tid)/media?processing=true",relativeTo:base)!.absoluteURL)
                    request.setValue("Bearer \(token)",forHTTPHeaderField:"Authorization")
                    let (download,response) = try await URLSession.shared.download(for:request)
                    guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw failure("Reference audio is unavailable.") }
                    let local = FileManager.default.temporaryDirectory.appendingPathComponent("gasp-speech-\(UUID().uuidString).wav")
                    try FileManager.default.moveItem(at:download,to:local)
                    defer { try? FileManager.default.removeItem(at:local) }
                    result = try await speech.align(url:local)
                    let start=Double((response as? HTTPURLResponse)?.value(forHTTPHeaderField:"X-Audio-Processing-Start-S") ?? "0") ?? 0
                    if var aligned=result as? [String:Any], let words=aligned["words"] as? [[String:Any]] {
                        aligned["words"]=words.map { word -> [String:Any] in
                            var shifted=word;shifted["start"]=(word["start"] as? Double ?? 0)+start
                            shifted["end"]=(word["end"] as? Double ?? 0)+start;return shifted
                        }
                        result=aligned
                    }
                case "audioPrepare": try audio.prepare(); result=audio.status()
                case "exportTraining":
                    guard let runId=body["runId"] as? String,
                          runId.range(of:"^[a-zA-Z0-9_-]{1,80}$",options:.regularExpression) != nil else { throw failure("Invalid training run.") }
                    let panel=NSSavePanel()
                    panel.nameFieldStringValue="gasp-training-\(runId.prefix(8)).zip"
                    panel.title="Export training package"
                    if panel.runModal() == .OK, let destination=panel.url {
                        var request=URLRequest(url:URL(string:"/api/learning/runs/\(runId)/package",relativeTo:base)!.absoluteURL)
                        request.setValue("Bearer \(token)",forHTTPHeaderField:"Authorization")
                        let (download,response)=try await URLSession.shared.download(for:request)
                        guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw failure("Training package is unavailable.") }
                        defer { try? FileManager.default.removeItem(at:download) }
                        if FileManager.default.fileExists(atPath:destination.path) { try FileManager.default.removeItem(at:destination) }
                        try FileManager.default.copyItem(at:download,to:destination)
                        result=["saved":true]
                    } else { result=["saved":false] }
                case "audioStatus": result=audio.status()
                case "audioCool": audio.cool()
                case "microphoneModes": AVCaptureDevice.showSystemUserInterface(.microphoneModes)
                case "audioStop": audio.stop()
                case "audioDiscard": audio.discard()
                case "audioAttach":
                    guard let sid = body["sid"] as? String,let tid = body["tid"] as? String,
                          sid.range(of:"^[a-zA-Z0-9_-]{1,80}$",options:.regularExpression) != nil,
                          tid.range(of:"^[a-zA-Z0-9_-]{1,80}$",options:.regularExpression) != nil else { throw failure("Invalid take identifier.") }
                    let (url,timing) = try audio.reference()
                    var request = URLRequest(url:URL(string:"/api/sessions/\(sid)/trials/\(tid)/media",relativeTo:base)!.absoluteURL)
                    request.httpMethod = "PUT"; request.setValue("Bearer \(token)",forHTTPHeaderField:"Authorization")
                    request.setValue("audio/wav",forHTTPHeaderField:"Content-Type")
                    request.setValue(String(data:try JSONSerialization.data(withJSONObject:timing),encoding:.utf8),forHTTPHeaderField:"X-Audio-Timing")
                    let (data,response) = try await URLSession.shared.upload(for:request,fromFile:url)
                    guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw failure("Audio attachment failed: \(String(data:data,encoding:.utf8) ?? "unknown error")") }
                    audio.discard(); result = ["ok":true]
                case "cue":
                    let timing=try await startCue.play();audio.markCue(timing);result=timing
                case "status":
                    recording = body["active"] as? Bool ?? false
                    let title = body["status"] as? String ?? "Ready"
                    overlayState.title = title; overlayState.detail = body["detail"] as? String ?? ""; overlayState.active = recording
                    overlayState.elapsed = body["elapsed"] as? Double ?? 0
                    overlayState.limit = body["limit"] as? Double ?? 0
                    hideOverlay?.cancel()
                    if recording || title.hasPrefix("Saved") || title.contains("attention") {
                        if let screen = NSScreen.main { panel.setFrameOrigin(NSPoint(x:screen.visibleFrame.midX-185,y:screen.visibleFrame.minY+28)) }
                        panel.orderFrontRegardless()
                        if !recording { let hide = DispatchWorkItem { [weak self] in self?.panel.orderOut(nil) }; hideOverlay = hide; DispatchQueue.main.asyncAfter(deadline:.now()+1.6,execute:hide) }
                    } else { panel.orderOut(nil) }
                default: throw failure("Unknown app action.")
                }
                reply(id,result:result,error:nil)
            } catch { reply(id,result:NSNull(),error:error.localizedDescription) }
        }
    }
    func reply(_ id:String,result:Any,error:String?) {
        let arguments: [Any] = [id,result,error.map { $0 as Any } ?? NSNull()]
        guard let data = try? JSONSerialization.data(withJSONObject:arguments), let json = String(data:data,encoding:.utf8) else { return }
        web.evaluateJavaScript("window.nativeReply(...\(json))",completionHandler:nil)
    }
    func setKey(_ body:[String:Any]) {
        if let key = body["keyCode"] as? Int, [61,62,63].contains(key) { gesture.keyCode = UInt16(key); gesture.reset(); UserDefaults.standard.set(key,forKey:"recordingKey") }
    }
    func startMonitor(request:Bool) {
        if eventTap != nil { return }
        guard CGPreflightListenEventAccess() || (request && CGRequestListenEventAccess()) else { return }
        let mask = (CGEventMask(1) << CGEventType.flagsChanged.rawValue) | (CGEventMask(1) << CGEventType.keyDown.rawValue)
        eventTap = CGEvent.tapCreate(tap:.cgSessionEventTap,place:.headInsertEventTap,options:.listenOnly,eventsOfInterest:mask,callback:{ _,type,event,info in
            guard let info else { return Unmanaged.passUnretained(event) }
            let app = Unmanaged<Application>.fromOpaque(info).takeUnretainedValue()
            if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput { if let tap = app.eventTap { CGEvent.tapEnable(tap:tap,enable:true) }; return Unmanaged.passUnretained(event) }
            app.handleKey(type,event)
            return Unmanaged.passUnretained(event)
        },userInfo:Unmanaged.passUnretained(self).toOpaque())
        if let tap = eventTap { tapSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault,tap,0); CFRunLoopAddSource(CFRunLoopGetMain(),tapSource,.commonModes); CGEvent.tapEnable(tap:tap,enable:true) }
    }
    func handleKey(_ type:CGEventType,_ event:CGEvent) {
        let code = UInt16(event.getIntegerValueField(.keyboardEventKeycode))
        if type == .keyDown { gesture.otherKey(); if code == 53 && recording { cancel() }; return }
        // Device-specific bits from IOLLEvent.h keep left/right modifier states independent.
        let mask = CGEventFlags(rawValue:gesture.keyCode == 61 ? 0x40 : gesture.keyCode == 62 ? 0x2000 : 0x00800000)
        if gesture.modifier(code:code,down:event.flags.contains(mask),time:Double(event.timestamp)/1e9,recording:recording) { toggle() }
    }
    @objc func showWindow() { window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps:true) }
    @objc func toggle() { web.evaluateJavaScript("window.dispatchEvent(new Event('gasp-toggle'))",completionHandler:nil) }
    @objc func cancel() { web.evaluateJavaScript("window.dispatchEvent(new Event('gasp-cancel'))",completionHandler:nil) }
    @objc func showData() { NSWorkspace.shared.open(support.appendingPathComponent("Recordings")) }
    @objc func quit() { NSApp.terminate(nil) }
    func applicationShouldHandleReopen(_ sender:NSApplication,hasVisibleWindows flag:Bool)->Bool { showWindow(); return true }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool { false }
    func applicationShouldTerminate(_ sender:NSApplication)->NSApplication.TerminateReply {
        if quitting { return .terminateNow }
        quitting = true; startupTimer?.invalidate(); audio.discard(); speech.cancel()
        if let tap = eventTap { CGEvent.tapEnable(tap:tap,enable:false) }
        guard let process = worker,process.isRunning else { return .terminateNow }
        process.interrupt()
        DispatchQueue.global().async { process.waitUntilExit(); DispatchQueue.main.async { NSApp.reply(toApplicationShouldTerminate:true) } }
        return .terminateLater
    }
    func fatalAlert(_ text:String) { let alert = NSAlert(); alert.messageText = "Gasp needs attention"; alert.informativeText = text; alert.runModal() }
}
extension Int { var nonzero: Int? { self == 0 ? nil : self } }
let application = NSApplication.shared
let delegate = Application()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
