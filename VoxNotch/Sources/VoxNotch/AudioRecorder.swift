// AudioRecorder.swift - Native macOS audio recording via AVAudioRecorder
// Records locally in the Swift app so macOS mic permissions work properly.

import AVFoundation
import Foundation

@MainActor
class AudioRecorder: ObservableObject {
    static let shared = AudioRecorder()

    @Published var isRecording = false
    @Published var elapsed: TimeInterval = 0

    private var recorder: AVAudioRecorder?
    private var timer: Timer?
    private var startTime: Date?
    private var outputURL: URL?

    private init() {}

    /// Start recording to a temp file. Returns immediately.
    func start() async throws {
        // Request mic permission if needed
        let status = AVCaptureDevice.authorizationStatus(for: .audio)
        if status == .notDetermined {
            let granted = await AVCaptureDevice.requestAccess(for: .audio)
            if !granted {
                throw RecorderError.permissionDenied
            }
        } else if status == .denied || status == .restricted {
            throw RecorderError.permissionDenied
        }

        // Create temp file
        let tempDir = FileManager.default.temporaryDirectory
        let filename = "vox-\(Int(Date().timeIntervalSince1970)).m4a"
        let url = tempDir.appendingPathComponent(filename)
        outputURL = url

        // Configure recorder
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 44100,
            AVNumberOfChannelsKey: 1,
            AVEncoderBitRateKey: 128_000,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue,
        ]

        let rec = try AVAudioRecorder(url: url, settings: settings)
        rec.prepareToRecord()

        if !rec.record() {
            throw RecorderError.recordFailed
        }

        recorder = rec
        isRecording = true
        startTime = Date()
        elapsed = 0

        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self = self, let start = self.startTime else { return }
                self.elapsed = Date().timeIntervalSince(start)
            }
        }
    }

    /// Stop recording. Returns the path to the audio file.
    func stop() -> String? {
        timer?.invalidate()
        timer = nil

        guard let rec = recorder else { return nil }
        rec.stop()
        isRecording = false
        recorder = nil

        guard let url = outputURL else { return nil }

        // Verify file has content
        let size = (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int) ?? 0
        if size < 1000 {
            try? FileManager.default.removeItem(at: url)
            return nil
        }

        return url.path
    }

    /// Abort recording, discard audio.
    func abort() {
        timer?.invalidate()
        timer = nil

        recorder?.stop()
        recorder = nil
        isRecording = false
        elapsed = 0

        if let url = outputURL {
            try? FileManager.default.removeItem(at: url)
        }
        outputURL = nil
    }
}

enum RecorderError: LocalizedError {
    case permissionNeeded
    case permissionDenied
    case recordFailed

    var errorDescription: String? {
        switch self {
        case .permissionNeeded:
            return "Microphone permission needed - please try again"
        case .permissionDenied:
            return "Microphone access denied. Enable in System Settings > Privacy > Microphone"
        case .recordFailed:
            return "Failed to start recording"
        }
    }
}
