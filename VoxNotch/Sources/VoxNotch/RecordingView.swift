// RecordingView.swift - Content sits beside the physical notch, not behind it

import SwiftUI

struct RecordingView: View {
    @EnvironmentObject var vm: VoxViewModel
    @State private var pulse = false

    var body: some View {
        HStack(spacing: 0) {
            // LEFT of notch: red dot + timer
            HStack(spacing: 6) {
                ZStack {
                    Circle()
                        .fill(.red.opacity(0.25))
                        .frame(width: 14, height: 14)
                        .scaleEffect(pulse ? 1.4 : 0.7)

                    Circle()
                        .fill(.red)
                        .frame(width: 6, height: 6)
                }
                .animation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true), value: pulse)
                .onAppear { pulse = true }

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

            // RIGHT of notch: waveform + controls
            HStack(spacing: 8) {
                // Mini waveform
                HStack(spacing: 2) {
                    ForEach(0..<5, id: \.self) { i in
                        RoundedRectangle(cornerRadius: 1)
                            .fill(.red.opacity(0.5))
                            .frame(width: 2, height: barHeight(index: i))
                            .animation(
                                .easeInOut(duration: 0.4 + Double(i) * 0.1)
                                    .repeatForever(autoreverses: true)
                                    .delay(Double(i) * 0.08),
                                value: pulse
                            )
                    }
                }

                // Stop
                Button {
                    withAnimation(.spring(response: 0.3)) {
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

                // Abort
                Button {
                    withAnimation(.spring(response: 0.3)) {
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
        let offsets: [CGFloat] = [6, 10, 14, 8, 5]
        return pulse ? offsets[index] : 4
    }
}
