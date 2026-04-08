// NotchSizing.swift - Notch dimension calculations

import SwiftUI

enum NotchSizing {
    static let shadowPadding: CGFloat = 20
    static let spacing: CGFloat = 16

    // Corner radii
    static let closedCorners: (top: CGFloat, bottom: CGFloat) = (6, 14)
    static let openCorners: (top: CGFloat, bottom: CGFloat) = (19, 24)

    // Standard dropdown panel - landscape rectangle (横向长方形)
    static let panelWidth: CGFloat = 460
    static let panelHeight: CGFloat = 220

    // Thin rod is notch + 240 (set dynamically in ContentView)

    // Thin rod extra width (added to notch width)
    static let thinRodExtra: CGFloat = 240

    // Window must be large enough for the biggest state
    static let windowWidth: CGFloat = 520
    static let windowHeight: CGFloat = panelHeight + shadowPadding + 20

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
