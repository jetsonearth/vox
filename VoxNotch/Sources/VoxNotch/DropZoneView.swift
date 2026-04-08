// DropZoneView.swift - Panel shown when dragging an audio file over the notch

import SwiftUI

struct DropZoneView: View {
    @EnvironmentObject var vm: VoxViewModel
    @State private var appeared = false
    @State private var pulse = false

    var body: some View {
        VStack(spacing: 0) {
            Color.clear
                .frame(height: vm.closedNotchSize.height)

            Spacer()

            VStack(spacing: 14) {
                // Icon with subtle glow
                ZStack {
                    Circle()
                        .fill(.blue.opacity(pulse ? 0.08 : 0.04))
                        .frame(width: 72, height: 72)
                        .scaleEffect(pulse ? 1.05 : 1.0)

                    Image(systemName: "waveform.badge.plus")
                        .font(.system(size: 30, weight: .light))
                        .foregroundStyle(.blue.opacity(0.8))
                }
                .animation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true), value: pulse)

                Text("Drop audio file")
                    .font(.system(size: 13, weight: .medium, design: .rounded))
                    .foregroundStyle(.white.opacity(0.5))

                // Format pills
                HStack(spacing: 6) {
                    ForEach(["m4a", "mp3", "wav", "flac"], id: \.self) { ext in
                        Text(ext)
                            .font(.system(size: 9, weight: .medium, design: .monospaced))
                            .foregroundStyle(.white.opacity(0.2))
                            .padding(.horizontal, 6)
                            .padding(.vertical, 3)
                            .background(.white.opacity(0.04))
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                    }
                }
            }

            Spacer()
        }
        .opacity(appeared ? 1 : 0)
        .scaleEffect(appeared ? 1 : 0.95)
        .onAppear {
            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                appeared = true
            }
            pulse = true
        }
    }
}
