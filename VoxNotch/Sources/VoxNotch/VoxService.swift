// VoxService.swift - HTTP client for the Python FastAPI sidecar

import Foundation

// MARK: - Response types

struct RecordStopResponse: Decodable {
    let audioPath: String
    let elapsed: Double

    enum CodingKeys: String, CodingKey {
        case audioPath = "audio_path"
        case elapsed
    }
}

struct TranscribeResponse: Decodable {
    let jobId: String

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
    }
}

struct FinalizeResponse: Decodable {
    let jobId: String

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
    }
}

struct JobStatusResponse: Decodable {
    let status: String
    let result: JobResult?
    let error: String?
}

struct JobResult: Decodable {
    let transcript: String?
    let speakerPreviews: [SpeakerPreviewDTO]
    let voiceprintMatches: [String: VoiceprintMatchDTO?]
    let notePath: String?
    let analysisOk: Bool?

    enum CodingKeys: String, CodingKey {
        case transcript
        case speakerPreviews = "speaker_previews"
        case voiceprintMatches = "voiceprint_matches"
        case notePath = "note_path"
        case analysisOk = "analysis_ok"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        transcript = try container.decodeIfPresent(String.self, forKey: .transcript)
        speakerPreviews =
            try container.decodeIfPresent([SpeakerPreviewDTO].self, forKey: .speakerPreviews) ?? []
        voiceprintMatches =
            try container.decodeIfPresent(
                [String: VoiceprintMatchDTO?].self, forKey: .voiceprintMatches) ?? [:]
        notePath = try container.decodeIfPresent(String.self, forKey: .notePath)
        analysisOk = try container.decodeIfPresent(Bool.self, forKey: .analysisOk)
    }
}

struct SpeakerPreviewDTO: Decodable {
    let label: String
    let textSnippet: String
    let bestSegmentStartSec: Double
    let bestSegmentEndSec: Double

    enum CodingKeys: String, CodingKey {
        case label
        case textSnippet = "text_snippet"
        case bestSegmentStartSec = "best_segment_start_sec"
        case bestSegmentEndSec = "best_segment_end_sec"
    }
}

struct VoiceprintMatchDTO: Decodable {
    let name: String
    let score: Double
    let confident: Bool
}

struct ConfigResponse: Decodable {
    let userName: String
    let languageHints: [String]
    let enableDiarization: Bool

    enum CodingKeys: String, CodingKey {
        case userName = "user_name"
        case languageHints = "language_hints"
        case enableDiarization = "enable_diarization"
    }
}

// MARK: - Service

@MainActor
class VoxService {
    static let shared = VoxService()

    private let port: Int = 7483
    private var baseURL: String { "http://127.0.0.1:\(port)" }
    private var serverProcess: Process?

    private init() {}

    // MARK: - Server lifecycle

    func ensureServerRunning() async throws {
        // Check if already running
        if await isServerHealthy() { return }

        // Launch the server
        startServer()

        // Wait for it to become healthy
        for _ in 0..<20 {
            try await Task.sleep(for: .milliseconds(500))
            if await isServerHealthy() { return }
        }
        throw VoxError.serverStartFailed
    }

    private func startServer() {
        guard let voxPath = findVoxProject() else {
            print("Could not find vox project directory")
            return
        }

        // Find uv binary
        let uvPath = findUV()

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [
            "-l", "-c",
            "\(uvPath) run vox-server --port \(port)",
        ]
        process.currentDirectoryURL = URL(fileURLWithPath: voxPath)
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice

        do {
            try process.run()
            serverProcess = process
            print("vox-server started (pid \(process.processIdentifier)) from \(voxPath)")
        } catch {
            print("Failed to start vox-server: \(error)")
        }
    }

    private func findVoxProject() -> String? {
        let candidates = [
            // Development: VoxNotch is inside the vox repo
            Bundle.main.bundlePath + "/../../..",
            // SwiftPM build: .build/debug/VoxNotch.app is deep inside repo
            Bundle.main.bundlePath + "/../../../../../..",
            // Hardcoded fallback
            NSHomeDirectory() + "/studio-kensense/vox",
        ]
        for path in candidates {
            let resolved = (path as NSString).standardizingPath
            if FileManager.default.fileExists(atPath: resolved + "/pyproject.toml") {
                return resolved
            }
        }
        return nil
    }

    private func findUV() -> String {
        let candidates = [
            NSHomeDirectory() + "/.local/bin/uv",
            NSHomeDirectory() + "/.cargo/bin/uv",
            "/opt/homebrew/bin/uv",
            "/usr/local/bin/uv",
        ]
        for path in candidates {
            if FileManager.default.fileExists(atPath: path) {
                return path
            }
        }
        return "uv"  // hope it's in PATH via bash -l
    }

    func stopServer() {
        serverProcess?.terminate()
        serverProcess = nil
    }

    private nonisolated func isServerHealthy() async -> Bool {
        guard let url = URL(string: "http://127.0.0.1:7483/health") else { return false }
        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    // MARK: - Recording

    func startRecording() async throws {
        try await ensureServerRunning()
        let _: [String: String] = try await post("/record/start")
    }

    func stopRecording() async throws -> RecordStopResponse {
        return try await post("/record/stop")
    }

    func abortRecording() async throws {
        let _: [String: String] = try await post("/record/abort")
    }

    // MARK: - Pipeline

    func transcribe(
        audioPath: String,
        languageHints: [String],
        context: String?
    ) async throws -> TranscribeResponse {
        var body: [String: Any] = [
            "audio_path": audioPath,
            "language_hints": languageHints,
            "enable_diarization": true,
        ]
        if let context = context {
            body["context"] = context
        }
        return try await post("/pipeline/transcribe", body: body)
    }

    func getJobStatus(jobId: String) async throws -> JobStatusResponse {
        return try await get("/pipeline/status/\(jobId)")
    }

    func finalize(
        audioPath: String,
        transcript: String,
        sessionName: String,
        speakerMapping: [String: String],
        people: [String]
    ) async throws -> FinalizeResponse {
        let body: [String: Any] = [
            "audio_path": audioPath,
            "transcript": transcript,
            "session_name": sessionName,
            "speaker_mapping": speakerMapping,
            "people": people,
        ]
        return try await post("/pipeline/finalize", body: body)
    }

    func fetchConfig() async throws -> ConfigResponse {
        try await ensureServerRunning()
        return try await get("/config")
    }

    // MARK: - Audio clips

    func speakerClipURL(audioPath: String, startSec: Double, endSec: Double) -> URL? {
        // We'll use a POST endpoint and play the response
        return URL(string: "\(baseURL)/speakers/clip")
    }

    func fetchSpeakerClip(audioPath: String, startSec: Double, endSec: Double) async throws
        -> Data
    {
        let body: [String: Any] = [
            "audio_path": audioPath,
            "start_sec": startSec,
            "end_sec": endSec,
        ]
        let jsonData = try JSONSerialization.data(withJSONObject: body)
        var request = URLRequest(url: URL(string: "\(baseURL)/speakers/clip")!)
        request.httpMethod = "POST"
        request.httpBody = jsonData
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200
        else {
            throw VoxError.serverError("Failed to fetch speaker clip")
        }
        return data
    }

    // MARK: - HTTP helpers

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let url = URL(string: "\(baseURL)\(path)")!
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200
        else {
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
            let body = String(data: data, encoding: .utf8) ?? ""
            throw VoxError.serverError("GET \(path) returned \(statusCode): \(body)")
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func post<T: Decodable>(_ path: String, body: [String: Any]? = nil) async throws -> T {
        var request = URLRequest(url: URL(string: "\(baseURL)\(path)")!)
        request.httpMethod = "POST"
        if let body = body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
            (200..<300).contains(httpResponse.statusCode)
        else {
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
            let responseBody = String(data: data, encoding: .utf8) ?? ""
            throw VoxError.serverError("POST \(path) returned \(statusCode): \(responseBody)")
        }
        return try JSONDecoder().decode(T.self, from: data)
    }
}

enum VoxError: LocalizedError {
    case serverStartFailed
    case serverError(String)

    var errorDescription: String? {
        switch self {
        case .serverStartFailed:
            return "Could not start the Vox server"
        case .serverError(let msg):
            return msg
        }
    }
}
