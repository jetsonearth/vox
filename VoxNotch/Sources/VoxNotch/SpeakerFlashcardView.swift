// SpeakerFlashcardView.swift - Audio flashcard for 3+ person speaker identification
// Hear a clip, tap a name. That's it.

import AVFoundation
import SwiftUI

struct SpeakerFlashcardView: View {
    @EnvironmentObject var vm: VoxViewModel
    @State private var audioPlayer: AVAudioPlayer?
    @State private var isPlaying = false
    @State private var isLoading = false
    @State private var appeared = false
    @State private var buttonScale: [String: CGFloat] = [:]

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Who is this?")
                    .font(.system(size: 15, weight: .semibold, design: .rounded))
                    .foregroundStyle(.white)

                Spacer()

                // Progress pills
                HStack(spacing: 4) {
                    ForEach(0..<vm.speakerPreviews.count, id: \.self) { i in
                        let label = vm.speakerPreviews[i].label
                        let identified = vm.speakerMapping[label] != nil
                        Capsule()
                            .fill(identified ? .green : .white.opacity(0.15))
                            .frame(width: identified ? 12 : 8, height: 4)
                            .animation(.spring(response: 0.3), value: identified)
                    }
                }
            }
            .padding(.horizontal, 20)
            .frame(height: vm.closedNotchSize.height + 16)

            Spacer()

            if let speaker = vm.currentFlashcardSpeaker {
                // Play button
                Button {
                    playClip(speaker: speaker)
                } label: {
                    ZStack {
                        // Ripple when playing
                        if isPlaying {
                            Circle()
                                .stroke(.blue.opacity(0.2), lineWidth: 2)
                                .frame(width: 64, height: 64)
                                .scaleEffect(isPlaying ? 1.4 : 1.0)
                                .opacity(isPlaying ? 0 : 0.5)
                                .animation(
                                    .easeOut(duration: 1.2).repeatForever(autoreverses: false),
                                    value: isPlaying
                                )
                        }

                        Circle()
                            .fill(.white.opacity(0.08))
                            .frame(width: 52, height: 52)

                        if isLoading {
                            ProgressView()
                                .scaleEffect(0.7)
                                .tint(.white)
                        } else {
                            Image(
                                systemName: isPlaying
                                    ? "waveform" : "play.fill"
                            )
                            .font(.system(size: isPlaying ? 18 : 16))
                            .foregroundStyle(isPlaying ? .blue : .white.opacity(0.8))
                            .symbolEffect(.variableColor.iterative, isActive: isPlaying)
                        }
                    }
                }
                .buttonStyle(.plain)

                // Text preview
                Text(speaker.textSnippet)
                    .font(.system(size: 11, design: .rounded))
                    .foregroundStyle(.white.opacity(0.35))
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 30)
                    .padding(.top, 10)

                Spacer()

                // Name buttons
                HStack(spacing: 8) {
                    ForEach(vm.availableNames, id: \.self) { name in
                        Button {
                            withAnimation(.spring(response: 0.25, dampingFraction: 0.7)) {
                                buttonScale[name] = 0.9
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                                withAnimation(.spring(response: 0.3)) {
                                    audioPlayer?.stop()
                                    isPlaying = false
                                    vm.assignSpeaker(name: name)
                                    buttonScale[name] = 1.0
                                }
                            }
                        } label: {
                            Text(name)
                                .font(.system(size: 13, weight: .semibold, design: .rounded))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 20)
                                .padding(.vertical, 10)
                                .background(
                                    RoundedRectangle(cornerRadius: 10)
                                        .fill(.blue.gradient)
                                )
                                .scaleEffect(buttonScale[name] ?? 1.0)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.bottom, 18)
            }
        }
        .opacity(appeared ? 1 : 0)
        .onAppear {
            withAnimation(.easeOut(duration: 0.3)) { appeared = true }
        }
    }

    private func playClip(speaker: SpeakerPreview) {
        guard !isLoading else { return }

        if isPlaying {
            audioPlayer?.stop()
            isPlaying = false
            return
        }

        isLoading = true
        Task {
            do {
                let data = try await VoxService.shared.fetchSpeakerClip(
                    audioPath: vm.audioPath,
                    startSec: speaker.clipStartSec,
                    endSec: speaker.clipEndSec
                )
                let player = try AVAudioPlayer(data: data)
                audioPlayer = player
                player.play()
                isPlaying = true
                isLoading = false

                Task {
                    try? await Task.sleep(
                        for: .seconds(speaker.clipEndSec - speaker.clipStartSec + 0.3))
                    await MainActor.run { isPlaying = false }
                }
            } catch {
                isLoading = false
            }
        }
    }
}
