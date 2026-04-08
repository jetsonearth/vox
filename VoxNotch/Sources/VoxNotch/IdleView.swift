// IdleView.swift - Hover expands with content beside the notch

import SwiftUI

struct IdleView: View {
    let isHovering: Bool
    @EnvironmentObject var vm: VoxViewModel
    @State private var textOffset: CGFloat = 8
    @State private var textOpacity: Double = 0
    @State private var buttonHover = false

    var body: some View {
        if isHovering {
            HStack(spacing: 0) {
                // LEFT of notch: record button
                HStack(spacing: 8) {
                    Image(systemName: "mic.fill")
                        .font(.system(size: buttonHover ? 12 : 11))
                        .foregroundStyle(buttonHover ? .red : .red.opacity(0.7))

                    Text("Record")
                        .font(.system(size: 12, weight: .semibold, design: .rounded))
                        .foregroundStyle(buttonHover ? .white : .white.opacity(0.5))
                        .offset(x: textOffset)
                        .opacity(textOpacity)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(.white.opacity(buttonHover ? 0.08 : 0))
                )
                .onHover { hover in
                    withAnimation(.easeOut(duration: 0.15)) {
                        buttonHover = hover
                    }
                }
                .frame(maxWidth: .infinity, alignment: .center)

                // CENTER: black gap matching physical notch
                Rectangle()
                    .fill(.black)
                    .frame(width: vm.closedNotchSize.width - 10)

                // RIGHT of notch: shortcut hint
                Text("\u{2303}\u{2325}R")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.white.opacity(0.25))
                    .frame(maxWidth: .infinity, alignment: .center)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .onAppear {
                textOffset = 8
                textOpacity = 0
                withAnimation(.spring(response: 0.5, dampingFraction: 0.7).delay(0.05)) {
                    textOffset = 0
                    textOpacity = 1
                }
            }
            .onDisappear {
                textOffset = 8
                textOpacity = 0
                buttonHover = false
            }
        } else {
            Color.clear
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}
