import threading
import time

from PySide6 import QtCore, QtGui, QtWidgets

from .config import APP_NAME
from .models import (
    build_categories_map,
    format_created,
    format_pricing,
    infer_categories,
    load_model_catalog,
    merge_models,
    ordered_categories,
)
from .openai_client import send_chat
from .prompts import load_prompt_library, load_wrapper_prompt
from .storage import (
    load_config,
    load_conversations,
    new_conversation,
    resolve_api_key,
    save_config,
    save_conversations,
    store_api_key,
)


class MessageWidget(QtWidgets.QWidget):
    def __init__(self, role, text):
        super().__init__()
        self.role = role

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        bubble = QtWidgets.QFrame()
        bubble.setObjectName("bubble_user" if role == "user" else "bubble_assistant")
        bubble.setMaximumWidth(700)
        bubble_layout = QtWidgets.QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 10)

        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        bubble_layout.addWidget(label)

        if role == "user":
            layout.addStretch()
            layout.addWidget(bubble)
        else:
            layout.addWidget(bubble)
            layout.addStretch()


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent, api_key_value):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.api_key_value = api_key_value or ""

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        key_label = QtWidgets.QLabel("API Key")
        key_label.setObjectName("section")
        layout.addWidget(key_label)

        self.api_key_input = QtWidgets.QLineEdit()
        self.api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.api_key_input.setText(self.api_key_value)
        layout.addWidget(self.api_key_input)

        self.show_key_checkbox = QtWidgets.QCheckBox("Show")
        self.show_key_checkbox.stateChanged.connect(self._toggle_show)
        layout.addWidget(self.show_key_checkbox)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch()
        save_btn = QtWidgets.QPushButton("Save Key")
        save_btn.clicked.connect(self._save)
        button_row.addWidget(save_btn)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        self.status = QtWidgets.QLabel("")
        layout.addWidget(self.status)

    def _toggle_show(self):
        mode = (
            QtWidgets.QLineEdit.Normal
            if self.show_key_checkbox.isChecked()
            else QtWidgets.QLineEdit.Password
        )
        self.api_key_input.setEchoMode(mode)

    def _save(self):
        key = self.api_key_input.text().strip()
        if not key:
            self.status.setText("Enter a key first.")
            return
        location = store_api_key(load_config(), key)
        self.api_key_value = key
        self.status.setText(
            "Saved to system keyring" if location == "keyring" else "Saved to config"
        )
        self.accept()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 780)
        self.setMinimumSize(1100, 720)

        self.config = load_config()
        self.conversations, self.active_conversation_id = load_conversations(self.config)
        self.prompt_library = load_prompt_library()
        self.wrapper_prompt = load_wrapper_prompt()
        self.model_catalog = load_model_catalog()

        self.api_key_value = resolve_api_key(load_config(), prefer_env=False)

        self.api_models_cache = self.config.get("models_cache") or []
        self.models_cache_updated_at = self.config.get("models_cache_updated_at", "")
        self._rebuild_models()

        self.prompt_map = {
            prompt["id"]: prompt for prompt in self.prompt_library["prompts"]
        }
        self.prompt_choices = [
            "Custom (current text)"
        ] + [
            f"{prompt['name']} ({prompt['id']})" for prompt in self.prompt_library["prompts"]
        ]
        self.prompt_choice_to_id = {
            f"{prompt['name']} ({prompt['id']})": prompt["id"]
            for prompt in self.prompt_library["prompts"]
        }

        self._build_ui()
        self._ensure_active_conversation()
        self._refresh_conversation_list()
        self._load_active_conversation()
        self._refresh_model_controls()
        self._update_prompt_description()

    def _open_settings(self):
        dialog = SettingsDialog(self, self.api_key_value)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            new_key = dialog.api_key_value
            if new_key:
                self.api_key_value = new_key
        # pricing reload button exists in main sidebar; settings is key-only for now

    def _current_api_key(self):
        return self.api_key_value or ""

    def _build_ui(self):
        self.setStyleSheet(
            """
            QMainWindow { background: #f7f8fb; }
            QWidget { color: #1b1d1f; font-size: 13px; }
            QFrame#sidebar { background: #ffffff; border-right: 1px solid #d7dbe0; }
            QLabel#title { font-size: 18px; font-weight: 600; }
            QLineEdit, QPlainTextEdit, QComboBox {
                background: #ffffff; color: #1b1d1f;
                border: 1px solid #d7dbe0; border-radius: 6px; padding: 6px;
            }
            QComboBox QAbstractItemView {
                background: #ffffff; color: #1b1d1f;
                selection-background-color: #d8e7ff; selection-color: #1b1d1f;
                border: 1px solid #cfd5dd;
            }
            QListWidget {
                background: #ffffff; border: 1px solid #d7dbe0; border-radius: 8px;
            }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background: #d8e7ff; color: #1b1d1f; }
            QPlainTextEdit { min-height: 80px; }
            QPushButton {
                background: #1f6feb; color: #ffffff; border: none; border-radius: 6px;
                padding: 8px 12px; font-weight: 600;
            }
            QPushButton:disabled { background: #95b6f2; }
            QPushButton#secondary { background: #e9edf5; color: #1b1d1f; }
            QPushButton#danger { background: #f4d7d7; color: #4c1d1d; }
            QScrollArea#chat_area { background: #ffffff; border-radius: 10px; }
            QWidget#chat_container { background: #ffffff; }
            QFrame#bubble_user { background: #e1f3ff; border-radius: 12px; }
            QFrame#bubble_assistant { background: #f4f5f7; border-radius: 12px; }
            QLabel#section { font-size: 12px; font-weight: 600; color: #4a5568; }
            """
        )

        central = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central)

        sidebar = QtWidgets.QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(340)
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(12)

        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(APP_NAME)
        title.setObjectName("title")
        title_row.addWidget(title)
        title_row.addStretch()
        self.settings_button = QtWidgets.QPushButton("Settings")
        self.settings_button.setObjectName("secondary")
        self.settings_button.clicked.connect(self._open_settings)
        title_row.addWidget(self.settings_button)
        self.new_chat_button = QtWidgets.QPushButton("New Chat")
        self.new_chat_button.setObjectName("secondary")
        self.new_chat_button.clicked.connect(self._new_chat)
        title_row.addWidget(self.new_chat_button)
        sidebar_layout.addLayout(title_row)

        convo_section = QtWidgets.QLabel("Conversations")
        convo_section.setObjectName("section")
        sidebar_layout.addWidget(convo_section)

        self.conversation_list = QtWidgets.QListWidget()
        self.conversation_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self.conversation_list.itemSelectionChanged.connect(
            self._on_conversation_selected
        )
        sidebar_layout.addWidget(self.conversation_list, stretch=2)

        divider = QtWidgets.QFrame()
        divider.setFrameShape(QtWidgets.QFrame.HLine)
        divider.setFrameShadow(QtWidgets.QFrame.Sunken)
        sidebar_layout.addWidget(divider)

        settings_scroll = QtWidgets.QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        settings_container = QtWidgets.QWidget()
        settings_layout = QtWidgets.QVBoxLayout(settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        model_section = QtWidgets.QLabel("Model")
        model_section.setObjectName("section")
        settings_layout.addWidget(model_section)

        self.refresh_models_button = QtWidgets.QPushButton("Refresh Models")
        self.refresh_models_button.clicked.connect(self._refresh_models)
        settings_layout.addWidget(self.refresh_models_button)

        self.update_pricing_button = QtWidgets.QPushButton("Reload Pricing")
        self.update_pricing_button.setObjectName("secondary")
        self.update_pricing_button.clicked.connect(self._update_pricing)
        settings_layout.addWidget(self.update_pricing_button)

        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.currentIndexChanged.connect(self._on_category_change)
        settings_layout.addWidget(self._labeled("Category", self.category_combo))

        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.currentIndexChanged.connect(self._on_model_change)
        settings_layout.addWidget(self._labeled("Model", self.model_combo))

        self.custom_model_input = QtWidgets.QLineEdit()
        self.custom_model_input.textChanged.connect(self._on_custom_model_change)
        settings_layout.addWidget(self._labeled("Custom model", self.custom_model_input))

        stats_section = QtWidgets.QLabel("Model Stats")
        stats_section.setObjectName("section")
        settings_layout.addWidget(stats_section)

        self.stats_labels = {}
        for key in ("Model", "Availability", "Categories", "Pricing", "Created"):
            label = QtWidgets.QLabel("")
            label.setWordWrap(True)
            self.stats_labels[key] = label
            settings_layout.addWidget(self._stat_row(key, label))

        prompt_section = QtWidgets.QLabel("System Prompt")
        prompt_section.setObjectName("section")
        settings_layout.addWidget(prompt_section)

        self.wrapper_toggle = QtWidgets.QCheckBox("Use wrapper prompt")
        self.wrapper_toggle.setChecked(self._get_initial_wrapper_state())
        self.wrapper_toggle.stateChanged.connect(self._on_wrapper_toggle)
        settings_layout.addWidget(self.wrapper_toggle)

        self.prompt_combo = QtWidgets.QComboBox()
        self.prompt_combo.addItems(self.prompt_choices)
        self.prompt_combo.setCurrentText(self._get_initial_prompt_choice())
        self.prompt_combo.currentIndexChanged.connect(self._on_prompt_change)
        settings_layout.addWidget(self._labeled("Preset", self.prompt_combo))

        self.prompt_description = QtWidgets.QLabel("")
        self.prompt_description.setWordWrap(True)
        settings_layout.addWidget(self.prompt_description)

        self.system_prompt_edit = QtWidgets.QPlainTextEdit()
        self.system_prompt_edit.setPlainText(self._get_initial_system_prompt())
        settings_layout.addWidget(self.system_prompt_edit)

        self.save_settings_button = QtWidgets.QPushButton("Save Settings")
        self.save_settings_button.setObjectName("secondary")
        self.save_settings_button.clicked.connect(self._save_config)
        settings_layout.addWidget(self.save_settings_button)

        settings_layout.addStretch()
        settings_scroll.setWidget(settings_container)
        sidebar_layout.addWidget(settings_scroll, stretch=3)

        self.progress_label = QtWidgets.QLabel("")
        self.progress_label.setWordWrap(True)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)

        self.status_label = QtWidgets.QLabel("Ready")
        status_container = QtWidgets.QVBoxLayout()
        status_container.setContentsMargins(0, 0, 0, 0)
        status_container.addWidget(self.progress_label)
        status_container.addWidget(self.progress_bar)
        status_container.addWidget(self.status_label)
        sidebar_layout.addLayout(status_container)

        layout.addWidget(sidebar)

        chat_column = QtWidgets.QWidget()
        chat_layout = QtWidgets.QVBoxLayout(chat_column)
        chat_layout.setContentsMargins(20, 20, 20, 20)
        chat_layout.setSpacing(12)

        self.chat_container = QtWidgets.QWidget()
        self.chat_container.setObjectName("chat_container")
        self.chat_container_layout = QtWidgets.QVBoxLayout(self.chat_container)
        self.chat_container_layout.setAlignment(QtCore.Qt.AlignTop)
        self.chat_container_layout.setSpacing(12)
        self.chat_spacer = QtWidgets.QSpacerItem(
            20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.chat_container_layout.addItem(self.chat_spacer)

        self.chat_scroll = QtWidgets.QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.chat_scroll.setWidget(self.chat_container)
        self.chat_scroll.setObjectName("chat_area")
        chat_layout.addWidget(self.chat_scroll, stretch=1)

        input_row = QtWidgets.QHBoxLayout()
        self.input_edit = QtWidgets.QPlainTextEdit()
        self.input_edit.setPlaceholderText("Message OpenAI API Communicator...")
        input_row.addWidget(self.input_edit, stretch=1)

        self.send_button = QtWidgets.QPushButton("Send")
        self.send_button.clicked.connect(self._on_send)
        input_row.addWidget(self.send_button)
        chat_layout.addLayout(input_row)

        layout.addWidget(chat_column, stretch=1)

        send_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self)
        send_shortcut.activated.connect(self._on_send)

    def _labeled(self, label, widget):
        wrapper = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QtWidgets.QLabel(label)
        title.setObjectName("section")
        layout.addWidget(title)
        layout.addWidget(widget)
        return wrapper

    def _stat_row(self, label, widget):
        row = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QtWidgets.QLabel(label)
        title.setObjectName("section")
        layout.addWidget(title)
        layout.addWidget(widget)
        return row

    def _set_status(self, text):
        self.status_label.setText(text)

    def _set_progress(self, text):
        self.progress_label.setText(text)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)

    def _clear_progress(self):
        self.progress_label.setText("")
        self.progress_bar.setVisible(False)

    def _ensure_active_conversation(self):
        if not self.conversations:
            default_model = self.config.get("model", "")
            if not default_model and self.models:
                default_model = self.models[0]["id"]
            conversation = new_conversation(model=default_model)
            self.conversations = [conversation]
            self.active_conversation_id = conversation["id"]
            save_conversations(self.conversations, self.active_conversation_id)

        if not self.active_conversation_id:
            self.active_conversation_id = self.conversations[0].get("id", "")
            save_conversations(self.conversations, self.active_conversation_id)
        else:
            if not any(
                convo.get("id") == self.active_conversation_id
                for convo in self.conversations
            ):
                self.active_conversation_id = self.conversations[0].get("id", "")
                save_conversations(self.conversations, self.active_conversation_id)

    def _get_active_conversation(self):
        for convo in self.conversations:
            if convo.get("id") == self.active_conversation_id:
                return convo
        return self.conversations[0]

    def _refresh_conversation_list(self):
        self.conversation_list.clear()

        def sort_key(convo):
            return convo.get("updated_at") or convo.get("created_at") or ""

        sorted_convos = sorted(self.conversations, key=sort_key, reverse=True)
        for convo in sorted_convos:
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, convo.get("id"))
            widget = self._build_conversation_item(convo)
            item.setSizeHint(widget.sizeHint())
            self.conversation_list.addItem(item)
            self.conversation_list.setItemWidget(item, widget)

        self._select_conversation_by_id(self.active_conversation_id)

    def _build_conversation_item(self, convo):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        title = QtWidgets.QLabel(convo.get("title") or "New Chat")
        title.setStyleSheet("font-weight: 600;")
        title.setWordWrap(True)
        layout.addWidget(title)

        model_text = self._conversation_model_label(convo)
        meta = QtWidgets.QLabel(model_text)
        meta.setStyleSheet("color: #6b7280; font-size: 11px;")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        return widget

    def _conversation_model_label(self, convo):
        models_used = list(convo.get("models_used") or [])
        primary = convo.get("model")
        if primary and primary not in models_used:
            models_used.insert(0, primary)

        if not models_used:
            return "Model: not set"
        if len(models_used) == 1:
            return f"Model: {models_used[0]}"
        label = ", ".join(models_used[:3])
        if len(models_used) > 3:
            label = f"{label}..."
        return f"Models: {label}"

    def _generate_title(self, text):
        title = text.splitlines()[0].strip()
        if len(title) > 60:
            return f"{title[:57]}..."
        return title or "New Chat"

    def _apply_conversation_model(self, conversation):
        model_id = conversation.get("model", "").strip()
        if not model_id:
            return
        current_category = self.category_combo.currentText()
        if not self._category_contains(current_category, model_id):
            target_category = self._find_category_for_model(model_id)
            if target_category:
                self.category_combo.blockSignals(True)
                self.category_combo.setCurrentText(target_category)
                self.category_combo.blockSignals(False)
                self._update_model_list()

        if self.model_combo.findText(model_id) >= 0:
            self.custom_model_input.setText("")
            self.model_combo.setCurrentText(model_id)
        else:
            self.custom_model_input.setText(model_id)

    def _category_contains(self, category, model_id):
        models = self.categories_map.get(category, [])
        return any(model.get("id") == model_id for model in models)

    def _find_category_for_model(self, model_id):
        for category, models in self.categories_map.items():
            if any(model.get("id") == model_id for model in models):
                return category
        return "All (Oldest->Newest)"

    def _select_conversation_by_id(self, convo_id):
        for index in range(self.conversation_list.count()):
            item = self.conversation_list.item(index)
            if item.data(QtCore.Qt.UserRole) == convo_id:
                self.conversation_list.setCurrentItem(item)
                return

    def _on_conversation_selected(self):
        item = self.conversation_list.currentItem()
        if not item:
            return
        convo_id = item.data(QtCore.Qt.UserRole)
        if convo_id and convo_id != self.active_conversation_id:
            self.active_conversation_id = convo_id
            save_conversations(self.conversations, self.active_conversation_id)
        self._load_active_conversation()

    def _load_active_conversation(self):
        conversation = self._get_active_conversation()
        while self.chat_container_layout.count():
            item = self.chat_container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.chat_container_layout.addItem(self.chat_spacer)
        for message in conversation.get("messages", []):
            role = message.get("role", "assistant")
            content = message.get("content", "")
            if content:
                self._append_message(role, content)
        self._apply_conversation_model(conversation)

    def _get_initial_api_key(self):
        return resolve_api_key(self.config, prefer_env=False)

    def _get_initial_prompt_choice(self):
        prompt_id = self.config.get("prompt_id")
        if prompt_id and prompt_id in self.prompt_map:
            for choice, choice_id in self.prompt_choice_to_id.items():
                if choice_id == prompt_id:
                    return choice
        return "Custom (current text)"

    def _get_initial_system_prompt(self):
        stored = self.config.get("system_prompt")
        if stored:
            return stored
        prompt_id = self._get_selected_prompt_id()
        prompt = self.prompt_map.get(prompt_id)
        if prompt:
            return prompt.get("content", "")
        return ""

    def _get_initial_wrapper_state(self):
        config_value = self.config.get("use_wrapper_prompt")
        if config_value is None:
            return bool(self.wrapper_prompt.get("enabled", True))
        return bool(config_value)

    def _get_selected_prompt_id(self):
        choice = self.prompt_combo.currentText()
        return self.prompt_choice_to_id.get(choice, "")

    def _get_wrapper_prompt(self):
        if not self.wrapper_toggle.isChecked():
            return ""
        return self.wrapper_prompt.get("content", "")

    def _rebuild_models(self):
        merged = merge_models(self.model_catalog, self.api_models_cache)
        self.models = merged
        self.models_by_id = {model["id"]: model for model in merged}
        self.categories_map = build_categories_map(merged)

    def _refresh_model_controls(self):
        categories = ordered_categories(self.categories_map)
        if not categories:
            categories = ["All (Oldest->Newest)"]
            self.categories_map = {"All (Oldest->Newest)": []}

        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItems(categories)
        if self.config.get("category") in categories:
            self.category_combo.setCurrentText(self.config.get("category"))
        else:
            self.category_combo.setCurrentIndex(0)
        self.category_combo.blockSignals(False)

        self._update_model_list()

    def _update_model_list(self):
        category = self.category_combo.currentText()
        models = self.categories_map.get(category, [])
        model_ids = [model["id"] for model in models]

        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(model_ids)
        conversation = self._get_active_conversation()
        configured_model = conversation.get("model") or self.config.get("model")
        if configured_model in model_ids:
            self.model_combo.setCurrentText(configured_model)
        elif model_ids:
            self.model_combo.setCurrentIndex(0)
        self.model_combo.blockSignals(False)

        if configured_model and configured_model not in model_ids:
            self.custom_model_input.setText(configured_model)

        custom = self.custom_model_input.text().strip()
        if custom:
            self._update_model_stats(custom)
            return

        if model_ids:
            self._update_model_stats(self.model_combo.currentText())
        else:
            self._update_model_stats("")

    def _update_model_stats(self, model_id):
        if not model_id:
            self.stats_labels["Model"].setText("None")
            self.stats_labels["Availability"].setText("Unknown")
            self.stats_labels["Categories"].setText("Unknown")
            self.stats_labels["Pricing"].setText("Unknown")
            self.stats_labels["Created"].setText("Unknown")
            return

        info = self.models_by_id.get(model_id)
        if info is None:
            info = {
                "id": model_id,
                "categories": infer_categories(model_id),
                "pricing": {},
                "created": None,
                "available": False,
                "source": "custom",
                "release_order": None,
            }

        categories = ", ".join(info.get("categories", [])) or "Other"
        if info.get("source") == "custom":
            availability = "Custom"
        else:
            availability = "Available" if info.get("available") else "Catalog-only"

        self.stats_labels["Model"].setText(info.get("id", ""))
        self.stats_labels["Availability"].setText(availability)
        self.stats_labels["Categories"].setText(categories)
        self.stats_labels["Pricing"].setText(format_pricing(info.get("pricing")))
        self.stats_labels["Created"].setText(
            format_created(info.get("created"), info.get("release_order"))
        )

    def _save_config(self):
        self.config["system_prompt"] = self.system_prompt_edit.toPlainText().strip()
        self.config["prompt_id"] = self._get_selected_prompt_id()
        self.config["use_wrapper_prompt"] = self.wrapper_toggle.isChecked()
        self.config["category"] = self.category_combo.currentText().strip()
        self.config["model"] = self._get_selected_model()
        self.config["models_cache"] = self.api_models_cache
        self.config["models_cache_updated_at"] = self.models_cache_updated_at
        save_config(self.config)
        self._set_status("Settings saved")

    def _get_selected_model(self):
        custom = self.custom_model_input.text().strip()
        if custom:
            return custom
        return self.model_combo.currentText().strip()

    def _on_category_change(self):
        self._update_model_list()

    def _on_model_change(self):
        self.custom_model_input.setText("")
        self._update_model_stats(self.model_combo.currentText().strip())
        self._update_active_conversation_model(self.model_combo.currentText().strip())

    def _on_custom_model_change(self):
        self._update_model_stats(self.custom_model_input.text().strip())
        self._update_active_conversation_model(self.custom_model_input.text().strip())

    def _on_prompt_change(self):
        prompt_id = self._get_selected_prompt_id()
        prompt = self.prompt_map.get(prompt_id)
        if prompt:
            self.system_prompt_edit.setPlainText(prompt.get("content", ""))
        self._update_prompt_description()

    def _update_prompt_description(self):
        prompt_id = self._get_selected_prompt_id()
        prompt = self.prompt_map.get(prompt_id)
        if prompt:
            self.prompt_description.setText(prompt.get("description", ""))
        else:
            self.prompt_description.setText("Custom text")

    def _update_active_conversation_model(self, model_id):
        conversation = self._get_active_conversation()
        if not conversation:
            return
        model_id = model_id.strip()
        if model_id:
            conversation["model"] = model_id
            models_used = conversation.setdefault("models_used", [])
            if model_id not in models_used:
                models_used.append(model_id)
        conversation["updated_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        save_conversations(self.conversations, self.active_conversation_id)
        self._refresh_conversation_list()

    def _on_wrapper_toggle(self):
        state = "enabled" if self.wrapper_toggle.isChecked() else "disabled"
        self._set_status(f"Wrapper prompt {state}")

    def _append_message(self, role, content):
        layout = self.chat_container_layout
        layout.removeItem(self.chat_spacer)
        layout.addWidget(MessageWidget(role, content))
        layout.addItem(self.chat_spacer)
        QtCore.QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self.chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _new_chat(self):
        model = self._get_selected_model()
        conversation = new_conversation(model=model)
        self.conversations.append(conversation)
        self.active_conversation_id = conversation["id"]
        save_conversations(self.conversations, self.active_conversation_id)
        while self.chat_container_layout.count():
            item = self.chat_container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.chat_container_layout.addItem(self.chat_spacer)
        self._refresh_conversation_list()
        self._set_status("New chat started")

    def _refresh_models(self):
        api_key = resolve_api_key(
            self.config, override=self._current_api_key(), prefer_env=True
        )
        if not api_key:
            self._show_error("Missing API Key", "Set your API key first.")
            return

        self._set_status("Loading models...")
        self.refresh_models_button.setEnabled(False)
        self.send_button.setEnabled(False)

        def worker():
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key)
                models = client.models.list()
                items = [
                    {"id": model.id, "created": getattr(model, "created", None)}
                    for model in models.data
                ]
                QtCore.QTimer.singleShot(0, lambda: self._on_models_loaded(items))
            except Exception as exc:
                QtCore.QTimer.singleShot(
                    0, lambda: self._on_models_error(str(exc))
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_models_loaded(self, models):
        self.api_models_cache = models
        self.models_cache_updated_at = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        self.config["models_cache"] = models
        self.config["models_cache_updated_at"] = self.models_cache_updated_at
        save_config(self.config)
        self.model_catalog = load_model_catalog()
        self._rebuild_models()
        self._refresh_model_controls()
        self.refresh_models_button.setEnabled(True)
        self.send_button.setEnabled(True)
        self._set_status("Models updated")

    def _on_models_error(self, message):
        self.refresh_models_button.setEnabled(True)
        self.send_button.setEnabled(True)
        self._set_status("Failed to load models")
        self._show_error("Model Load Error", message)

    def _update_pricing(self):
        self._set_status("Reloading pricing from catalog...")
        self._clear_progress()
        self.model_catalog = load_model_catalog()
        self._rebuild_models()
        self._refresh_model_controls()
        self.update_pricing_button.setEnabled(True)
        self.refresh_models_button.setEnabled(True)
        self._set_status("Pricing reloaded from catalog")

    def _on_pricing_updated(self, result):
        self._clear_progress()
        self.model_catalog = load_model_catalog()
        self._rebuild_models()
        self._refresh_model_controls()
        self.update_pricing_button.setEnabled(True)
        self.refresh_models_button.setEnabled(True)
        self._set_status(
            f"Pricing updated ({result['prices']} prices for {result['models']} models)"
        )

    def _on_pricing_error(self, message):
        self._clear_progress()
        self.update_pricing_button.setEnabled(True)
        self.refresh_models_button.setEnabled(True)
        self._set_status("Pricing update failed")
        self._show_error("Pricing Update Error", message)

    def _show_error(self, title, message):
        QtWidgets.QMessageBox.critical(self, title, message)

    def _on_send(self):
        message = self.input_edit.toPlainText().strip()
        if not message:
            return

        model = self._get_selected_model()
        if not model:
            self._show_error("Missing Model", "Select a model first.")
            return

        api_key = resolve_api_key(
            self.config, override=self._current_api_key(), prefer_env=True
        )
        if not api_key:
            self._show_error("Missing API Key", "Set your API key first.")
            return

        self.input_edit.setPlainText("")
        self._append_message("user", message)

        conversation = self._get_active_conversation()
        conversation.setdefault("messages", []).append(
            {"role": "user", "content": message}
        )
        conversation["updated_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        conversation["model"] = model
        models_used = conversation.setdefault("models_used", [])
        if model not in models_used:
            models_used.append(model)
        if conversation.get("title") in ("", "New Chat"):
            conversation["title"] = self._generate_title(message)
        save_conversations(self.conversations, self.active_conversation_id)
        self._refresh_conversation_list()
        self._set_status("Sending...")
        self.send_button.setEnabled(False)

        system_prompt = self.system_prompt_edit.toPlainText().strip()
        wrapper_prompt = self._get_wrapper_prompt()
        messages_snapshot = list(conversation.get("messages", []))

        def worker():
            try:
                reply = send_chat(
                    api_key, model, wrapper_prompt, system_prompt, messages_snapshot
                )
                QtCore.QTimer.singleShot(0, lambda: self._on_reply(reply))
            except Exception as exc:
                QtCore.QTimer.singleShot(0, lambda: self._on_error(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_reply(self, reply):
        if not reply:
            reply = "(No text response.)"
        self._append_message("assistant", reply)
        conversation = self._get_active_conversation()
        conversation.setdefault("messages", []).append(
            {"role": "assistant", "content": reply}
        )
        conversation["updated_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        save_conversations(self.conversations, self.active_conversation_id)
        self._refresh_conversation_list()
        self.send_button.setEnabled(True)
        self._set_status("Ready")

    def _on_error(self, message):
        self.send_button.setEnabled(True)
        self._append_message("assistant", f"Error: {message}")
        self._set_status("Error")


def run_gui():
    app = QtWidgets.QApplication([])
    app.setFont(QtGui.QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    app.exec()
