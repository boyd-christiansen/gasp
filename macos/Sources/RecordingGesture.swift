import Foundation

/// Observe short modifier taps without treating modifier+typing as a recording gesture.
struct RecordingGesture {
    var keyCode: UInt16 = 61
    private var downAt: Double?
    private var lastTap: Double?
    private var usedWithKey = false

    mutating func otherKey() { usedWithKey = true; lastTap = nil }
    mutating func reset() { downAt = nil; lastTap = nil; usedWithKey = false }
    mutating func modifier(code: UInt16, down: Bool, time: Double, recording: Bool) -> Bool {
        guard code == keyCode else { lastTap = nil; if downAt != nil { usedWithKey = true }; return false }
        if down {
            if downAt == nil { downAt = time; usedWithKey = false }
            return false
        }
        guard let began = downAt else { return false }
        downAt = nil
        guard !usedWithKey, time-began <= 0.3 else { lastTap = nil; return false }
        if recording { lastTap = nil; return true }
        if let previous = lastTap, time-previous <= 0.5 {
            lastTap = nil
            return true
        }
        lastTap = time
        return false
    }
}
