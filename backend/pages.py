from nicegui import ui

# web version of desktop/mainscreen.ui: chat on the left, army workspace on the right,
# round Build Army button sitting on the divider about one third down.
BUILD_BUTTON_CSS = """
.build-button {
    width: 120px; height: 120px; border-radius: 60px !important;
    border: 3px solid #d5b879; background-color: #59442a !important;
    color: white; font-size: 16px; font-weight: bold; white-space: pre-line;
}
.build-button:hover { background-color: #80613a !important; }
.build-button:active { background-color: #3e301f !important; }
@media (min-width: 768px) {
    .build-button { position: absolute; left: 50%; top: 33%; transform: translate(-50%, -50%); z-index: 10; }
}
"""


@ui.page("/")
def index():
    ui.add_css(BUILD_BUTTON_CSS)

    def status(message):
        ui.notify(message, position="bottom", timeout=5000)

    def send_message():
        message = message_input.value.strip()
        if message:
            with chat_history:
                ui.chat_message(message, name="You", sent=True)
            message_input.value = ""
            status("AI chat is not connected yet.")

    with ui.element("div").classes("relative w-full flex flex-col md:flex-row gap-4 p-4 min-h-[90vh]"):
        with ui.column().classes("flex-1 min-w-0"):
            ui.label("Army assistant").classes("text-lg font-bold")
            with ui.scroll_area().classes("flex-1 min-h-[300px] border rounded"):
                chat_history = ui.column().classes("w-full")
            with ui.row().classes("w-full no-wrap"):
                message_input = ui.input(placeholder="Describe your army...").classes("flex-1")
                message_input.on("keydown.enter", send_message)
                ui.button("Send", on_click=send_message)

        ui.button("Build\nArmy", on_click=lambda: status("Army building will be connected here.")) \
            .classes("build-button self-center").props("unelevated")

        with ui.column().classes("flex-1 min-w-0"):
            ui.label("Army workspace").classes("text-lg font-bold")
            ui.element("div").classes("flex-1 min-h-[300px] w-full border rounded")
            ui.label("Model placement will go here.")
            ui.button("Add unit", on_click=lambda: status("Manual unit selection will be added here."))
            ui.label("Points: 0    Cost: $0.00").style("white-space: pre")
