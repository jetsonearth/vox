// SpeakerFlashcardView.swift - Identify speakers by reading their lines

import AVFoundation
import SwiftUI

struct SpeakerFlashcardView: View {
    @EnvironmentObject var vm: VoxViewModel
    @State private var audioPlayer: AVAudioPlayer?
    @State private var isPlaying = false
    @State private var isLoading = false
    @State private var appeared = false

    var body: some View {
        VStack(spacing: 0) {
            // Spacer for notch
            Color.clear
                .frame(height: vm.closedNotchSize.height)

            // Header
            HStack {
                if let speaker = vm.currentFlashcardSpeaker {
                    Text("Who is \(speaker.label)?")
                        .font(.system(size: 14, weight: .semibold, design: .rounded))
                        .foregroundStyle(.white)
                } else {
                    Text("All tagged")
                        .font(.system(size: 14, weight: .semibold, design: .rounded))
                        .foregroundStyle(.white)
                }

                Spacer()

                // Undo
                if !vm.speakerMapping.isEmpty {
                    Button {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                            audioPlayer?.stop()
                            isPlaying = false
                            vm.undoLastSpeaker()
                        }
                    } label: {
                        Image(systemName: "arrow.uturn.backward")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(.white.opacity(0.4))
                            .frame(width: 22, height: 22)
                            .background(.white.opacity(0.08))
                            .clipShape(Circle())
                    }
                    .buttonStyle(.plain)
                }

                // Progress pills
                HStack(spacing: 3) {
                    ForEach(0..<vm.speakerPreviews.count, id: \.self) { i in
                        let label = vm.speakerPreviews[i].label
                        let identified = vm.speakerMapping[label] != nil
                        Circle()
                            .fill(identified ? .green : .white.opacity(0.15))
                            .frame(width: 6, height: 6)
                            .animation(.spring(response: 0.3), value: identified)
                    }
                }
            }
            .padding(.horizontal, 18)
            .padding(.top, 8)

            if let speaker = vm.currentFlashcardSpeaker {
                // Transcript preview - scrollable
                ScrollView(.vertical, showsIndicators: false) {
                    Text(speaker.textSnippet)
                        .font(.system(size: 12, design: .rounded))
                        .foregroundStyle(.white.opacity(0.6))
                        .lineSpacing(3)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 18)
                }
                .frame(maxHeight: .infinity)
                .padding(.top, 10)

                // Play button + name buttons row
                HStack(spacing: 10) {
                    // Play audio clip
                    Button {
                        playClip(speaker: speaker)
                    } label: {
                        Image(systemName: isPlaying ? "stop.fill" : "play.fill")
                            .font(.system(size: 10))
                            .foregroundStyle(isPlaying ? .blue : .white.opacity(0.5))
                            .frame(width: 28, height: 28)
                            .background(.white.opacity(0.08))
                            .clipShape(Circle())
                    }
                    .buttonStyle(.plain)

                    // Name buttons
                    ForEach(vm.availableNames, id: \.self) { name in
                        Button {
                            withAnimation(.spring(response: 0.25, dampingFraction: 0.7)) {
                                audioPlayer?.stop()
                                isPlaying = false
                                vm.assignSpeaker(name: name)
                            }
                        } label: {
                            Text(name)
                                .font(.system(size: 12, weight: .semibold, design: .rounded))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 7)
                                .background(RoundedRectangle(cornerRadius: 8).fill(.blue.gradient))
                        }
                        .buttonStyle(.plain)
                    }

                    // Skip this speaker (keep raw label)
                    Button {
                        withAnimation(.spring(response: 0.25, dampingFraction: 0.7)) {
                            audioPlayer?.stop()
                            isPlaying = false
                            vm.skipCurrentSpeaker()
                        }
                    } label: {
                        Text("Skip")
                            .font(.system(size: 12, weight: .medium, design: .rounded))
                            .foregroundStyle(.white.opacity(0.4))
                            .padding(.horizontal, 10)
                            .padding(.vertical, 7)
                            .background(.white.opacity(0.05))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                    .buttonStyle(.plain)
                }
                .padding(.horizontal, 18)
                .padding(.bottom, 14)
            } else {
                // All done - continue button
                Spacer()
                Button {
                    vm.finalize()
                } label: {
                    HStack(spacing: 5) {
                        Text("Continue")
                            .font(.system(size: 13, weight: .semibold, design: .rounded))
                        Image(systemName: "arrow.right")
                            .font(.system(size: 11, weight: .semibold))
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(RoundedRectangle(cornerRadius: 10).fill(.blue.gradient))
                }
                .buttonStyle(.plain)
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
