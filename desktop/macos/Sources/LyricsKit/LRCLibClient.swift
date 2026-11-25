import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Fetches lyrics from lrclib.net and picks the richest timing available.
public final class LRCLibClient: @unchecked Sendable {
    public struct Query: Hashable, Sendable {
        public var title: String
        public var artist: String
        public var album: String
        public var duration: Double
        public init(title: String, artist: String, album: String, duration: Double) {
            self.title = title; self.artist = artist; self.album = album; self.duration = duration
        }
        var cacheKey: String { "\(artist.lowercased())|\(title.lowercased())" }
    }

    private let session: URLSession
    private var cache: [String: Lyrics] = [:]
    private let lock = NSLock()
    private let base = "https://lrclib.net/api"

    public init(session: URLSession = .shared) { self.session = session }

    public func lyrics(for q: Query) async -> Lyrics {
        if let cached = cached(q.cacheKey) { return cached }

        var result = Lyrics.none
        var json = await get("/get", query(q, includeAlbum: true))
        if json == nil { json = await get("/get", query(q, includeAlbum: false)) }
        if let json {
            result = LRCLibClient.decode(json)
        } else if let list = await getArray("/search", [("track_name", q.title), ("artist_name", q.artist)]) {
            let match = list.first { item in
                guard let d = item["duration"] as? Double else { return false }
                return abs(d - q.duration) <= 3 || q.duration <= 0
            }
            if let match { result = LRCLibClient.decode(match) }
        }
        store(q.cacheKey, result)
        return result
    }

    private func cached(_ key: String) -> Lyrics? { lock.withLock { cache[key] } }
    private func store(_ key: String, _ value: Lyrics) { lock.withLock { cache[key] = value } }

    /// Turns one LRCLIB record into lyrics, preferring word timings.
    public static func decode(_ json: [String: Any]) -> Lyrics {
        if (json["instrumental"] as? Bool) == true { return .none }
        if (json["hasWordSync"] as? Bool) == true, let file = json["lyricsfile"] as? String {
            let parsed = LyricsfileParser.parse(file)
            if !parsed.lines.isEmpty { return parsed }
        }
        if let lrc = json["syncedLyrics"] as? String, !lrc.isEmpty {
            let parsed = LRCParser.parse(lrc)
            if !parsed.lines.isEmpty { return parsed }
        }
        return .none
    }

    private func query(_ q: Query, includeAlbum: Bool) -> [(String, String)] {
        var items = [("artist_name", q.artist), ("track_name", q.title)]
        if includeAlbum && !q.album.isEmpty { items.append(("album_name", q.album)) }
        if q.duration > 0 { items.append(("duration", String(Int(q.duration.rounded())))) }
        return items
    }

    private func request(_ path: String, _ items: [(String, String)]) async -> Any? {
        var comps = URLComponents(string: base + path)!
        comps.queryItems = items.map { URLQueryItem(name: $0.0, value: $0.1) }
        guard let url = comps.url else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 10)
        req.setValue("Lyra/1.0 (desktop lyrics app)", forHTTPHeaderField: "User-Agent")
        return await withCheckedContinuation { (cont: CheckedContinuation<Any?, Never>) in
            session.dataTask(with: req) { data, response, _ in
                guard let data, let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                    cont.resume(returning: nil); return
                }
                cont.resume(returning: try? JSONSerialization.jsonObject(with: data))
            }.resume()
        }
    }

    private func get(_ path: String, _ items: [(String, String)]) async -> [String: Any]? {
        await request(path, items) as? [String: Any]
    }

    private func getArray(_ path: String, _ items: [(String, String)]) async -> [[String: Any]]? {
        await request(path, items) as? [[String: Any]]
    }
}
