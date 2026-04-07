// NotchSizing.swift - Notch dimension calculations

import SwiftUI

enum NotchSizing {
    static let shadowPadding: CGFloat = 20
    static let spacing: CGFloat = 16

    // Corner radii
    static let closedCorners: (top: CGFloat, bottom: CGFloat) = (6, 14)
    static let openCorners: (top: CGFloat, bottom: CGFloat) = (19, 24)

    // Config panel (compact)
    static let openWidth: CGFloat = 380
    static let configHeight: CGFloat = 210

    // Flashcard panel (needs more room)
    static let flashcardHeight: CGFloat = 300

    // Recording thin rod - wider so controls are visible beside the notch
    static let recordingWidth: CGFloat = 380

    // Done toast
    static let doneWidth: CGFloat = 260
    static let doneHeight: CGFloat = 50

    // Window must be large enough for the biggest state
    // Recording extends notch width + 200, so window needs headroom
    static let windowWidth: CGFloat = 500
    static let windowHeight: CGFloat = flashcardHeight + shadowPadding + 20

    @MainActor
    static func closedSize(for screen: NSScreen? = nil) -> CGSize {
        let screen = screen ?? NSScreen.main ?? NSScreen.screens.first!
        var width: CGFloat = 185
        var height: CGFloat = 32

        if let leftPad = screen.auxiliaryTopLeftArea?.width,
           let rightPad = screen.auxiliaryTopRightArea?.width
        {
            width = screen.frame.width - leftPad - rightPad + 4
        }

        if screen.safeAreaInsets.top > 0 {
            height = screen.safeAreaInsets.top
        }

        return CGSize(width: width, height: height)
    }
}
