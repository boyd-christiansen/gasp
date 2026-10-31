import AppKit
import WebKit
import AVFoundation
import SwiftUI

final class AudioReference {
    private let engine = AVAudioEngine()
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
    private(set) var stopped = true

    func start() throws {
        guard stopped, location == nil else { throw failure("Finish the previous audio reference first.") }
        guard AVCaptureDevice.authorizationStatus(for: .audio) == .authorized else { throw failure("Enable microphone access in Session setup first.") }
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else { throw failure("No microphone input is available.") }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("subvocal-audio-\(UUID().uuidString).wav")
        let settings: [String: Any] = [AVFormatIDKey:kAudioFormatLinearPCM, AVSampleRateKey:format.sampleRate,
            AVNumberOfChannelsKey:format.channelCount, AVLinearPCMBitDepthKey:32,
            AVLinearPCMIsFloatKey:true, AVLinearPCMIsNonInterleaved:false]
        let output = try AVAudioFile(forWriting:url, settings:settings, commonFormat:.pcmFormatFloat32, interleaved:false)
        lock.lock()
        file = output; location = url; firstHost = nil; firstSample = nil; expectedSample = nil
        frames = 0; discontinuities = 0; writeError = nil; sampleRate = format.sampleRate; channels = format.channelCount
        lock.unlock()
        input.installTap(onBus:0, bufferSize:1024, format:format) { [weak self] buffer, when in
            guard let self else { return }
            self.lock.lock(); defer { self.lock.unlock() }
            guard let f = self.file else { return }
            if self.firstHost == nil && when.isHostTimeValid {
                self.firstHost = UInt64(AVAudioTime.seconds(forHostTime:when.hostTime)*1e9)
            }
            if when.isSampleTimeValid {
                if self.firstSample == nil { self.firstSample = when.sampleTime }
                if let expected = self.expectedSample, when.sampleTime != expected { self.discontinuities += 1 }
                self.expectedSample = when.sampleTime + Int64(buffer.frameLength)
            }
            do { try f.write(from:buffer); self.frames += Int64(buffer.frameLength) }
            catch { self.writeError = error.localizedDescription }
        }
        do { try engine.start(); stopped = false }
        catch { input.removeTap(onBus:0); file = nil; try? FileManager.default.removeItem(at:url); location = nil; throw error }
    }
    func stop() {
        guard !stopped else { return }
        engine.stop(); engine.inputNode.removeTap(onBus:0)
        lock.lock(); file = nil; stopped = true; lock.unlock()
    }
    func reference() throws -> (URL, [String:Any]) {
        stop()
        lock.lock(); defer { lock.unlock() }
        guard let url = location, frames > 0 else { throw failure("No microphone samples were recorded.") }
        if let error = writeError { throw failure("Audio write failed: \(error)") }
        let metadata: [String:Any] = ["clock":"mach_absolute_time / AVAudioTime hostTime; same host clock as Python monotonic",
            "first_sample_host_ns":firstHost.map { $0 as Any } ?? NSNull(),
            "first_sample_position":firstSample.map { $0 as Any } ?? NSNull(),
            "sample_rate_hz":sampleRate, "channels":channels, "frames":frames,
            "sample_discontinuities":discontinuities, "duration_s":Double(frames)/sampleRate,
            "alignment":"Host-clock audio anchor. Radar transport latency and DCA command-to-frame offset are unmeasured." ]
        return (url,metadata)
    }
    func discard() { stop(); if let url = location { try? FileManager.default.removeItem(at:url) }; location = nil }
}
func failure(_ message: String) -> NSError { NSError(domain:"DesktopSubvocal",code:1,userInfo:[NSLocalizedDescriptionKey:message]) }

final class OverlayState: ObservableObject {
    @Published var title = "Ready to collect"
    @Published var detail = ""
    @Published var active = false
}
struct CaptureOverlay: View {
    @ObservedObject var state: OverlayState
    var body: some View {
        HStack(spacing:13) {
            Image(systemName:state.active ? "waveform" : "checkmark.circle").font(.system(size:22)).foregroundColor(state.active ? Color(red:0.88,green:0.67,blue:0.4) : Color(red:0.67,green:0.82,blue:0.65))
            VStack(alignment:.leading,spacing:4) {
                Text(state.title).font(.system(size:13,weight:.medium)).foregroundColor(.white)
                Text(state.detail).font(.system(size:11)).foregroundColor(.white.opacity(0.6)).lineLimit(1)
            }
            Spacer(minLength:0)
        }.padding(18).frame(width:370,height:76).background(Color(red:0.13,green:0.23,blue:0.19)).cornerRadius(15)
    }
}

final class Application: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var statusItem: NSStatusItem!
    let overlayState = OverlayState()
    var panel: NSPanel!
    let audio = AudioReference()
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
        support = FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("Desktop Subvocal",isDirectory:true)
        do { try FileManager.default.createDirectory(at:support,withIntermediateDirectories:true) }
        catch { fatalAlert(error.localizedDescription); return }
        gesture.keyCode = UInt16(UserDefaults.standard.integer(forKey:"recordingKey").nonzero ?? 61)
        makeWindow(); makeMenu(); makeOverlay()
        startMonitor(request:false)
        do { try startWorker() } catch { fatalAlert(error.localizedDescription) }
    }
    func makeWindow() {
        let content = WKUserContentController(); content.add(self,name:"subvocal")
        let configuration = WKWebViewConfiguration(); configuration.userContentController = content
        web = WKWebView(frame:.zero,configuration:configuration); web.navigationDelegate = self
        web.setValue(false,forKey:"drawsBackground")
        window = NSWindow(contentRect:NSRect(x:0,y:0,width:1230,height:870),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
        window.title = "Subvocal · Training Studio"; window.titlebarAppearsTransparent = true
        window.backgroundColor = NSColor(calibratedRed:0.969,green:0.973,blue:0.957,alpha:1)
        window.appearance = NSAppearance(named:.aqua)
        window.minSize = NSSize(width:860,height:650); window.contentView = web
        window.center(); window.setFrameAutosaveName("TrainingStudio"); window.makeKeyAndOrderFront(nil)
        web.loadHTMLString("<body style='font:16px -apple-system;background:#f7f8f4;color:#204b3e;padding:80px'><h1>subvocal</h1><p>Starting your local training studio…</p></body>",baseURL:nil)
        NSApp.activate(ignoringOtherApps:true)
    }
    func makeMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength:NSStatusItem.variableLength)
        statusItem.button?.image = NSImage(systemSymbolName:"waveform",accessibilityDescription:"Subvocal training")
        let menu = NSMenu()
        menu.addItem(withTitle:"Open Training Studio",action:#selector(showWindow),keyEquivalent:"").target = self
        menu.addItem(withTitle:"Record / finish take",action:#selector(toggle),keyEquivalent:"").target = self
        menu.addItem(withTitle:"Cancel take",action:#selector(cancel),keyEquivalent:"").target = self
        menu.addItem(.separator())
        menu.addItem(withTitle:"Show local recordings",action:#selector(showData),keyEquivalent:"").target = self
        menu.addItem(.separator())
        menu.addItem(withTitle:"Quit Subvocal",action:#selector(quit),keyEquivalent:"q").target = self
        statusItem.menu = menu
        let appMenu = NSMenu(); let root = NSMenuItem(); root.submenu = menu; appMenu.addItem(root)
        let editRoot = NSMenuItem(title:"Edit",action:nil,keyEquivalent:""); let edit = NSMenu(title:"Edit")
        for (name,selector,key) in [("Undo",Selector(("undo:")),"z"),("Cut",#selector(NSText.cut(_:)),"x"),("Copy",#selector(NSText.copy(_:)),"c"),("Paste",#selector(NSText.paste(_:)),"v"),("Select All",#selector(NSText.selectAll(_:)),"a")] { edit.addItem(withTitle:name,action:selector,keyEquivalent:key) }
        editRoot.submenu = edit; appMenu.addItem(editRoot); NSApp.mainMenu = appMenu
    }
    func makeOverlay() {
        panel = NSPanel(contentRect:NSRect(x:0,y:0,width:370,height:76),styleMask:[.borderless,.nonactivatingPanel],backing:.buffered,defer:false)
        panel.level = .floating; panel.isOpaque = false; panel.backgroundColor = .clear
        panel.hasShadow = true; panel.ignoresMouseEvents = true
        panel.collectionBehavior = [.canJoinAllSpaces,.fullScreenAuxiliary]
        panel.contentView = NSHostingView(rootView:CaptureOverlay(state:overlayState))
    }
    func startWorker() throws {
        guard let resource = Bundle.main.resourceURL else { throw failure("App resources are missing.") }
        let executable = resource.appendingPathComponent("capture/subvocal-capture")
        guard FileManager.default.isExecutableFile(atPath:executable.path) else { throw failure("The bundled capture engine is missing. Rebuild the app.") }
        let logs = support.appendingPathComponent("Logs",isDirectory:true)
        try FileManager.default.createDirectory(at:logs,withIntermediateDirectories:true)
        let logURL = logs.appendingPathComponent("capture.log")
        if !FileManager.default.fileExists(atPath:logURL.path) { FileManager.default.createFile(atPath:logURL.path,contents:nil) }
        workerLog = try FileHandle(forWritingTo:logURL); try workerLog?.truncate(atOffset:0)
        readyFile = FileManager.default.temporaryDirectory.appendingPathComponent("subvocal-ready-\(UUID().uuidString).json")
        let process = Process(); process.executableURL = executable
        process.arguments = ["--data",support.appendingPathComponent("Recordings").path,"--ready-file",readyFile.path]
        var env = ProcessInfo.processInfo.environment; env["SUBVOCAL_APP_TOKEN"] = token
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
        } else if startupChecks > 150 { startupTimer?.invalidate(); fatalAlert("The local capture engine did not become ready. Check the capture log in Application Support/Desktop Subvocal/Logs.") }
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
                case "info": result = ["keyCode":Int(gesture.keyCode),"shortcutEnabled":eventTap != nil,"shortcutMessage":eventTap != nil ? "Input Monitoring is available. The shortcut works across apps." : "Enable Input Monitoring to use the shortcut across apps. On-screen capture works now."]
                case "enableShortcut":
                    setKey(body); startMonitor(request:true)
                    result = ["enabled":eventTap != nil,"message":eventTap != nil ? "Shortcut enabled. Double-tap to start; tap once to finish. Escape cancels." : "Allow Subvocal in System Settings → Privacy & Security → Input Monitoring, then click Enable again."]
                case "setShortcut": setKey(body)
                case "audioPermission":
                    let allowed = await AVCaptureDevice.requestAccess(for:.audio)
                    if !allowed { throw failure("Allow Subvocal in System Settings → Privacy & Security → Microphone.") }
                case "audioStart": try audio.start()
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
                case "cue": NSSound(named:"Pop")?.play()
                case "status":
                    recording = body["active"] as? Bool ?? false
                    let title = body["status"] as? String ?? "Ready"
                    overlayState.title = title; overlayState.detail = body["detail"] as? String ?? ""; overlayState.active = recording
                    hideOverlay?.cancel()
                    if recording || title.hasPrefix("Saved") || title.contains("attention") {
                        if let screen = NSScreen.main { panel.setFrameOrigin(NSPoint(x:screen.visibleFrame.midX-185,y:screen.visibleFrame.minY+28)) }
                        panel.orderFrontRegardless()
                        if !recording { let hide = DispatchWorkItem { [weak self] in self?.panel.orderOut(nil) }; hideOverlay = hide; DispatchQueue.main.asyncAfter(deadline:.now()+3,execute:hide) }
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
    @objc func toggle() { web.evaluateJavaScript("window.dispatchEvent(new Event('subvocal-toggle'))",completionHandler:nil) }
    @objc func cancel() { web.evaluateJavaScript("window.dispatchEvent(new Event('subvocal-cancel'))",completionHandler:nil) }
    @objc func showData() { NSWorkspace.shared.open(support.appendingPathComponent("Recordings")) }
    @objc func quit() { NSApp.terminate(nil) }
    func applicationShouldHandleReopen(_ sender:NSApplication,hasVisibleWindows flag:Bool)->Bool { showWindow(); return true }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool { false }
    func applicationShouldTerminate(_ sender:NSApplication)->NSApplication.TerminateReply {
        if quitting { return .terminateNow }
        quitting = true; startupTimer?.invalidate(); audio.discard()
        if let tap = eventTap { CGEvent.tapEnable(tap:tap,enable:false) }
        guard let process = worker,process.isRunning else { return .terminateNow }
        process.interrupt()
        DispatchQueue.global().async { process.waitUntilExit(); DispatchQueue.main.async { NSApp.reply(toApplicationShouldTerminate:true) } }
        return .terminateLater
    }
    func fatalAlert(_ text:String) { let alert = NSAlert(); alert.messageText = "Subvocal needs attention"; alert.informativeText = text; alert.runModal() }
}
extension Int { var nonzero: Int? { self == 0 ? nil : self } }
let application = NSApplication.shared
let delegate = Application()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
