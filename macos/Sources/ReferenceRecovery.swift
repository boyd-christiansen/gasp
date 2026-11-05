import Foundation

/// Completed microphone references survive failed uploads and app restarts.
/// The original is removed only after a durable queue entry exists and the
/// queued copy is removed only after the backend acknowledges the attachment.
final class ReferenceRecovery {
    struct Entry: Codable {
        let sid: String
        let tid: String
        let timing: Data
        var key: String { sid + "--" + tid }
    }
    let root: URL
    init(root: URL) { self.root = root }
    private func valid(_ value: String) -> Bool {
        value.range(of: "^[a-zA-Z0-9_-]{1,80}$", options: .regularExpression) != nil
    }
    func enqueue(file: URL, sid: String, tid: String, timing: [String: Any]) throws -> Entry {
        guard valid(sid), valid(tid) else { throw NSError(domain:"Gasp",code:1,userInfo:[NSLocalizedDescriptionKey:"Invalid recording identifier."]) }
        let entry = Entry(sid:sid,tid:tid,timing:try JSONSerialization.data(withJSONObject:timing,options:.sortedKeys))
        try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        let target = audio(entry), manifest = root.appendingPathComponent(entry.key + ".json")
        if FileManager.default.fileExists(atPath:target.path) {
            guard FileManager.default.contentsEqual(atPath:file.path,andPath:target.path) else {
                throw NSError(domain:"Gasp",code:2,userInfo:[NSLocalizedDescriptionKey:"A different audio recovery copy already exists for this take."])
            }
        } else {
            // Atomic write prevents a partial copy from looking recoverable.
            try Data(contentsOf:file,options:.mappedIfSafe).write(to:target,options:.atomic)
        }
        if FileManager.default.fileExists(atPath:manifest.path) {
            let previous = try JSONDecoder().decode(Entry.self,from:Data(contentsOf:manifest))
            guard previous.timing == entry.timing else { throw NSError(domain:"Gasp",code:3,userInfo:[NSLocalizedDescriptionKey:"Audio recovery timing differs from the saved copy."]) }
        } else { try JSONEncoder().encode(entry).write(to:manifest,options:.atomic) }
        return entry
    }
    func entries() throws -> [Entry] {
        guard FileManager.default.fileExists(atPath:root.path) else { return [] }
        return try FileManager.default.contentsOfDirectory(at:root,includingPropertiesForKeys:nil)
            .filter { $0.pathExtension == "json" }.sorted { $0.path < $1.path }.map { url in
                let entry = try JSONDecoder().decode(Entry.self,from:Data(contentsOf:url))
                guard valid(entry.sid),valid(entry.tid),url.lastPathComponent == entry.key + ".json" else {
                    throw NSError(domain:"Gasp",code:4,userInfo:[NSLocalizedDescriptionKey:"Invalid audio recovery entry. Your recovery files have been retained."])
                }
                return entry
            }
    }
    func audio(_ entry: Entry) -> URL { root.appendingPathComponent(entry.key + ".wav") }
    func acknowledge(_ entry: Entry) throws {
        // A crash between removals leaves an unreferenced copy, never a live
        // queue entry whose only audio file has been deleted.
        let manifest=root.appendingPathComponent(entry.key + ".json")
        if FileManager.default.fileExists(atPath:manifest.path) { try FileManager.default.removeItem(at:manifest) }
        try? FileManager.default.removeItem(at:audio(entry))
    }
}
