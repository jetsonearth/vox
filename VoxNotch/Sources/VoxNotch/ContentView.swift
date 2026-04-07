// ContentView.swift - Main notch view with smooth state transitions

import SwiftUI

@MainActor
struct ContentView: View {
    @EnvironmentObject var vm: VoxViewModel
    @State private var isHovering = false
    @State private var hoverTask: Task<Void, Never>?
    @State private var gestureProgress: CGFloat = 0

    // Bouncy spring - overshoots slightly then settles
    private let sizeSpring = Animation.spring(response: 0.4, dampingFraction: 0.7)

    // MARK: - Dynamic sizing

    private var topCornerRadius: CGFloat {
        vm.isExpanded ? NotchSizing.openCorners.top : NotchSizing.closedCorners.top
    }

    private var bottomCornerRadius: CGFloat {
        vm.isExpanded ? NotchSizing.openCorners.bottom : NotchSizing.closedCorners.bottom
    }

    private var notchWidth: CGFloat {
        switch vm.voxState {
        case .idle:
            return isHovering
                ? vm.closedNotchSize.width + 200
                : vm.closedNotchSize.width
        case .recording:
            // Wide enough to show content in the auxiliary areas beside the notch
            return vm.closedNotchSize.width + 200
        case .transcribing, .analyzing, .done:
            return vm.closedNotchSize.width + 200
        case .configuring, .identifying:
            return NotchSizing.openWidth
        }
    }

    private var notchHeight: CGFloat {
        switch vm.voxState {
        case .idle, .recording, .transcribing, .analyzing, .done:
            return vm.closedNotchSize.height
        case .configuring:
            return NotchSizing.configHeight
        case .identifying:
            return NotchSizing.flashcardHeight
        }
    }

    private var showShadow: Bool {
        vm.voxState != .idle || isHovering
    }

    // MARK: - Body

    var body: some View {
        ZStack(alignment: .top) {
            VStack(spacing: 0) {
                notchBody
                    .frame(width: notchWidth, height: notchHeight)
                    .padding(.horizontal, vm.isExpanded ? 12 : 0)
                    .padding(.bottom, vm.isExpanded ? 12 : 0)
                    .background(.black)
                    .clipShape(
                        NotchShape(
                            topCornerRadius: topCornerRadius,
                            bottomCornerRadius: bottomCornerRadius
                        )
                    )
                    // Black line at top to blend with the physical notch
                    .overlay(alignment: .top) {
                        Rectangle()
                            .fill(.black)
                            .frame(height: 1)
                            .padding(.horizontal, topCornerRadius)
                    }
                    .shadow(
                        color: showShadow ? .black.opacity(0.7) : .clear,
                        radius: vm.isExpanded ? 8 : 5
                    )
                    .contentShape(Rectangle())
                    .onHover { hovering in
                        handleHover(hovering)
                    }
                    .onTapGesture {
                        handleTap()
                    }
            }
        }
        .frame(
            maxWidth: NotchSizing.windowWidth,
            maxHeight: NotchSizing.windowHeight,
            alignment: .top
        )
        .compositingGroup()
        .animation(sizeSpring, value: vm.voxState)
        .animation(sizeSpring, value: isHovering)
        .preferredColorScheme(.dark)
    }

    // MARK: - Content switching

    @ViewBuilder
    private var notchBody: some View {
        switch vm.voxState {
        case .idle:
            IdleView(isHovering: isHovering)
        case .recording:
            RecordingView()
        case .transcribing:
            TranscribingView()
        case .configuring:
            ConfigPanelView()
        case .identifying:
            SpeakerFlashcardView()
        case .analyzing:
            AnalyzingView()
        case .done:
            DoneView()
        }
    }

    // MARK: - Interaction

    private func handleHover(_ hovering: Bool) {
        hoverTask?.cancel()

        if hovering {
            withAnimation(.spring(response: 0.5, dampingFraction: 0.72, blendDuration: 0.1)) {
                isHovering = true
            }
        } else {
            hoverTask = Task {
                try? await Task.sleep(for: .milliseconds(150))
                guard !Task.isCancelled else { return }
                await MainActor.run {
                    withAnimation(.spring(response: 0.45, dampingFraction: 0.85, blendDuration: 0)) {
                        isHovering = false
                    }
                    if vm.voxState == .done {
                        vm.close()
                        vm.resetSession()
                    }
                }
            }
        }
    }

    private func handleTap() {
        switch vm.voxState {
        case .idle:
            withAnimation(sizeSpring) {
                vm.startRecording()
            }
        case .done:
            if !vm.doneNotePath.isEmpty {
                NSWorkspace.shared.open(URL(fileURLWithPath: vm.doneNotePath))
            }
            vm.close()
            vm.resetSession()
        default:
            break
        }
    }
}
