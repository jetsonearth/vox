// VoxViewModel.swift - Core state machine for the Vox notch app

import AVFoundation
import Combine
import SwiftUI

// MARK: - State

enum VoxState: Equatable {
    case idle
    case recording
    case transcribing
    case configuring  // post-recording panel
    case identifying  // speaker flashcard (3+ people)
    case analyzing
    case done

    static func == (lhs: VoxState, rhs: VoxState) -> Bool {
        switch (lhs, rhs) {
        case (.idle, .idle),
            (.recording, .recording),
            (.transcribing, .transcribing),
            (.configuring, .configuring),
            (.identifying, .identifying),
            (.analyzing, .analyzing),
            (.done, .done):
            return true
        default:
            return false
        }
    }
}

enum NotchOpenState {
    case closed
    case open
}

// MARK: - Speaker data

struct SpeakerPreview: Identifiable {
    let id: String  // label
    let label: String
    let textSnippet: String
    let clipStartSec: Double
    let clipEndSec: Double
}

struct VoiceprintMatchInfo {
    let name: String
    let score: Double
    let confident: Bool
}

// MARK: - ViewModel

@MainActor
class VoxViewModel: ObservableObject {
    // Notch state
    @Published var notchState: NotchOpenState = .closed
    @Published var voxState: VoxState = .idle
    @Published var closedNotchSize: CGSize = .init(width: 185, height: 32)

    // Recording
    @Published var recordingElapsed: TimeInterval = 0

    // Transcription results
    @Published var transcript: String = ""
    @Published var speakerPreviews: [SpeakerPreview] = []
    @Published var voiceprintMatches: [String: VoiceprintMatchInfo] = [:]
    @Published var audioPath: String = ""
    @Published var jobId: String = ""

    // Configuration (post-recording panel)
    @Published var sessionName: String = ""
    @Published var participantNames: String = ""  // comma-separated
    @Published var languageHints: String = "en, zh"
    @Published var context: String = ""

    // Speaker identification (flashcard)
    @Published var currentFlashcardIndex: Int = 0
    @Published var speakerMapping: [String: String] = [:]  // SPEAKER_XX -> name

    // Done state
    @Published var doneNotePath: String = ""

    // Error
    @Published var errorMessage: String?

    // Config from server
    @Published var userName: String = "Jetson"

    // Timer for recording elapsed
    private var recordingTimer: Timer?
    private var pollingTimer: Timer?

    var screenUUID: String?

    init(screenUUID: String? = nil) {
        self.screenUUID = screenUUID
        self.closedNotchSize = NotchSizing.closedSize()
    }

    // MARK: - Notch open/close

    var notchSize: CGSize {
        switch voxState {
        case .idle:
            return closedNotchSize
        case .recording:
            return CGSize(
                width: NotchSizing.recordingWidth,
                height: closedNotchSize.height
            )
        case .transcribing, .analyzing:
            return CGSize(
                width: NotchSizing.recordingWidth,
                height: closedNotchSize.height
            )
        case .configuring:
            return CGSize(
                width: NotchSizing.openWidth,
                height: NotchSizing.configHeight
            )
        case .identifying:
            return CGSize(
                width: NotchSizing.openWidth,
                height: NotchSizing.flashcardHeight
            )
        case .done:
            return CGSize(
                width: NotchSizing.doneWidth,
                height: NotchSizing.doneHeight
            )
        }
    }

    var isExpanded: Bool {
        switch voxState {
        case .configuring, .identifying:
            return true
        default:
            return false
        }
    }

    func open() {
        notchState = .open
    }

    func close() {
        notchState = .closed
        if voxState == .done {
            voxState = .idle
        }
    }

    // MARK: - Recording (native AVAudioRecorder - no sox dependency)

    private let recorder = AudioRecorder.shared

    func startRecording() {
        Task {
            do {
                try await recorder.start()
                voxState = .recording
                notchState = .open
                recordingElapsed = 0
                recordingTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) {
                    [weak self] _ in
                    Task { @MainActor [weak self] in
                        guard let self = self else { return }
                        self.recordingElapsed = self.recorder.elapsed
                    }
                }
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    func stopRecording() {
        recordingTimer?.invalidate()
        recordingTimer = nil
        guard let path = recorder.stop() else {
            errorMessage = "Recording failed - no audio captured"
            voxState = .idle
            return
        }
        audioPath = path
        recordingElapsed = recorder.elapsed
        voxState = .configuring
        notchState = .open
    }

    func abortRecording() {
        recordingTimer?.invalidate()
        recordingTimer = nil
        recorder.abort()
        voxState = .idle
        notchState = .closed
        recordingElapsed = 0
    }

    // MARK: - Processing

    func startTranscription() {
        guard !audioPath.isEmpty else { return }
        voxState = .transcribing

        let hints = languageHints
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }

        Task {
            do {
                let result = try await VoxService.shared.transcribe(
                    audioPath: audioPath,
                    languageHints: hints,
                    context: context.isEmpty ? nil : context
                )
                jobId = result.jobId
                startPolling()
            } catch {
                errorMessage = "Transcription failed: \(error.localizedDescription)"
                voxState = .configuring
            }
        }
    }

    private func startPolling() {
        pollingTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) {
            [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.pollJob()
            }
        }
    }

    private func pollJob() async {
        guard !jobId.isEmpty else { return }
        do {
            let status = try await VoxService.shared.getJobStatus(jobId: jobId)
            if status.status == "completed", let result = status.result {
                pollingTimer?.invalidate()
                pollingTimer = nil
                transcript = result.transcript ?? ""
                speakerPreviews = result.speakerPreviews.map {
                    SpeakerPreview(
                        id: $0.label,
                        label: $0.label,
                        textSnippet: $0.textSnippet,
                        clipStartSec: $0.bestSegmentStartSec,
                        clipEndSec: $0.bestSegmentEndSec
                    )
                }
                voiceprintMatches = Dictionary(
                    uniqueKeysWithValues: result.voiceprintMatches.compactMap { key, value in
                        guard let v = value else { return nil }
                        return (
                            key,
                            VoiceprintMatchInfo(
                                name: v.name, score: v.score, confident: v.confident)
                        )
                    })

                // Auto-assign Jetson via voiceprint
                for (label, match) in voiceprintMatches where match.confident
                    && match.name == userName
                {
                    speakerMapping[label] = userName
                }

                handlePostTranscription()
            } else if status.status == "failed" {
                pollingTimer?.invalidate()
                pollingTimer = nil
                errorMessage = status.error ?? "Transcription failed"
                voxState = .configuring
            }
        } catch {
            // Keep polling on network errors
        }
    }

    private func handlePostTranscription() {
        let unknownSpeakers = speakerPreviews.filter { speakerMapping[$0.label] == nil }

        if unknownSpeakers.isEmpty && speakerPreviews.isEmpty {
            // No speakers detected (no diarization) - just finalize
            finalize()
        } else if unknownSpeakers.isEmpty {
            // All speakers already identified via voiceprint
            finalize()
        } else {
            // Show flashcard UI - user tags each speaker
            // Available names = [Jetson] + whatever they typed in "Who else?"
            currentFlashcardIndex = 0
            voxState = .identifying
        }
    }

    // MARK: - Speaker flashcard

    var unknownSpeakers: [SpeakerPreview] {
        speakerPreviews.filter { speakerMapping[$0.label] == nil }
    }

    var currentFlashcardSpeaker: SpeakerPreview? {
        let unknown = unknownSpeakers
        guard currentFlashcardIndex < unknown.count else { return nil }
        return unknown[currentFlashcardIndex]
    }

    var availableNames: [String] {
        let assigned = Set(speakerMapping.values)
        let others = participantNames
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        let allNames = [userName] + others
        return allNames.filter { !assigned.contains($0) }
    }

    func assignSpeaker(name: String) {
        guard let speaker = currentFlashcardSpeaker else { return }
        speakerMapping[speaker.label] = name

        if unknownSpeakers.isEmpty {
            finalize()
        } else {
            currentFlashcardIndex = 0  // reset since unknownSpeakers changed
        }
    }

    // MARK: - Finalize

    func finalize() {
        voxState = .analyzing

        let people = participantNames
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }

        Task {
            do {
                let result = try await VoxService.shared.finalize(
                    audioPath: audioPath,
                    transcript: transcript,
                    sessionName: sessionName.isEmpty ? "Recording" : sessionName,
                    speakerMapping: speakerMapping,
                    people: people
                )
                jobId = result.jobId
                // Poll for finalization
                pollingTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) {
                    [weak self] _ in
                    Task { @MainActor [weak self] in
                        await self?.pollFinalize()
                    }
                }
            } catch {
                errorMessage = "Finalization failed: \(error.localizedDescription)"
                voxState = .configuring
            }
        }
    }

    private func pollFinalize() async {
        guard !jobId.isEmpty else { return }
        do {
            let status = try await VoxService.shared.getJobStatus(jobId: jobId)
            if status.status == "completed" {
                pollingTimer?.invalidate()
                pollingTimer = nil
                if let result = status.result {
                    doneNotePath = result.notePath ?? ""
                }
                voxState = .done
                // Auto-dismiss after 4 seconds
                Task {
                    try? await Task.sleep(for: .seconds(4))
                    await MainActor.run {
                        if self.voxState == .done {
                            self.close()
                            self.resetSession()
                        }
                    }
                }
            } else if status.status == "failed" {
                pollingTimer?.invalidate()
                pollingTimer = nil
                errorMessage = status.error ?? "Analysis failed"
                voxState = .configuring
            }
        } catch {
            // Keep polling
        }
    }

    func resetSession() {
        voxState = .idle
        transcript = ""
        speakerPreviews = []
        voiceprintMatches = [:]
        audioPath = ""
        jobId = ""
        sessionName = ""
        participantNames = ""
        context = ""
        speakerMapping = [:]
        currentFlashcardIndex = 0
        doneNotePath = ""
        errorMessage = nil
        recordingElapsed = 0
    }

    // MARK: - Helpers

    var formattedElapsed: String {
        let mins = Int(recordingElapsed) / 60
        let secs = Int(recordingElapsed) % 60
        return String(format: "%d:%02d", mins, secs)
    }
}
