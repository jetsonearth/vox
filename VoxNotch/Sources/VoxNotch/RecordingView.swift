// RecordingView.swift - Content sits beside the physical notch, not behind it

import SwiftUI

struct RecordingView: View {
    @EnvironmentObject var vm: VoxViewModel
    @ObservedObject private var recorder = AudioRecorder.shared

    // Each bar gets a slightly different scale from the audio level
    private let barOffsets: [Float] = [0.6, 0.85, 1.0, 0.75, 0.5]

    var body: some View {
        HStack(spacing: 0) {
            // LEFT of notch: waveform bars + timer
            HStack(spacing: 8) {
                // Live waveform bars driven by mic level
                HStack(spacing: 2) {
                    ForEach(0..<5, id: \.self) { i in
                        RoundedRectangle(cornerRadius: 1)
                            .fill(.red.opacity(0.6))
                            .frame(width: 2, height: barHeight(index: i))
                    }
                }
                .animation(.easeOut(duration: 0.08), value: recorder.audioLevel)

                Text(vm.formattedElapsed)
                    .font(.system(size: 12, weight: .semibold, design: .monospaced))
                    .foregroundStyle(.white.opacity(0.9))
            }
            .padding(.leading, 6)
            .frame(maxWidth: .infinity, alignment: .center)

            // CENTER: black gap matching the physical notch
            Rectangle()
                .fill(.black)
                .frame(width: vm.closedNotchSize.width - 10)

            // RIGHT of notch: stop + abort
            HStack(spacing: 6) {
                Button {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                        vm.stopRecording()
                    }
                } label: {
                    Image(systemName: "stop.fill")
                        .font(.system(size: 9))
                        .foregroundStyle(.white)
                        .frame(width: 22, height: 22)
                        .background(.white.opacity(0.15))
                        .clipShape(Circle())
                }
                .buttonStyle(.plain)

                Button {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                        vm.abortRecording()
                    }
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 8, weight: .bold))
                        .foregroundStyle(.white.opacity(0.4))
                        .frame(width: 22, height: 22)
                        .background(.white.opacity(0.08))
                        .clipShape(Circle())
                }
                .buttonStyle(.plain)
            }
            .frame(maxWidth: .infinity, alignment: .center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func barHeight(index: Int) -> CGFloat {
        let level = CGFloat(recorder.audioLevel * barOffsets[index])
        let minH: CGFloat = 3
        let maxH: CGFloat = 14
        return minH + level * (maxH - minH)
    }
}
