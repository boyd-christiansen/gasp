import Foundation
import Speech
import AVFoundation

// Optional annotation assistance. Every request requires on-device recognition;
// unavailable local models produce an error instead of a network fallback.
@MainActor
final class SpeechReference {
    private var task: SFSpeechRecognitionTask?
    private var operation = UUID()
    private var currentRecognizer: SFSpeechRecognizer?

    func permission() async throws {
        let status = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0) }
        }
        guard status == .authorized else { throw failure("Allow Gasp in Privacy & Security → Speech Recognition to use on-device speech assistance.") }
    }
    private func recognizer() throws -> SFSpeechRecognizer {
        guard let recognizer = SFSpeechRecognizer(locale:Locale.current), recognizer.supportsOnDeviceRecognition else {
            throw failure("On-device speech recognition is unavailable for this Mac's language. Use paced reading or import word alignments.")
        }
        return recognizer
    }
    func live(receive: @escaping ([String:Any])->Void) throws -> SFSpeechAudioBufferRecognitionRequest {
        let recognizer = try recognizer()
        task?.cancel(); operation = UUID()
        let id = operation
        currentRecognizer = recognizer
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.requiresOnDeviceRecognition = true
        request.shouldReportPartialResults = true
        task = recognizer.recognitionTask(with:request) { [weak self] result,error in
            DispatchQueue.main.async {
                guard self?.operation == id else { return }
                if let result { receive(["text":result.bestTranscription.formattedString]) }
                else if let error { receive(["error":error.localizedDescription]) }
            }
        }
        return request
    }
    func align(url:URL) async throws -> [String:Any] {
        try await permission()
        let input = try AVAudioFile(forReading:url)
        let rate = input.processingFormat.sampleRate
        let chunkFrames = AVAudioFramePosition(rate * 45)
        guard rate > 0, chunkFrames > 0 else { throw failure("Invalid reference audio sample rate.") }
        if input.length <= chunkFrames { return try await recognize(url:url) }
        // Keep recognition requests short. Chunk offsets stay in original audio time.
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent("gasp-speech-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        defer { try? FileManager.default.removeItem(at:folder) }
        var words: [[String:Any]] = [], texts: [String] = []
        while input.framePosition < input.length {
            let start = input.framePosition
            let count = min(chunkFrames,input.length-start)
            let chunk = folder.appendingPathComponent("\(start).wav")
            do {
                let output = try AVAudioFile(forWriting:chunk,settings:input.fileFormat.settings,
                    commonFormat:input.processingFormat.commonFormat,interleaved:input.processingFormat.isInterleaved)
                guard let buffer = AVAudioPCMBuffer(pcmFormat:input.processingFormat,frameCapacity:16384) else {
                    throw failure("Could not allocate speech reference buffer.")
                }
                while input.framePosition < start+count {
                    try input.read(into:buffer,frameCount:AVAudioFrameCount(min(16384,start+count-input.framePosition)))
                    guard buffer.frameLength > 0 else { throw failure("Reference audio ended before its declared duration.") }
                    try output.write(from:buffer)
                }
            }
            let result = try await recognize(url:chunk)
            let offset = Double(start)/rate
            for var word in result["words"] as? [[String:Any]] ?? [] {
                word["start"] = (word["start"] as? Double ?? 0)+offset
                word["end"] = (word["end"] as? Double ?? 0)+offset
                words.append(word)
            }
            texts.append(result["text"] as? String ?? "")
        }
        return ["words":words,"text":texts.joined(separator:" "),"source":"on_device_speech_estimate",
            "locale":Locale.current.identifier,"chunk_seconds":45]
    }
    private func recognize(url:URL) async throws -> [String:Any] {
        let recognizer = try recognizer()
        currentRecognizer = recognizer
        task?.cancel()
        let id = UUID(); operation = id
        let request = SFSpeechURLRecognitionRequest(url:url)
        request.requiresOnDeviceRecognition = true
        request.shouldReportPartialResults = false
        return try await withCheckedThrowingContinuation { continuation in
            var finished = false
            let finish: (Result<[String:Any],Error>)->Void = { result in
                guard !finished else { return }
                finished = true
                continuation.resume(with:result)
            }
            task = recognizer.recognitionTask(with:request) { result,error in
                DispatchQueue.main.async {
                    if let result, result.isFinal {
                        let words: [[String:Any]] = result.bestTranscription.segments.map {
                            ["text":$0.substring,"start":$0.timestamp,"end":$0.timestamp+$0.duration]
                        }
                        finish(.success(["words":words,"text":result.bestTranscription.formattedString,
                            "source":"on_device_speech_estimate","locale":Locale.current.identifier]))
                    } else if let error { finish(.failure(error)) }
                }
            }
            DispatchQueue.main.asyncAfter(deadline:.now()+90) { [weak self] in
                guard !finished else { return }
                if self?.operation == id { self?.task?.cancel() }
                finish(.failure(failure("On-device speech assistance timed out. Your recording is preserved.")))
            }
        }
    }
    func cancel() { operation = UUID(); task?.cancel(); task = nil; currentRecognizer = nil }
}
