import Foundation

@main struct RecoveryCheck {
    static func main() throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent("gasp-recovery-check-"+UUID().uuidString)
        defer { try? FileManager.default.removeItem(at:root) }
        try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        let input=root.appendingPathComponent("source.wav"), destination=root.appendingPathComponent("queue")
        try Data("original samples".utf8).write(to:input)
        let queue=ReferenceRecovery(root:destination)
        let item=try queue.enqueue(file:input,sid:"session",tid:"take",timing:["frames":16])
        // An upload failure leaves a queue that another app instance can open.
        let restarted=ReferenceRecovery(root:destination)
        let restored=try restarted.entries()
        precondition(restored.count==1 && restored[0].key==item.key)
        let saved=try Data(contentsOf:restarted.audio(restored[0]))
        precondition(saved==Data("original samples".utf8))
        _ = try queue.enqueue(file:input,sid:"session",tid:"take",timing:["frames":16])
        try Data("different samples".utf8).write(to:input)
        do { _ = try queue.enqueue(file:input,sid:"session",tid:"take",timing:["frames":16]);fatalError("Overwrote original") } catch {}
        do { _ = try queue.enqueue(file:input,sid:"../bad",tid:"take",timing:[:]);fatalError("Allowed invalid ID") } catch {}
        precondition(FileManager.default.fileExists(atPath:queue.audio(item).path))
        try restarted.acknowledge(restored[0])
        let remaining=try restarted.entries();precondition(remaining.isEmpty)
        precondition(!FileManager.default.fileExists(atPath:queue.audio(item).path))
        print("Passed audio recovery: restart, idempotent enqueue, conflict protection, identifier validation, acknowledged cleanup")
    }
}
