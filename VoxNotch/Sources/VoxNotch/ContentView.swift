// ContentView.swift - Main notch view with smooth state transitions

import SwiftUI
import UniformTypeIdentifiers

@MainActor
struct ContentView: View {
    @EnvironmentObject var vm: VoxViewModel
    @State private var isHovering = false
    @State private var hoverTask: Task<Void, Never>?
    @State private var gestureProgress: CGFloat = 0
    @State private var isDragTargeted = false

    private var isDropActive: Bool { isDragTargeted || vm.debugDropZone }

    // Bouncy spring - overshoots slightly then settles
    private let sizeSpring = Animation.spring(response: 0.4, dampingFraction: 0.7)

    // MARK: - Dynamic sizing

    private var topCornerRadius: CGFloat {
        isPanel ? NotchSizing.openCorners.top : NotchSizing.closedCorners.top
    }

    private var bottomCornerRadius: CGFloat {
        isPanel ? NotchSizing.openCorners.bottom : NotchSizing.closedCorners.bottom
    }

    private var thinRodExtra: CGFloat { NotchSizing.thinRodExtra }

    private var notchWidth: CGFloat {
        switch vm.voxState {
        case .idle where isDropActive:
            return NotchSizing.panelWidth
        case .idle:
            return isHovering
                ? vm.closedNotchSize.width + thinRodExtra
                : vm.closedNotchSize.width
        case .recording, .transcribing, .analyzing, .done:
            return vm.closedNotchSize.width + thinRodExtra
        case .configuring, .identifying:
            return NotchSizing.panelWidth
        }
    }

    private var notchHeight: CGFloat {
        switch vm.voxState {
        case .idle where isDropActive:
            return NotchSizing.panelHeight
        case .idle, .recording, .transcribing, .analyzing, .done:
            return vm.closedNotchSize.height
        case .configuring, .identifying:
            return NotchSizing.panelHeight
        }
    }

    private var isPanel: Bool {
        vm.isExpanded || isDropActive
    }

    private var showShadow: Bool {
        vm.voxState != .idle || isHovering || isDropActive
    }

    // MARK: - Body

    var body: some View {
        ZStack(alignment: .top) {
            VStack(spacing: 0) {
                notchBody
                    .frame(width: notchWidth, height: notchHeight)
                    .padding(.horizontal, isPanel ? 12 : 0)
                    .padding(.bottom, isPanel ? 12 : 0)
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
                    .onDrop(of: [.fileURL], isTargeted: $isDragTargeted) { providers in
                        handleDrop(providers)
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
        .animation(sizeSpring, value: isDropActive)
        .preferredColorScheme(.dark)
    }

    // MARK: - Content switching

    @ViewBuilder
    private var notchBody: some View {
        switch vm.voxState {
        case .idle where isDropActive:
            DropZoneView()
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

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        guard vm.voxState == .idle else { return false }

        for provider in providers {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                guard let data = item as? Data,
                      let url = URL(dataRepresentation: data, relativeTo: nil),
                      Self.audioExtensions.contains(url.pathExtension.lowercased())
                else { return }

                Task { @MainActor in
                    vm.loadExternalAudio(path: url.path)
                }
            }
        }
        return true
    }

    private static let audioExtensions: Set<String> = [
        "m4a", "mp3", "wav", "aac", "ogg", "flac", "mp4", "webm"
    ]
}
