import XCTest
@testable import LyricsKit

final class LyricsKitTests: XCTestCase {
    private func fixture() throws -> String {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent("fixtures/lyricsfile-sample.yaml")
        return try String(contentsOf: url, encoding: .utf8)
    }

    func testLyricsfileLinesAndWords() throws {
        let lyrics = LyricsfileParser.parse(try fixture())
        XCTAssertEqual(lyrics.source, .wordSynced)
        XCTAssertEqual(lyrics.lines.count, 4)

        let first = lyrics.lines[0]
        XCTAssertEqual(first.text, "Hello there world")
        XCTAssertEqual(first.start, 1.0, accuracy: 1e-9)
        XCTAssertEqual(first.end, 3.0, accuracy: 1e-9)
        XCTAssertEqual(first.words.map(\.text), ["Hello", "there", "world"])
        XCTAssertEqual(first.words[1].start, 1.5, accuracy: 1e-9)
        XCTAssertEqual(first.words.map(\.spaceAfter), [true, true, false])
    }

    func testQuotingAndEscapes() throws {
        let lyrics = LyricsfileParser.parse(try fixture())
        let second = lyrics.lines[1]
        XCTAssertEqual(second.text, "It's a \"test\" line")
        XCTAssertEqual(second.words.map(\.text), ["It's", "a", "\"test\"", "line"])
        XCTAssertEqual(second.words.map(\.spaceAfter), [true, true, true, false])
    }

    func testLineWithoutWordsIsInterpolated() throws {
        let lyrics = LyricsfileParser.parse(try fixture())
        let third = lyrics.lines[2]
        XCTAssertEqual(third.text, "No words here, just a line")
        XCTAssertEqual(third.words.count, 6)
        XCTAssertEqual(third.words.first!.start, 7.0, accuracy: 1e-9)
        XCTAssertEqual(third.words.last!.end, 9.0, accuracy: 1e-6)
        // Longer words get more time.
        XCTAssertGreaterThan(third.words[0].end - third.words[0].start, third.words[4].end - third.words[4].start)
    }

    func testMissingEndAndStopsAtPlainBlock() throws {
        let lyrics = LyricsfileParser.parse(try fixture())
        let last = lyrics.lines[3]
        XCTAssertEqual(last.text, "Last line without an end")
        XCTAssertEqual(last.end, 14.0, accuracy: 1e-9)
        XCTAssertFalse(lyrics.lines.contains { $0.text.contains("plain") })
    }

    func testFoldedScalars() {
        let yaml = """
        lines:
        - text: "a long line that the emitter
            folded onto two lines"
          start_ms: 0
          end_ms: 1000
        - text: plain scalar that also
            wraps around
          start_ms: 2000
        """
        let lyrics = LyricsfileParser.parse(yaml)
        XCTAssertEqual(lyrics.lines.map(\.text), ["a long line that the emitter folded onto two lines",
                                                  "plain scalar that also wraps around"])
    }

    func testLRCInterpolation() {
        let lrc = """
        [ar:Someone]
        [00:01.00]one two three
        [00:03.50]
        [00:05.00]last line
        """
        let lyrics = LRCParser.parse(lrc)
        XCTAssertEqual(lyrics.source, .lineSynced)
        XCTAssertEqual(lyrics.lines.count, 3)
        XCTAssertEqual(lyrics.lines[0].words.map(\.text), ["one", "two", "three"])
        XCTAssertEqual(lyrics.lines[0].words.last!.end, 3.5, accuracy: 1e-6)
        XCTAssertTrue(lyrics.lines[1].isInstrumental)
        XCTAssertNil(lyrics.state(at: 4.0))
    }

    func testEnhancedLRCAndOffset() {
        let lrc = """
        [offset:+500]
        [00:10.00]<00:10.00>Hi <00:10.40>there<00:11.00>
        """
        let lyrics = LRCParser.parse(lrc)
        XCTAssertEqual(lyrics.source, .wordSynced)
        let line = lyrics.lines[0]
        XCTAssertEqual(line.start, 9.5, accuracy: 1e-9)
        XCTAssertEqual(line.words.map(\.text), ["Hi", "there"])
        XCTAssertEqual(line.words[1].start, 9.9, accuracy: 1e-9)
        XCTAssertEqual(line.words[1].end, 10.5, accuracy: 1e-9)
    }

    func testStateLookup() throws {
        let lyrics = LyricsfileParser.parse(try fixture())
        XCTAssertNil(lyrics.state(at: 0.5))
        XCTAssertEqual(lyrics.state(at: 1.25), LyricState(lineIndex: 0, wordIndex: 0, wordProgress: 0.5))
        XCTAssertEqual(lyrics.state(at: 2.5)?.wordIndex, 2)
        // Lingers 1.5 s past the end, but the next line wins when it starts.
        XCTAssertEqual(lyrics.state(at: 3.9)?.lineIndex, 0)
        XCTAssertEqual(lyrics.state(at: 4.0)?.lineIndex, 1)
        XCTAssertNil(lyrics.state(at: 100))
    }

    func testDecodePrefersWordSync() throws {
        let json: [String: Any] = [
            "instrumental": false, "hasWordSync": true,
            "lyricsfile": try fixture(), "syncedLyrics": "[00:01.00]other",
        ]
        XCTAssertEqual(LRCLibClient.decode(json).source, .wordSynced)
        XCTAssertEqual(LRCLibClient.decode(["instrumental": true]).source, .none)
        XCTAssertEqual(LRCLibClient.decode(["syncedLyrics": "[00:01.00]x"]).source, .lineSynced)
    }
}
