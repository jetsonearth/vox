// ConfigPanelView.swift - Post-recording configuration panel

import SwiftUI

private let commonLanguages: [(code: String, flag: String)] = [
    ("en", "EN"),
    ("zh", "ZH"),
    ("ja", "JA"),
    ("ko", "KO"),
    ("es", "ES"),
    ("fr", "FR"),
]

struct ConfigPanelView: View {
    @EnvironmentObject var vm: VoxViewModel
    @FocusState private var focusedField: Field?
    @State private var appeared = false
    @State private var selectedLangs: Set<String> = []

    enum Field: Hashable {
        case sessionName, participants, context
    }

    var body: some View {
        VStack(spacing: 0) {
            // Notch header area
            HStack(spacing: 8) {
                Circle()
                    .fill(.green)
                    .frame(width: 7, height: 7)

                Text("\(vm.formattedElapsed)")
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundStyle(.white.opacity(0.5))

                Spacer()
            }
            .padding(.horizontal, 20)
            .frame(height: vm.closedNotchSize.height)

            Rectangle()
                .fill(.white.opacity(0.06))
                .frame(height: 1)
                .padding(.horizontal, 16)

            // Form
            VStack(spacing: 10) {
                // Session name - big and prominent
                TextField("Session name", text: $vm.sessionName)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(.white)
                    .textFieldStyle(.plain)
                    .focused($focusedField, equals: .sessionName)
                    .padding(.horizontal, 4)
                    .padding(.top, 2)

                // Two fields side by side
                HStack(spacing: 8) {
                    // Participants
                    HStack(spacing: 6) {
                        Image(systemName: "person.2")
                            .font(.system(size: 10))
                            .foregroundStyle(.white.opacity(0.3))
                        TextField("Who else?", text: $vm.participantNames)
                            .font(.system(size: 12))
                            .foregroundStyle(.white)
                            .textFieldStyle(.plain)
                            .focused($focusedField, equals: .participants)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(.white.opacity(0.05))
                    .clipShape(RoundedRectangle(cornerRadius: 8))

                    // Context
                    HStack(spacing: 6) {
                        Image(systemName: "text.quote")
                            .font(.system(size: 10))
                            .foregroundStyle(.white.opacity(0.3))
                        TextField("Context", text: $vm.context)
                            .font(.system(size: 12))
                            .foregroundStyle(.white)
                            .textFieldStyle(.plain)
                            .focused($focusedField, equals: .context)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(.white.opacity(0.05))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }

                // Language row
                LanguagePickerRow(selectedLangs: $selectedLangs)
            }
            .padding(.horizontal, 16)
            .padding(.top, 10)

            // Error
            if let error = vm.errorMessage {
                HStack(spacing: 4) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 9))
                    Text(error)
                        .font(.system(size: 10))
                }
                .foregroundStyle(.orange.opacity(0.8))
                .padding(.horizontal, 20)
                .padding(.top, 6)
                .transition(.move(edge: .top).combined(with: .opacity))
            }

            Spacer()

            // Bottom actions
            HStack(spacing: 10) {
                Button {
                    withAnimation(.spring(response: 0.35)) {
                        vm.resetSession()
                        vm.close()
                    }
                } label: {
                    Text("Cancel")
                        .font(.system(size: 12, weight: .medium, design: .rounded))
                        .foregroundStyle(.white.opacity(0.4))
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(.white.opacity(0.06))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                .buttonStyle(.plain)

                Spacer()

                Button {
                    withAnimation(.spring(response: 0.3)) {
                        vm.languageHints = selectedLangs.sorted().joined(separator: ", ")
                        vm.startTranscription()
                    }
                } label: {
                    HStack(spacing: 5) {
                        Text("Process")
                            .font(.system(size: 12, weight: .semibold, design: .rounded))
                        Image(systemName: "arrow.right")
                            .font(.system(size: 10, weight: .semibold))
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 8)
                    .background(
                        LinearGradient(
                            colors: [.blue, .blue.opacity(0.8)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 14)
        }
        .opacity(appeared ? 1 : 0)
        .offset(y: appeared ? 0 : 8)
        .onAppear {
            selectedLangs = Set(
                vm.languageHints
                    .split(separator: ",")
                    .map { $0.trimmingCharacters(in: .whitespaces).lowercased() }
            )
            withAnimation(.easeOut(duration: 0.35).delay(0.1)) {
                appeared = true
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                focusedField = .sessionName
            }
        }
    }
}

// MARK: - Language picker

struct LanguagePickerRow: View {
    @Binding var selectedLangs: Set<String>
    @State private var isAdding = false
    @State private var newLangText = ""
    @FocusState private var addFieldFocused: Bool

    // All custom langs the user added (beyond the common 6)
    private var customLangs: [String] {
        selectedLangs
            .filter { code in !commonLanguages.contains(where: { $0.code == code }) }
            .sorted()
    }

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "globe")
                .font(.system(size: 10))
                .foregroundStyle(.white.opacity(0.3))

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 5) {
                    // Common languages
                    ForEach(commonLanguages, id: \.code) { lang in
                        LanguageChip(
                            label: lang.flag,
                            selected: selectedLangs.contains(lang.code)
                        ) {
                            toggle(lang.code)
                        }
                    }

                    // Custom added languages
                    ForEach(customLangs, id: \.self) { code in
                        LanguageChip(
                            label: code.uppercased(),
                            selected: true
                        ) {
                            _ = withAnimation(.spring(response: 0.2, dampingFraction: 0.7)) {
                                selectedLangs.remove(code)
                            }
                        }
                    }

                    // Add button / inline field
                    if isAdding {
                        TextField("xx", text: $newLangText)
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .foregroundStyle(.white)
                            .textFieldStyle(.plain)
                            .frame(width: 32, height: 24)
                            .multilineTextAlignment(.center)
                            .background(
                                RoundedRectangle(cornerRadius: 6)
                                    .fill(.white.opacity(0.08))
                            )
                            .focused($addFieldFocused)
                            .onSubmit {
                                addCustomLang()
                            }
                            .onExitCommand {
                                isAdding = false
                                newLangText = ""
                            }
                    } else {
                        Button {
                            withAnimation(.spring(response: 0.2, dampingFraction: 0.7)) {
                                isAdding = true
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                                addFieldFocused = true
                            }
                        } label: {
                            Image(systemName: "plus")
                                .font(.system(size: 9, weight: .bold))
                                .foregroundStyle(.white.opacity(0.35))
                                .frame(width: 24, height: 24)
                                .background(
                                    RoundedRectangle(cornerRadius: 6)
                                        .stroke(.white.opacity(0.12), style: StrokeStyle(lineWidth: 1, dash: [3]))
                                )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }

    private func toggle(_ code: String) {
        withAnimation(.spring(response: 0.2, dampingFraction: 0.7)) {
            if selectedLangs.contains(code) {
                selectedLangs.remove(code)
            } else {
                selectedLangs.insert(code)
            }
        }
    }

    private func addCustomLang() {
        let code = newLangText.trimmingCharacters(in: .whitespaces).lowercased()
        if code.count >= 2 {
            withAnimation(.spring(response: 0.2, dampingFraction: 0.7)) {
                selectedLangs.insert(code)
            }
        }
        newLangText = ""
        isAdding = false
    }
}

struct LanguageChip: View {
    let label: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundStyle(selected ? .white : .white.opacity(0.3))
                .frame(width: 32, height: 24)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(selected ? .blue.opacity(0.6) : .white.opacity(0.04))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(selected ? .blue.opacity(0.3) : .clear, lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
        .scaleEffect(selected ? 1.0 : 0.95)
    }
}
