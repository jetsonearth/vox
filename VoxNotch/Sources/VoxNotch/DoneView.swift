// DoneView.swift - Success toast, content beside the physical notch

import SwiftUI

struct DoneView: View {
    @EnvironmentObject var vm: VoxViewModel
    @State private var checkScale: CGFloat = 0
    @State private var textOpacity: Double = 0

    var body: some View {
        HStack(spacing: 0) {
            // LEFT of notch: checkmark + Done
            HStack(spacing: 6) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 13))
                    .foregroundStyle(.green)
                    .scaleEffect(checkScale)

                Text("Done")
                    .font(.system(size: 11, weight: .medium, design: .rounded))
                    .foregroundStyle(.white.opacity(0.7))
                    .opacity(textOpacity)
            }
            .frame(maxWidth: .infinity, alignment: .center)

            // CENTER: black gap
            Rectangle()
                .fill(.black)
                .frame(width: vm.closedNotchSize.width - 10)

            // RIGHT: empty
            Color.clear
                .frame(maxWidth: .infinity)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear {
            withAnimation(.spring(response: 0.35, dampingFraction: 0.6)) {
                checkScale = 1.0
            }
            withAnimation(.easeOut(duration: 0.3).delay(0.15)) {
                textOpacity = 1.0
            }
        }
    }
}
