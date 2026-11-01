import AppKit
import AVFoundation

@MainActor
final class StartCue: NSObject, NSSoundDelegate {
    private var sound: NSSound?
    private var continuation: CheckedContinuation<[String:Any],Error>?
    private var started: UInt64 = 0
    private var generation = UUID()
    private func hostTime() -> UInt64 { UInt64(AVAudioTime.seconds(forHostTime:mach_absolute_time())*1e9) }

    func play() async throws -> [String:Any] {
        guard continuation == nil else { throw failure("A start cue is already playing.") }
        guard let url=Bundle.main.url(forResource:"start-cue",withExtension:"wav"),
              let cue=NSSound(contentsOf:url,byReference:false) else { throw failure("The start cue is missing. Reinstall Gasp.") }
        sound=cue;cue.delegate=self;generation=UUID();let run=generation
        return try await withCheckedThrowingContinuation { pending in
            continuation=pending;started=hostTime()
            if !cue.play() { finish(success:false);return }
            // A missing completion callback must not leave the recorder stuck.
            DispatchQueue.main.asyncAfter(deadline:.now()+2) { [weak self] in
                guard self?.generation == run, self?.continuation != nil else { return }
                self?.sound?.stop();self?.finish(success:false)
            }
        }
    }
    nonisolated func sound(_ sound:NSSound,didFinishPlaying success:Bool) {
        Task { @MainActor in
            guard self.sound === sound else { return }
            self.finish(success:success)
        }
    }
    private func finish(success:Bool) {
        guard let pending=continuation else { return }
        continuation=nil;sound?.delegate=nil;sound=nil
        guard success else { pending.resume(throwing:failure("The start sound could not finish. Try the take again."));return }
        let finished=hostTime(), began=started
        // The input remains live; only downstream processing excludes the cue
        // and 80 ms of acoustic decay. Keep the original host-clock anchor.
        DispatchQueue.main.asyncAfter(deadline:.now() + .milliseconds(80)) {
            pending.resume(returning:["cue_protocol":"short-tone-v1","cue_started_host_ns":began,
                "cue_finished_host_ns":finished,"processing_start_host_ns":finished+80_000_000])
        }
    }
}
