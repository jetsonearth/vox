// TranscribingView.swift - Content sits beside the physical notch

import SwiftUI

struct TranscribingView: View {
    @EnvironmentObject var vm: VoxViewModel

    var body: some View {
        HStack(spacing: 0) {
            Text("Transcribing")
                .font(.system(size: 11, weight: .medium, design: .rounded))
                .foregroundStyle(.white.opacity(0.6))
                .frame(maxWidth: .infinity, alignment: .center)

            Rectangle()
                .fill(.black)
                .frame(width: vm.closedNotchSize.width - 10)

            SpinningArc(color: .blue)
                .frame(maxWidth: .infinity, alignment: .center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct AnalyzingView: View {
    @EnvironmentObject var vm: VoxViewModel

    var body: some View {
        HStack(spacing: 0) {
            Text("Analyzing")
                .font(.system(size: 11, weight: .medium, design: .rounded))
                .foregroundStyle(.white.opacity(0.6))
                .frame(maxWidth: .infinity, alignment: .center)

            Rectangle()
                .fill(.black)
                .frame(width: vm.closedNotchSize.width - 10)

            SpinningArc(color: .blue)
                .frame(maxWidth: .infinity, alignment: .center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct SpinningArc: View {
    let color: Color
    @State private var rotation: Double = 0

    var body: some View {
        Circle()
            .trim(from: 0, to: 0.3)
            .stroke(color.opacity(0.6), style: StrokeStyle(lineWidth: 2, lineCap: .round))
            .frame(width: 14, height: 14)
            .rotationEffect(.degrees(rotation))
            .onAppear {
                withAnimation(.linear(duration: 1.0).repeatForever(autoreverses: false)) {
                    rotation = 360
                }
            }
    }
}
