// VoxNotchApp.swift - Entry point for the Vox notch app

import KeyboardShortcuts
import SwiftUI

extension KeyboardShortcuts.Name {
    static let toggleRecording = Self("toggleRecording", default: .init(.r, modifiers: [.control, .option]))
}

@main
struct VoxNotchApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        MenuBarExtra {
            Button("Toggle Recording") {
                Task { @MainActor in
                    appDelegate.toggleRecording()
                }
            }
            .keyboardShortcut("R", modifiers: [.control, .option])
            Divider()
            Menu("Debug States") {
                Button("Idle") { Task { @MainActor in appDelegate.vm.voxState = .idle; appDelegate.vm.notchState = .closed } }
                Button("Recording") { Task { @MainActor in appDelegate.vm.voxState = .recording; appDelegate.vm.notchState = .open; appDelegate.vm.recordingElapsed = 42 } }
                Button("Transcribing") { Task { @MainActor in appDelegate.vm.voxState = .transcribing; appDelegate.vm.notchState = .open } }
                Button("Configuring") { Task { @MainActor in
                    appDelegate.vm.voxState = .configuring; appDelegate.vm.notchState = .open; appDelegate.vm.recordingElapsed = 185
                } }
                Button("Identifying (2 speakers)") { Task { @MainActor in
                    appDelegate.vm.speakerPreviews = [
                        SpeakerPreview(id: "Speaker 1", label: "Speaker 1", textSnippet: "[en] Hey, how's it going?", clipStartSec: 0, clipEndSec: 5),
                        SpeakerPreview(id: "Speaker 2", label: "Speaker 2", textSnippet: "[en] Good, thanks for asking.", clipStartSec: 10, clipEndSec: 15),
                    ]
                    appDelegate.vm.speakerMapping = [:]
                    appDelegate.vm.participantNames = "Alex"
                    appDelegate.vm.currentFlashcardIndex = 0
                    appDelegate.vm.voxState = .identifying; appDelegate.vm.notchState = .open
                } }
                Button("Identifying (3 speakers)") { Task { @MainActor in
                    appDelegate.vm.speakerPreviews = [
                        SpeakerPreview(id: "Speaker 1", label: "Speaker 1", textSnippet: "[en] Hey, how's it going?", clipStartSec: 0, clipEndSec: 5),
                        SpeakerPreview(id: "Speaker 2", label: "Speaker 2", textSnippet: "[en] Good, thanks.", clipStartSec: 10, clipEndSec: 15),
                        SpeakerPreview(id: "Speaker 3", label: "Speaker 3", textSnippet: "[zh] OK cool.", clipStartSec: 20, clipEndSec: 25),
                    ]
                    appDelegate.vm.speakerMapping = [:]
                    appDelegate.vm.participantNames = "Alex, Stash"
                    appDelegate.vm.currentFlashcardIndex = 0
                    appDelegate.vm.voxState = .identifying; appDelegate.vm.notchState = .open
                } }
                Button("Drop Zone") { Task { @MainActor in
                    appDelegate.vm.resetSession()
                    appDelegate.vm.debugDropZone = true
                    appDelegate.vm.notchState = .open
                } }
                Button("Analyzing") { Task { @MainActor in appDelegate.vm.voxState = .analyzing; appDelegate.vm.notchState = .open } }
                Button("Done") { Task { @MainActor in appDelegate.vm.voxState = .done; appDelegate.vm.notchState = .open; appDelegate.vm.sessionName = "Test Session" } }
            }
            Divider()
            Button("Quit") {
                VoxService.shared.stopServer()
                NSApplication.shared.terminate(nil)
            }
            .keyboardShortcut("Q", modifiers: .command)
        } label: {
            if let image = loadMenuBarIcon() {
                Image(nsImage: image)
            } else {
                Image(systemName: "mic.fill")
            }
        }
    }
}

private func loadMenuBarIcon() -> NSImage? {
    let bundle = Bundle.main
    guard let url = bundle.url(forResource: "menubar", withExtension: "png"),
          let image = NSImage(contentsOf: url)
    else { return nil }
    image.isTemplate = true  // adapts to light/dark menu bar
    image.size = NSSize(width: 18, height: 18)
    return image
}

@MainActor
class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NotchWindow?
    let vm = VoxViewModel()
    private let notchSpace = CGSSpace(level: 2_147_483_647)

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        createNotchWindow()
        setupKeyboardShortcut()

        // Fetch config from server in background
        Task {
            do {
                let config = try await VoxService.shared.fetchConfig()
                await MainActor.run {
                    vm.userName = config.userName
                    vm.languageHints = config.languageHints.joined(separator: ", ")
                }
            } catch {
                // Server not running yet - will start on first recording
            }
        }

        // Listen for screen changes
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(screenConfigDidChange),
            name: NSApplication.didChangeScreenParametersNotification,
            object: nil
        )
    }

    func applicationWillTerminate(_ notification: Notification) {
        VoxService.shared.stopServer()
    }

    // MARK: - Window

    @MainActor
    private func createNotchWindow() {
        guard let screen = NSScreen.main else { return }

        let windowSize = CGSize(
            width: NotchSizing.windowWidth,
            height: NotchSizing.windowHeight
        )

        let rect = NSRect(
            x: 0, y: 0,
            width: windowSize.width,
            height: windowSize.height
        )

        let styleMask: NSWindow.StyleMask = [.borderless, .nonactivatingPanel, .utilityWindow, .hudWindow]
        let window = NotchWindow(
            contentRect: rect,
            styleMask: styleMask,
            backing: .buffered,
            defer: false
        )

        window.contentView = NSHostingView(
            rootView: ContentView().environmentObject(vm)
        )

        window.orderFrontRegardless()
        notchSpace.windows.insert(window)
        positionWindow(window, on: screen)
        self.window = window
    }

    @MainActor
    private func positionWindow(_ window: NSWindow, on screen: NSScreen) {
        let screenFrame = screen.frame
        window.setFrameOrigin(
            NSPoint(
                x: screenFrame.origin.x + (screenFrame.width / 2) - window.frame.width / 2,
                y: screenFrame.origin.y + screenFrame.height - window.frame.height
            )
        )
    }

    @objc private func screenConfigDidChange() {
        guard let window = window, let screen = NSScreen.main else { return }
        Task { @MainActor in
            vm.closedNotchSize = NotchSizing.closedSize(for: screen)
            positionWindow(window, on: screen)
        }
    }

    // MARK: - Keyboard shortcut

    private func setupKeyboardShortcut() {
        KeyboardShortcuts.onKeyDown(for: .toggleRecording) { [weak self] in
            Task { @MainActor in
                self?.toggleRecording()
            }
        }
    }

    @MainActor
    func toggleRecording() {
        switch vm.voxState {
        case .idle:
            vm.startRecording()
        case .recording:
            vm.stopRecording()
        default:
            break
        }
    }
}
