import AppKit
import Combine
import QuartzCore

public enum Player: String, CaseIterable, Identifiable, Sendable {
    case spotify = "Spotify"
    case music = "Apple Music"

    public var id: String { rawValue }

    public var bundleID: String {
        switch self {
        case .spotify: return "com.spotify.client"
        case .music: return "com.apple.Music"
        }
    }

    public var isRunning: Bool {
        !NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).isEmpty
    }
}

public enum PermissionState: Equatable, Sendable {
    case unknown, granted, denied
}

public struct Track: Equatable, Sendable {
    public var player: Player
    public var id: String
    public var title: String
    public var artist: String
    public var album: String
    public var duration: Double
    public var position: Double
    public var isPlaying: Bool
    public var artworkURL: URL?
}

public struct PlayerStatus: Equatable, Sendable {
    public var running = false
    public var permission: PermissionState = .unknown
    public var track: Track?
}

/// Polls Spotify and Apple Music over AppleScript and extrapolates the playback position between polls.
@MainActor
public final class NowPlayingMonitor: ObservableObject {
    @Published public private(set) var track: Track?
    @Published public private(set) var statuses: [Player: PlayerStatus] = [:]
    @Published public private(set) var artwork: NSImage?
    @Published public private(set) var artworkColors: [NSColor] = []

    private let queue = DispatchQueue(label: "nowplaying.applescript", qos: .userInitiated)
    private var timer: Timer?
    private var polling = false
    private var basePosition: Double = 0
    private var baseTime: CFTimeInterval = 0
    private var lastPlayingPlayer: Player?
    private var artworkTask: Task<Void, Never>?

    public init() {}

    public func start(interval: TimeInterval = 0.5) {
        guard timer == nil else { return }
        let t = Timer(timeInterval: interval, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.poll() }
        }
        RunLoop.main.add(t, forMode: .common)
        timer = t
        poll()
    }

    public func stop() {
        timer?.invalidate()
        timer = nil
    }

    /// The best estimate of the playback position right now, in seconds.
    public func position(at now: CFTimeInterval = CACurrentMediaTime()) -> Double {
        guard let track else { return 0 }
        return track.isPlaying ? basePosition + (now - baseTime) : basePosition
    }

    public var isPlaying: Bool { track?.isPlaying ?? false }

    private func poll() {
        guard !polling else { return }
        polling = true
        let players = Player.allCases.filter(\.isRunning)
        queue.async { [weak self] in
            var results: [Player: PlayerStatus] = [:]
            for p in Player.allCases {
                results[p] = players.contains(p) ? AppleScriptBridge.query(p) : PlayerStatus()
            }
            let now = CACurrentMediaTime()
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    self?.apply(results, at: now)
                    self?.polling = false
                }
            }
        }
    }

    private func apply(_ results: [Player: PlayerStatus], at now: CFTimeInterval) {
        statuses = results
        // Prefer the player that is playing; otherwise whichever played last.
        let playing = Player.allCases.first { results[$0]?.track?.isPlaying == true }
        if let playing { lastPlayingPlayer = playing }
        let chosen = playing ?? lastPlayingPlayer.flatMap { p in results[p]?.track != nil ? p : nil }
            ?? Player.allCases.first { results[$0]?.track != nil }
        let next = chosen.flatMap { results[$0]?.track }

        guard let next else {
            if track != nil { track = nil; setArtwork(nil, for: nil) }
            return
        }
        let changed = next.id != track?.id || next.player != track?.player
        if changed {
            basePosition = next.position
            baseTime = now
            loadArtwork(for: next)
        } else {
            let predicted = (track?.isPlaying ?? false) ? basePosition + (now - baseTime) : basePosition
            let diff = next.position - predicted
            if abs(diff) > 0.35 || !next.isPlaying {
                basePosition = next.position
            } else {
                // Ease toward the reported value so the clock never visibly jumps backwards.
                basePosition = predicted + diff * 0.3
            }
            baseTime = now
        }
        if track != next { track = next }
    }

    private func loadArtwork(for track: Track) {
        artworkTask?.cancel()
        let player = track.player
        let url = track.artworkURL
        let id = track.id
        let scriptQueue = queue
        artworkTask = Task { [weak self] in
            var image: NSImage?
            if let url {
                if let result = try? await URLSession.shared.data(from: url) { image = NSImage(data: result.0) }
            } else if player == .music {
                image = await withCheckedContinuation { cont in
                    scriptQueue.async { cont.resume(returning: AppleScriptBridge.musicArtwork()) }
                }
            }
            guard !Task.isCancelled else { return }
            await MainActor.run {
                guard self?.track?.id == id else { return }
                self?.setArtwork(image, for: id)
            }
        }
    }

    private func setArtwork(_ image: NSImage?, for id: String?) {
        artwork = image
        artworkColors = image.map { ColorExtractor.vibrantColors(from: $0, count: 3) } ?? []
    }
}

/// AppleScript access to Spotify and Music. Only ever called on one serial queue.
enum AppleScriptBridge {
    private static let sep = "\u{1F}"

    private static let spotifyScript = """
    tell application id "com.spotify.client"
        set s to player state as string
        if s is "stopped" then return "stopped"
        set t to current track
        set sep to (ASCII character 31)
        return s & sep & (id of t) & sep & (name of t) & sep & (artist of t) & sep & (album of t) & sep & ((duration of t) as string) & sep & ((player position) as string) & sep & (artwork url of t)
    end tell
    """

    private static let musicScript = """
    tell application id "com.apple.Music"
        set s to player state as string
        if s is "stopped" then return "stopped"
        set t to current track
        set sep to (ASCII character 31)
        set pid to ""
        try
            set pid to persistent ID of t
        end try
        return s & sep & pid & sep & (name of t) & sep & (artist of t) & sep & (album of t) & sep & ((duration of t) as string) & sep & ((player position) as string) & sep & ""
    end tell
    """

    private static var compiled: [String: NSAppleScript] = [:]

    private static func run(_ source: String) -> (String?, Int?) {
        let script: NSAppleScript
        if let s = compiled[source] {
            script = s
        } else {
            guard let s = NSAppleScript(source: source) else { return (nil, nil) }
            compiled[source] = s
            script = s
        }
        var error: NSDictionary?
        let result = script.executeAndReturnError(&error)
        if let error {
            return (nil, error[NSAppleScript.errorNumber] as? Int)
        }
        return (result.stringValue, nil)
    }

    static func query(_ player: Player) -> PlayerStatus {
        var status = PlayerStatus(running: true)
        let (out, err) = run(player == .spotify ? spotifyScript : musicScript)
        if let err {
            // -1743: the user denied Automation access. -1744: would need to ask.
            status.permission = (err == -1743 || err == -1744) ? .denied : .granted
            return status
        }
        status.permission = .granted
        guard let out, out != "stopped" else { return status }
        let f = out.components(separatedBy: sep)
        guard f.count >= 8 else { return status }
        func num(_ s: String) -> Double { Double(s.replacingOccurrences(of: ",", with: ".")) ?? 0 }
        var duration = num(f[5])
        if player == .spotify { duration /= 1000 } // Spotify reports milliseconds.
        status.track = Track(
            player: player,
            id: f[1].isEmpty ? "\(f[2])|\(f[3])" : f[1],
            title: f[2], artist: f[3], album: f[4],
            duration: duration,
            position: num(f[6]),
            isPlaying: f[0] == "playing",
            artworkURL: URL(string: f[7]).flatMap { $0.scheme == nil ? nil : $0 }
        )
        return status
    }

    static func musicArtwork() -> NSImage? {
        let source = """
        tell application id "com.apple.Music"
            try
                return raw data of artwork 1 of current track
            end try
            return missing value
        end tell
        """
        guard let script = NSAppleScript(source: source) else { return nil }
        var error: NSDictionary?
        let desc = script.executeAndReturnError(&error)
        guard error == nil else { return nil }
        let data = desc.data
        return data.isEmpty ? nil : NSImage(data: data)
    }
}
