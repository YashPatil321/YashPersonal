import Accelerate
import AudioToolbox
import CoreAudio
import Foundation
import QuartzCore

/// Band levels published by the analyzer, each 0...1.
public struct AudioLevels: Sendable {
    public var level: Float = 0
    public var bass: Float = 0
    public var mid: Float = 0
    public var treble: Float = 0
    /// Decaying pulse, 1 on a beat.
    public var beat: Float = 0
    public static let silent = AudioLevels()
}

/// FFT band analysis and beat detection, as described in desktop/README.md section 2.
public final class AudioAnalyzer: @unchecked Sendable {
    private let n = 1024
    private let log2n: vDSP_Length = 10
    private let fft: FFTSetup
    private var window: [Float]
    private var buffer: [Float] = []
    private var real: [Float]
    private var imag: [Float]
    private var mags: [Float]

    private var peaks: [Float] = [1e-4, 1e-4, 1e-4, 1e-4]
    private var smooth: [Float] = [0, 0, 0, 0]
    private var previousBass: Float = 0
    private var fluxHistory: [Float] = []
    private var lastBeat: CFTimeInterval = 0
    private var lastAudio: CFTimeInterval = 0

    private let lock = NSLock()

    public init() {
        fft = vDSP_create_fftsetup(10, FFTRadix(kFFTRadix2))!
        window = [Float](repeating: 0, count: n)
        vDSP_hann_window(&window, vDSP_Length(n), Int32(vDSP_HANN_NORM))
        real = [Float](repeating: 0, count: n / 2)
        imag = [Float](repeating: 0, count: n / 2)
        mags = [Float](repeating: 0, count: n / 2)
    }

    deinit { vDSP_destroy_fftsetup(fft) }

    /// Feed mono samples from the audio thread.
    public func process(_ samples: UnsafePointer<Float>, count: Int, sampleRate: Double) {
        buffer.append(contentsOf: UnsafeBufferPointer(start: samples, count: count))
        while buffer.count >= n {
            analyze(Array(buffer[0..<n]), sampleRate: sampleRate)
            buffer.removeFirst(n)
        }
    }

    private func analyze(_ block: [Float], sampleRate: Double) {
        var windowed = [Float](repeating: 0, count: n)
        vDSP_vmul(block, 1, window, 1, &windowed, 1, vDSP_Length(n))

        var rms: Float = 0
        vDSP_rmsqv(block, 1, &rms, vDSP_Length(n))

        real.withUnsafeMutableBufferPointer { rp in
            imag.withUnsafeMutableBufferPointer { ip in
                var split = DSPSplitComplex(realp: rp.baseAddress!, imagp: ip.baseAddress!)
                windowed.withUnsafeBufferPointer { wp in
                    wp.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: n / 2) {
                        vDSP_ctoz($0, 2, &split, 1, vDSP_Length(n / 2))
                    }
                }
                vDSP_fft_zrip(fft, &split, 1, log2n, FFTDirection(FFT_FORWARD))
                vDSP_zvmags(&split, 1, &mags, 1, vDSP_Length(n / 2))
            }
        }

        let binHz = sampleRate / Double(n)
        func band(_ lo: Double, _ hi: Double) -> Float {
            let a = max(1, Int(lo / binHz)), b = min(n / 2 - 1, Int(hi / binHz))
            guard b >= a else { return 0 }
            var sum: Float = 0
            for i in a...b { sum += mags[i] }
            return sqrt(sum / Float(b - a + 1))
        }
        let raw: [Float] = [rms, band(20, 150), band(150, 2000), band(2000, 8000)]

        let now = CACurrentMediaTime()
        lock.lock()
        defer { lock.unlock() }
        if rms > 1e-5 { lastAudio = now }
        for i in 0..<4 {
            peaks[i] = max(raw[i], peaks[i] * 0.995)
            let norm = min(1, raw[i] / max(peaks[i], 1e-4))
            let k: Float = norm > smooth[i] ? 0.5 : 0.08
            smooth[i] += (norm - smooth[i]) * k
        }

        let bassNorm = min(1, raw[1] / max(peaks[1], 1e-4))
        let flux = max(0, bassNorm - previousBass)
        previousBass = bassNorm
        let mean = fluxHistory.isEmpty ? 0 : fluxHistory.reduce(0, +) / Float(fluxHistory.count)
        if flux > 1.5 * mean && bassNorm > 0.3 && now - lastBeat >= 0.25 && fluxHistory.count >= 8 {
            lastBeat = now
        }
        fluxHistory.append(flux)
        if fluxHistory.count > 43 { fluxHistory.removeFirst() }
    }

    /// Thread-safe snapshot for the render loop.
    public func levels(at now: CFTimeInterval = CACurrentMediaTime()) -> AudioLevels {
        lock.lock()
        defer { lock.unlock() }
        // No audio for a while: report silence.
        if now - lastAudio > 1.0 { return .silent }
        let beat = lastBeat > 0 ? Float(pow(0.88, (now - lastBeat) * 60)) : 0
        return AudioLevels(level: smooth[0], bass: smooth[1], mid: smooth[2], treble: smooth[3], beat: beat)
    }

    public var hasRecentAudio: Bool {
        lock.lock(); defer { lock.unlock() }
        return CACurrentMediaTime() - lastAudio < 2
    }
}

/// Captures everything the Mac is playing with a Core Audio process tap (macOS 14.2+).
/// macOS asks for "System Audio Recording" permission the first time. The microphone is never used.
@available(macOS 14.2, *)
public final class SystemAudioTap: @unchecked Sendable {
    public let analyzer = AudioAnalyzer()

    private var tapID = AudioObjectID(kAudioObjectUnknown)
    private var aggregateID = AudioObjectID(kAudioObjectUnknown)
    private var procID: AudioDeviceIOProcID?
    private var format = AudioStreamBasicDescription()
    private let queue = DispatchQueue(label: "halo.audio", qos: .userInteractive)
    private var mono = [Float](repeating: 0, count: 8192)
    private var deviceListener: AudioObjectPropertyListenerBlock?
    public private(set) var isRunning = false
    public private(set) var lastError: String?

    public init() {}

    deinit { stop() }

    public func start() {
        guard !isRunning else { return }
        do {
            try startTap()
            isRunning = true
            lastError = nil
            listenForDeviceChanges()
        } catch {
            lastError = "\(error)"
            teardown()
        }
    }

    public func stop() {
        removeDeviceListener()
        teardown()
        isRunning = false
    }

    private struct TapError: Error, CustomStringConvertible {
        let description: String
        init(_ what: String, _ status: OSStatus) { description = "\(what) failed (\(status))" }
    }

    private func startTap() throws {
        let desc = CATapDescription(stereoGlobalTapButExcludeProcesses: [])
        desc.uuid = UUID()
        desc.muteBehavior = .unmuted
        desc.isPrivate = true
        desc.name = "Halo"

        var tap = AudioObjectID(kAudioObjectUnknown)
        var err = AudioHardwareCreateProcessTap(desc, &tap)
        guard err == noErr else { throw TapError("Creating the audio tap", err) }
        tapID = tap

        var addr = AudioObjectPropertyAddress(mSelector: kAudioTapPropertyFormat,
                                              mScope: kAudioObjectPropertyScopeGlobal,
                                              mElement: kAudioObjectPropertyElementMain)
        var size = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
        err = AudioObjectGetPropertyData(tapID, &addr, 0, nil, &size, &format)
        guard err == noErr else { throw TapError("Reading the tap format", err) }

        let outputUID = try Self.defaultOutputUID()
        let aggregate: [String: Any] = [
            kAudioAggregateDeviceNameKey: "Halo Audio Tap",
            kAudioAggregateDeviceUIDKey: UUID().uuidString,
            kAudioAggregateDeviceMainSubDeviceKey: outputUID,
            kAudioAggregateDeviceIsPrivateKey: true,
            kAudioAggregateDeviceIsStackedKey: false,
            kAudioAggregateDeviceTapAutoStartKey: true,
            kAudioAggregateDeviceSubDeviceListKey: [[kAudioSubDeviceUIDKey: outputUID]],
            kAudioAggregateDeviceTapListKey: [[
                kAudioSubTapDriftCompensationKey: true,
                kAudioSubTapUIDKey: desc.uuid.uuidString,
            ]],
        ]
        var agg = AudioObjectID(kAudioObjectUnknown)
        err = AudioHardwareCreateAggregateDevice(aggregate as CFDictionary, &agg)
        guard err == noErr else { throw TapError("Creating the aggregate device", err) }
        aggregateID = agg

        let sampleRate = format.mSampleRate
        let channels = Int(max(format.mChannelsPerFrame, 1))
        let nonInterleaved = (format.mFormatFlags & kAudioFormatFlagIsNonInterleaved) != 0
        let analyzer = self.analyzer

        err = AudioDeviceCreateIOProcIDWithBlock(&procID, aggregateID, queue) { [weak self] _, inInputData, _, _, _ in
            guard let self else { return }
            let list = UnsafeMutableAudioBufferListPointer(UnsafeMutablePointer(mutating: inInputData))
            guard let first = list.first, let data = first.mData else { return }
            if nonInterleaved {
                let frames = Int(first.mDataByteSize) / MemoryLayout<Float>.size
                let count = min(frames, self.mono.count)
                let l = data.assumingMemoryBound(to: Float.self)
                if list.count > 1, let rData = list[1].mData {
                    let r = rData.assumingMemoryBound(to: Float.self)
                    for i in 0..<count { self.mono[i] = (l[i] + r[i]) * 0.5 }
                } else {
                    for i in 0..<count { self.mono[i] = l[i] }
                }
                self.mono.withUnsafeBufferPointer { analyzer.process($0.baseAddress!, count: count, sampleRate: sampleRate) }
            } else {
                let samples = Int(first.mDataByteSize) / MemoryLayout<Float>.size
                let frames = min(samples / channels, self.mono.count)
                let p = data.assumingMemoryBound(to: Float.self)
                for i in 0..<frames {
                    var s: Float = 0
                    for c in 0..<channels { s += p[i * channels + c] }
                    self.mono[i] = s / Float(channels)
                }
                self.mono.withUnsafeBufferPointer { analyzer.process($0.baseAddress!, count: frames, sampleRate: sampleRate) }
            }
        }
        guard err == noErr else { throw TapError("Creating the audio callback", err) }
        err = AudioDeviceStart(aggregateID, procID)
        guard err == noErr else { throw TapError("Starting audio capture", err) }
    }

    private func teardown() {
        if aggregateID != kAudioObjectUnknown {
            AudioDeviceStop(aggregateID, procID)
            if let procID { AudioDeviceDestroyIOProcID(aggregateID, procID) }
            AudioHardwareDestroyAggregateDevice(aggregateID)
        }
        if tapID != kAudioObjectUnknown { AudioHardwareDestroyProcessTap(tapID) }
        procID = nil
        aggregateID = AudioObjectID(kAudioObjectUnknown)
        tapID = AudioObjectID(kAudioObjectUnknown)
    }

    private static var defaultOutputAddress = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDefaultSystemOutputDevice,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)

    private static func defaultOutputUID() throws -> String {
        var device = AudioObjectID(kAudioObjectUnknown)
        var size = UInt32(MemoryLayout<AudioObjectID>.size)
        var addr = defaultOutputAddress
        var err = AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &device)
        guard err == noErr else { throw TapError("Finding the output device", err) }

        var uidAddr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyDeviceUID,
                                                 mScope: kAudioObjectPropertyScopeGlobal,
                                                 mElement: kAudioObjectPropertyElementMain)
        var uid: Unmanaged<CFString>?
        size = UInt32(MemoryLayout<Unmanaged<CFString>?>.size)
        err = AudioObjectGetPropertyData(device, &uidAddr, 0, nil, &size, &uid)
        guard err == noErr, let uid else { throw TapError("Reading the output device", err) }
        return uid.takeRetainedValue() as String
    }

    /// Rebuild the tap when the default output changes (headphones plugged in, AirPlay, ...).
    private func listenForDeviceChanges() {
        guard deviceListener == nil else { return }
        let block: AudioObjectPropertyListenerBlock = { [weak self] _, _ in
            DispatchQueue.main.async {
                guard let self, self.isRunning else { return }
                self.teardown()
                self.isRunning = false
                self.start()
            }
        }
        deviceListener = block
        var addr = Self.defaultOutputAddress
        AudioObjectAddPropertyListenerBlock(AudioObjectID(kAudioObjectSystemObject), &addr, DispatchQueue.main, block)
    }

    private func removeDeviceListener() {
        guard let block = deviceListener else { return }
        var addr = Self.defaultOutputAddress
        AudioObjectRemovePropertyListenerBlock(AudioObjectID(kAudioObjectSystemObject), &addr, DispatchQueue.main, block)
        deviceListener = nil
    }
}
