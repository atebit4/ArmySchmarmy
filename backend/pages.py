from nicegui import ui

# web version of desktop/mainscreen.ui: chat on the left, army workspace on the right,
# round Build Army button sitting on the divider about one third down.
BUILD_BUTTON_CSS = """
.nicegui-content { padding: 0; gap: 0; }
.app-layout, .panel-content, .message-input {
    background: #303436;
}
.app-layout {
    min-height: 100vh; align-items: stretch; color: #ece8df;
}
.app-panel { gap: 6px; padding: 9px; align-items: stretch; }
.app-panel.locked .q-btn,
.app-panel.locked .q-field { filter: grayscale(1); opacity: 0.4; }
.app-overlay { 
    position: absolute;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.9);
    z-index: 5;
    }
.panel-content {
    width: 100%; flex: 1 1 auto; min-height: 300px;
    border-color: #777b79;
}
.app-panel .q-field__native, .app-panel .q-field__input { color: #ece8df; }
.app-panel .q-field__native::placeholder { color: #bcb9af; opacity: 1; }
.app-panel .q-field__control:before { border-color: #8a8f8f; }
.chat-placeholder { color: #888; padding: 6px; }
.app-status { padding: 2px 9px; font-size: 12px; }
.build-button {
    position: relative; 
    z-index: 10;
    width: 120px; height: 120px; border-radius: 60px !important;
    border: 3px solid #d5b879;
    color: white; font-size: 16px; font-weight: bold; white-space: pre-line;
}
@media (min-width: 768px) {
    .build-button { position: absolute; left: 50%; top: 33%; transform: translate(-50%, -50%); z-index: 10; }
}
"""


def disable_with_opacity(button):
    """Disable a button without fading its appearance."""
    button.disable()
    button.style("opacity: 1 !important")


def set_button_red(button):
    """Override NiceGUI's default button color."""
    button.style('background-color: #420D09 !important; color: white !important')


@ui.page("/")
def index():
    ui.add_css(BUILD_BUTTON_CSS)

    def status(message):
        ui.notify(message, position="bottom", timeout=5000)

    def send_message():
        message = message_input.value.strip()
        if message:
            placeholder.visible = False
            with chat_history:
                ui.chat_message(message, name="You", sent=True)
            message_input.value = ""
            status("AI chat is not connected yet.")

    def start_app():
        overlay.visible = False

        for panel in (chat_panel, army_panel):
            panel.classes(remove="locked")
        for control in (message_input, send_button, add_unit_button):
            control.enable()

        disable_with_opacity(build_button)
        status("Ready to build your army.")

    with ui.element("div").classes("relative w-full flex flex-col md:flex-row app-layout"):
        with ui.column().classes("flex-1 min-w-0 app-panel locked") as chat_panel:
            ui.label("Army assistant")
            with ui.scroll_area().classes("panel-content border"):
                chat_history = ui.column().classes("w-full")
                placeholder = ui.label("Chat messages will appear here.").classes("chat-placeholder")
            with ui.row().classes("w-full no-wrap"):
                message_input = ui.input(placeholder="Describe your army...").classes("flex-1 message-input")
                message_input.disable()
                message_input.on("keydown.enter", send_message)
                send_button = ui.button("Send", on_click=send_message)
                set_button_red(send_button)
                send_button.disable()

        build_button = ui.button("Build\nArmy", on_click=start_app) \
            .classes("build-button self-center").props("unelevated")
        set_button_red(build_button)

        with ui.column().classes("flex-1 min-w-0 app-panel locked") as army_panel:
            ui.label("Army workspace")
            ui.element("div").classes("panel-content border")
            ui.label("Model placement will go here.")
            add_unit_button = ui.button("Add unit", on_click=lambda: status("Manual unit selection will be added here."))
            set_button_red(add_unit_button)
            add_unit_button.disable()
            ui.label("Points: 0    Cost: $0.00").style("white-space: pre")
        overlay = ui.element("div").classes("app-overlay")
