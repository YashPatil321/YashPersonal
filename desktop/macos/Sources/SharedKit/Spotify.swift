import AppKit
import CryptoKit
import Foundation
import Network
import Security

/// Spotify Web API with Authorization Code + PKCE (no client secret).
/// Sign-in opens the browser; a one-shot listener on 127.0.0.1:8765 catches the redirect.
@MainActor
public final class SpotifyClient: ObservableObject {
    public static let defaultClientID = "9168fe0d1873402497e1738a923b9a76"
    public static let redirectURI = "http://127.0.0.1:8765/callback"
    static let scopes = [
        "user-read-playback-state", "user-modify-playback-state", "user-read-currently-playing",
        "user-library-read", "user-library-modify",
    ].joined(separator: " ")

    public enum State: Equatable { case disconnected, connecting, connected, error(String) }

    public struct Playback: Equatable {
        public var id: String
        public var title: String
        public var artist: String
        public var album: String
        public var artURL: URL?
        public var duration: Double
        public var position: Double
        public var isPlaying: Bool
        public var liked: Bool
        public var fetchedAt: Date
    }

    @Published public private(set) var state: State = .disconnected
    @Published public private(set) var userName = ""
    @Published public private(set) var playback: Playback?

    public var clientID: String { didSet { if clientID.isEmpty { clientID = Self.defaultClientID } } }

    private var accessToken: String?
    private var expiry = Date.distantPast
    private var refreshToken: String? {
        get { Keychain.read("spotify.refresh") }
        set { if let newValue { Keychain.write("spotify.refresh", newValue) } else { Keychain.delete("spotify.refresh") } }
    }
    private var listener: NWListener?
    private var verifier = ""
    private var authState = ""
    private var pollTimer: Timer?
    private var likedCache: [String: Bool] = [:]

    public init(clientID: String = "") {
        self.clientID = clientID.isEmpty ? Self.defaultClientID : clientID
        if refreshToken != nil {
            state = .connected
            Task { await self.loadProfile() }
        }
    }

    public var isConnected: Bool { state == .connected }

    // MARK: Sign in

    public func connect() {
        verifier = Self.randomString(64)
        authState = Self.randomString(16)
        let challenge = Data(SHA256.hash(data: Data(verifier.utf8))).base64URL
        var comps = URLComponents(string: "https://accounts.spotify.com/authorize")!
        comps.queryItems = [
            .init(name: "client_id", value: clientID),
            .init(name: "response_type", value: "code"),
            .init(name: "redirect_uri", value: Self.redirectURI),
            .init(name: "code_challenge_method", value: "S256"),
            .init(name: "code_challenge", value: challenge),
            .init(name: "scope", value: Self.scopes),
            .init(name: "state", value: authState),
        ]
        do {
            try startListener()
        } catch {
            state = .error("Port 8765 is busy. Close the app using it and try again.")
            return
        }
        state = .connecting
        NSWorkspace.shared.open(comps.url!)
    }

    public func disconnect() {
        refreshToken = nil
        accessToken = nil
        playback = nil
        userName = ""
        state = .disconnected
    }

    private func startListener() throws {
        listener?.cancel()
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: 8765)
        params.allowLocalEndpointReuse = true
        let l = try NWListener(using: params)
        l.newConnectionHandler = { [weak self] conn in
            conn.start(queue: .main)
            conn.receive(minimumIncompleteLength: 1, maximumLength: 16384) { data, _, _, _ in
                let request = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
                let firstLine = request.components(separatedBy: "\r\n").first ?? ""
                let path = firstLine.split(separator: " ").dropFirst().first.map(String.init) ?? "/"
                let comps = URLComponents(string: "http://127.0.0.1" + path)
                let code = comps?.queryItems?.first { $0.name == "code" }?.value
                let st = comps?.queryItems?.first { $0.name == "state" }?.value
                let err = comps?.queryItems?.first { $0.name == "error" }?.value
                let ok = code != nil
                let body = """
                <!doctype html><meta charset="utf-8"><title>Spotify</title>
                <body style="font-family:-apple-system,system-ui;background:#0a0a0f;color:#fff;display:grid;place-items:center;height:100vh;margin:0">
                <div style="text-align:center"><h1>\(ok ? "Connected" : "Didn’t connect")</h1>
                <p style="opacity:.6">\(ok ? "You can close this tab and go back to the app." : "You can close this tab and try again.")</p></div>
                """
                let response = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: \(body.utf8.count)\r\nConnection: close\r\n\r\n" + body
                conn.send(content: Data(response.utf8), completion: .contentProcessed { _ in conn.cancel() })
                guard path.hasPrefix("/callback") else { return }
                MainActor.assumeIsolated {
                    guard let self else { return }
                    self.listener?.cancel()
                    self.listener = nil
                    if let code, st == self.authState {
                        Task { await self.exchange(code: code) }
                    } else {
                        self.state = .error(err ?? "Sign-in was cancelled")
                    }
                }
            }
        }
        l.start(queue: .main)
        listener = l
    }

    private func exchange(code: String) async {
        let ok = await tokenRequest([
            "grant_type": "authorization_code", "code": code, "redirect_uri": Self.redirectURI,
            "client_id": clientID, "code_verifier": verifier,
        ])
        if ok {
            state = .connected
            await loadProfile()
        } else if case .connecting = state {
            state = .error("Spotify refused the sign-in. Check the app's redirect URI.")
        }
    }

    private func tokenRequest(_ form: [String: String]) async -> Bool {
        var req = URLRequest(url: URL(string: "https://accounts.spotify.com/api/token")!)
        req.httpMethod = "POST"
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        req.httpBody = form.map { "\($0.key)=\($0.value.formEncoded)" }.joined(separator: "&").data(using: .utf8)
        guard let result = try? await URLSession.shared.data(for: req),
              (result.1 as? HTTPURLResponse)?.statusCode == 200,
              let json = try? JSONSerialization.jsonObject(with: result.0) as? [String: Any],
              let token = json["access_token"] as? String
        else { return false }
        accessToken = token
        expiry = Date().addingTimeInterval((json["expires_in"] as? Double ?? 3600) - 60)
        if let r = json["refresh_token"] as? String { refreshToken = r }
        return true
    }

    private func validToken() async -> String? {
        if let accessToken, Date() < expiry { return accessToken }
        guard let refresh = refreshToken else { return nil }
        let ok = await tokenRequest(["grant_type": "refresh_token", "refresh_token": refresh, "client_id": clientID])
        if !ok {
            // A revoked token: sign out so the UI offers Connect again.
            disconnect()
            state = .error("Spotify signed you out. Connect again.")
        }
        return ok ? accessToken : nil
    }

    // MARK: API

    @discardableResult
    private func api(_ method: String, _ path: String, query: [String: String] = [:]) async -> (Int, Data?) {
        guard let token = await validToken() else { return (401, nil) }
        var comps = URLComponents(string: "https://api.spotify.com/v1" + path)!
        if !query.isEmpty { comps.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) } }
        var req = URLRequest(url: comps.url!, timeoutInterval: 8)
        req.httpMethod = method
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if method != "GET" { req.setValue("0", forHTTPHeaderField: "Content-Length") }
        guard let result = try? await URLSession.shared.data(for: req) else { return (0, nil) }
        return ((result.1 as? HTTPURLResponse)?.statusCode ?? 0, result.0)
    }

    private func loadProfile() async {
        let (status, data) = await api("GET", "/me")
        if status == 200, let data, let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            userName = json["display_name"] as? String ?? ""
        }
    }

    /// Poll the player every `interval` seconds while connected.
    public func startPolling(interval: TimeInterval = 1.0) {
        pollTimer?.invalidate()
        let t = Timer(timeInterval: interval, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self, self.isConnected else { return }
                Task { await self.refreshPlayback() }
            }
        }
        RunLoop.main.add(t, forMode: .common)
        pollTimer = t
    }

    public func refreshPlayback() async {
        let (status, data) = await api("GET", "/me/player", query: ["additional_types": "track,episode"])
        guard status == 200, let data,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let item = json["item"] as? [String: Any], let id = item["id"] as? String
        else {
            if status == 204 { playback = nil }
            return
        }
        let artists = (item["artists"] as? [[String: Any]])?.compactMap { $0["name"] as? String }.joined(separator: ", ")
            ?? (item["show"] as? [String: Any])?["name"] as? String ?? ""
        let album = item["album"] as? [String: Any]
        let images = (album?["images"] as? [[String: Any]]) ?? (item["images"] as? [[String: Any]]) ?? []
        var liked = likedCache[id]
        if liked == nil {
            let (s, d) = await api("GET", "/me/tracks/contains", query: ["ids": id])
            if s == 200, let d, let arr = try? JSONSerialization.jsonObject(with: d) as? [Bool] { liked = arr.first }
            likedCache[id] = liked ?? false
        }
        playback = Playback(
            id: id,
            title: item["name"] as? String ?? "",
            artist: artists,
            album: album?["name"] as? String ?? "",
            artURL: (images.first?["url"] as? String).flatMap(URL.init(string:)),
            duration: (item["duration_ms"] as? Double ?? 0) / 1000,
            position: (json["progress_ms"] as? Double ?? 0) / 1000,
            isPlaying: json["is_playing"] as? Bool ?? false,
            liked: liked ?? false,
            fetchedAt: Date())
    }

    public func playPause() async {
        let playing = playback?.isPlaying ?? false
        await api("PUT", playing ? "/me/player/pause" : "/me/player/play")
        await refreshPlayback()
    }

    public func next() async { await api("POST", "/me/player/next"); try? await Task.sleep(nanoseconds: 300_000_000); await refreshPlayback() }
    public func previous() async { await api("POST", "/me/player/previous"); try? await Task.sleep(nanoseconds: 300_000_000); await refreshPlayback() }

    public func toggleLike() async {
        guard let p = playback else { return }
        let (s, _) = await api(p.liked ? "DELETE" : "PUT", "/me/tracks", query: ["ids": p.id])
        if (200..<300).contains(s) {
            likedCache[p.id] = !p.liked
            playback?.liked = !p.liked
        }
    }

    private static func randomString(_ n: Int) -> String {
        let chars = Array("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
        return String((0..<n).map { _ in chars[Int.random(in: 0..<chars.count)] })
    }
}

extension Data {
    var base64URL: String {
        base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}

extension String {
    var formEncoded: String {
        var allowed = CharacterSet.alphanumerics
        allowed.insert(charactersIn: "-._~")
        return addingPercentEncoding(withAllowedCharacters: allowed) ?? self
    }
}

/// Minimal Keychain wrapper for the refresh token.
enum Keychain {
    private static let service = Bundle.main.bundleIdentifier ?? "dev.yash.wave"

    static func read(_ key: String) -> String? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                kSecAttrAccount as String: key, kSecReturnData as String: true]
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }

    static func write(_ key: String, _ value: String) {
        delete(key)
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                kSecAttrAccount as String: key, kSecValueData as String: Data(value.utf8)]
        SecItemAdd(q as CFDictionary, nil)
    }

    static func delete(_ key: String) {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                kSecAttrAccount as String: key]
        SecItemDelete(q as CFDictionary)
    }
}
