from __future__ import annotations

from dataclasses import dataclass

from image_toolbox.core.paths import get_assets_dir


def _asset_url(relative_path: str) -> str:
    return (get_assets_dir() / relative_path).resolve().as_posix()


CHEVRON_DOWN = _asset_url("icons/chevron-down.svg")
CHEVRON_DOWN_HOVER = _asset_url("icons/chevron-down-hover.svg")
CHEVRON_DOWN_SMALL = _asset_url("icons/chevron-down-small.svg")
CHEVRON_DOWN_SMALL_HOVER = _asset_url("icons/chevron-down-small-hover.svg")
CHEVRON_UP = _asset_url("icons/chevron-up.svg")
CHEVRON_UP_HOVER = _asset_url("icons/chevron-up-hover.svg")


@dataclass(frozen=True)
class ThemeTokens:
    background: str = "#F5F7FB"
    surface: str = "#FFFFFF"
    surface_strong: str = "#FFFFFF"
    surface_soft: str = "#F8FAFD"
    border: str = "#FFFFFF"
    border_soft: str = "rgba(118, 134, 159, 58)"
    text: str = "#111827"
    text_muted: str = "#667085"
    accent: str = "#2F7DF6"
    accent_soft: str = "#E8F2FF"
    success: str = "#28A86B"
    warning: str = "#C98513"
    danger: str = "#D14343"
    radius_shell: int = 24
    radius_card: int = 20
    radius_button: int = 14
    radius_input: int = 12
    space_1: int = 8
    space_2: int = 16
    space_3: int = 24
    space_4: int = 32
    shadow_soft: str = "0 18 54 rgba(28, 37, 52, 0.14)"
    font_family: str = '"Segoe UI Variable", "Microsoft YaHei UI", "Segoe UI"'
    font_body: int = 13
    font_caption: int = 12
    font_title: int = 18
    font_hero: int = 32


TOKENS = ThemeTokens()


LIGHT_THEME = f"""
* {{
    font-family: {TOKENS.font_family};
    font-size: {TOKENS.font_body}px;
    letter-spacing: 0px;
}}

QMainWindow, QWidget#AppShell {{
    background: {TOKENS.background};
    color: {TOKENS.text};
}}

QWidget {{
    color: {TOKENS.text};
}}

QWidget#AppContent {{
    background: {TOKENS.background};
}}

QFrame#WindowMenuBar {{
    background: #F2F2F2;
    border: 0;
    border-bottom: 1px solid rgba(0, 0, 0, 18);
}}

QPushButton#WindowMenuIconButton,
QPushButton#WindowMenuAccentButton {{
    border: 0;
    border-radius: 14px;
    background: transparent;
    color: #80868D;
    font-size: 15px;
    font-weight: 650;
    padding: 0;
}}

QPushButton#WindowMenuIconButton:hover {{
    background: rgba(0, 0, 0, 22);
    color: #4D5660;
}}

QPushButton#WindowMenuIconButton:disabled {{
    background: transparent;
    color: rgba(128, 134, 141, 86);
}}

QPushButton#WindowMenuAccentButton {{
    background: #339CFF;
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 720;
}}

QPushButton#WindowMenuAccentButton:hover {{
    background: #1F8EF5;
}}

QPushButton#WindowMenuTextButton {{
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: #73787F;
    font-size: 14px;
    padding: 0 12px;
    text-align: center;
}}

QPushButton#WindowMenuTextButton:hover {{
    background: rgba(0, 0, 0, 20);
    color: #343A42;
}}

QPushButton#WindowMenuTextButton::menu-indicator {{
    image: none;
    width: 0;
}}

QPushButton#WindowControlButton,
QPushButton#WindowCloseButton {{
    border: 0;
    border-radius: 0;
    background: transparent;
    color: #111827;
    font-size: 15px;
    padding: 0;
}}

QPushButton#WindowControlButton:hover {{
    background: rgba(0, 0, 0, 22);
}}

QPushButton#WindowCloseButton:hover {{
    background: #E81123;
    color: #FFFFFF;
}}

QMenu {{
    background: rgba(255, 255, 255, 248);
    border: 1px solid rgba(118, 134, 159, 55);
    border-radius: 8px;
    padding: 6px;
    color: #343A42;
}}

QMenu::item {{
    min-width: 132px;
    padding: 7px 26px 7px 12px;
    border-radius: 6px;
    background: transparent;
}}

QMenu::item:selected {{
    background: #E8F2FF;
    color: #0F3575;
}}

QMenu::separator {{
    height: 1px;
    background: rgba(118, 134, 159, 46);
    margin: 5px 8px;
}}

QFrame#AppShellBody, QFrame#AppWorkspace {{
    background: transparent;
    border: 0;
}}

QFrame#GlassToolbar,
QFrame#GlassSidebar,
QFrame#GlassPanel,
QFrame#GlassStatusBar,
QFrame#RightPanel,
QFrame#BottomPanel,
QFrame#LiquidShell,
QFrame#LiquidHeroPanel,
QFrame#LiquidGlassCard {{
    background: {TOKENS.surface};
    border: 1px solid {TOKENS.border};
    border-radius: {TOKENS.radius_shell}px;
}}

QFrame#GlassSidebar {{
    border-radius: {TOKENS.radius_shell}px;
}}

QFrame#RightPanel {{
    border-radius: {TOKENS.radius_card}px;
}}

QFrame#BottomPanel, QFrame#GlassStatusBar {{
    border-radius: 18px;
}}

QFrame#GlassStatusBar {{
    background: rgba(255, 255, 255, 235);
}}

QFrame#TaskCompletionToast {{
    background: rgba(255, 255, 255, 245);
    border: 1px solid rgba(47, 125, 246, 58);
    border-radius: 18px;
}}

QLabel#TaskCompletionToastIcon {{
    background: #28A86B;
    border-radius: 17px;
    color: #FFFFFF;
    font-size: 18px;
    font-weight: 800;
}}

QLabel#TaskCompletionToastTitle {{
    color: #111827;
    font-size: 14px;
    font-weight: 760;
}}

QLabel#TaskCompletionToastMessage {{
    color: #667085;
    font-size: 12px;
    font-weight: 500;
}}

QFrame#SettingsSaveToast {{
    background: rgba(255, 255, 255, 246);
    border: 1px solid rgba(40, 168, 107, 72);
    border-radius: 16px;
}}

QLabel#SettingsSaveToastIcon {{
    background: #28A86B;
    border-radius: 12px;
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 800;
}}

QLabel#SettingsSaveToastTitle {{
    color: #111827;
    font-size: 13px;
    font-weight: 760;
}}

QLabel#SettingsSaveToastMessage {{
    color: #667085;
    font-size: 12px;
    font-weight: 500;
}}

QWidget#LiquidHome {{
    background: transparent;
    color: {TOKENS.text};
}}

QWidget#LiquidHome QLabel,
QWidget#LiquidHome QPushButton,
QFrame#LiquidShell QLabel,
QFrame#LiquidHeroPanel QLabel,
QFrame#LiquidGlassCard QLabel,
QFrame#LiquidGlassCard QPushButton {{
    background: transparent;
}}

QLabel#HeroTitle {{
    color: {TOKENS.text};
    font-size: 34px;
    font-weight: 760;
}}

QLabel#PanelTitle {{
    color: {TOKENS.text};
    font-size: 24px;
    font-weight: 760;
}}

QLabel#CardTitle,
QLabel#LiquidSectionTitle {{
    color: {TOKENS.text};
    font-size: {TOKENS.font_title}px;
    font-weight: 720;
}}

QLabel#MutedText,
QLabel#LiquidMutedText {{
    color: {TOKENS.text_muted};
    font-size: {TOKENS.font_caption}px;
}}

QLabel#BottomStatusText {{
    color: #000000;
    font-size: 13px;
    font-weight: 600;
}}

QLabel#IntroText {{
    color: #3F4B5F;
    font-size: 15px;
}}

QLabel#LiquidHeroTitle {{
    color: #102033;
    font-size: {TOKENS.font_hero}px;
    font-weight: 760;
}}

QLabel#LiquidCardTitle {{
    color: {TOKENS.text};
    font-size: 15px;
    font-weight: 700;
}}

QLabel#LiquidMetricValue {{
    color: {TOKENS.accent};
    font-size: 20px;
    font-weight: 760;
}}

QPushButton {{
    background: {TOKENS.accent};
    border: 1px solid rgba(47, 125, 246, 30);
    border-radius: {TOKENS.radius_button}px;
    color: white;
    font-weight: 700;
    min-height: 30px;
    padding: 8px 14px;
}}

QPushButton:hover {{
    background: #1F6DF0;
    border-color: rgba(47, 125, 246, 120);
}}

QPushButton:pressed {{
    background: #185BD4;
    border-color: rgba(20, 91, 212, 160);
}}

QPushButton:focus {{
    border: 1px solid rgba(47, 125, 246, 170);
}}

QPushButton:disabled {{
    background: rgba(224, 231, 242, 180);
    color: #98A2B3;
    border-color: rgba(118, 134, 159, 35);
}}

QPushButton#GhostButton,
QPushButton#LiquidPillButton {{
    background: #FFFFFF;
    border: 1px solid {TOKENS.border_soft};
    color: #21314D;
}}

QPushButton#GhostButton:hover,
QPushButton#LiquidPillButton:hover {{
    background: #E8F2FF;
    border-color: rgba(47, 125, 246, 115);
    color: #0F3575;
}}

QPushButton#GhostButton:pressed,
QPushButton#LiquidPillButton:pressed {{
    background: #D8EAFE;
    border-color: rgba(47, 125, 246, 150);
    color: #0B2F6F;
}}

QPushButton#GhostButton:focus,
QPushButton#LiquidPillButton:focus {{
    background: #F4F9FF;
    border-color: rgba(47, 125, 246, 160);
}}

QPushButton#BottomActionButton {{
    background: #FFFFFF;
    border: 1px solid {TOKENS.border_soft};
    border-radius: 14px;
    color: #000000;
    font-size: 13px;
    font-weight: 760;
    padding: 0 14px;
}}

QPushButton#BottomActionButton:hover {{
    background: #E8F2FF;
    border-color: rgba(47, 125, 246, 115);
    color: #0F3575;
}}

QPushButton#BottomActionButton:pressed {{
    background: #D8EAFE;
    border-color: rgba(47, 125, 246, 150);
    color: #0B2F6F;
}}

QPushButton#BottomActionButton:focus {{
    background: #F4F9FF;
    border-color: rgba(47, 125, 246, 160);
}}

QPushButton#LiquidPillButton[variant="primary"] {{
    background: {TOKENS.accent};
    color: white;
}}

QPushButton#LiquidPillButton[variant="soft"] {{
    background: {TOKENS.accent_soft};
    color: #1F66D1;
}}

QPushButton#NavButton {{
    background: rgba(255, 255, 255, 92);
    border: 1px solid rgba(255, 255, 255, 88);
    color: #000000;
    text-align: left;
    padding: 0 16px;
    border-radius: 12px;
    min-height: 40px;
    max-height: 40px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#NavButton:hover {{
    background: rgba(232, 242, 255, 210);
    border-color: rgba(47, 125, 246, 70);
    color: #0F3575;
}}

QPushButton#NavButton:pressed {{
    background: rgba(216, 234, 254, 235);
    border-color: rgba(47, 125, 246, 130);
    color: #0B2F6F;
}}

QPushButton#NavButton:checked {{
    background: rgba(47, 125, 246, 225);
    border-color: rgba(47, 125, 246, 120);
    color: #000000;
}}

QFrame#FeatureCard,
QGroupBox {{
    background: #FFFFFF;
    border: 1px solid rgba(84, 101, 130, 78);
    border-radius: {TOKENS.radius_card}px;
    color: {TOKENS.text};
}}

QGroupBox {{
    margin-top: 10px;
    padding: 18px 14px 14px 14px;
    font-weight: 700;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 5px;
    color: {TOKENS.text};
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QListWidget, QTableWidget {{
    background: #FFFFFF;
    border: 1px solid {TOKENS.border_soft};
    border-radius: {TOKENS.radius_input}px;
    color: {TOKENS.text};
    padding: 7px 10px;
    selection-background-color: #CCE0FF;
}}

QLineEdit:hover,
QSpinBox:hover,
QDoubleSpinBox:hover,
QTextEdit:hover,
QListWidget:hover,
QTableWidget:hover {{
    background: #F8FBFF;
    border-color: rgba(47, 125, 246, 95);
}}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QTextEdit:focus,
QListWidget:focus,
QTableWidget:focus {{
    background: #FFFFFF;
    border-color: rgba(47, 125, 246, 165);
}}

QComboBox {{
    padding-right: 34px;
}}

QComboBox:hover {{
    background: #F8FBFF;
    border-color: rgba(47, 125, 246, 110);
}}

QComboBox:on {{
    background: #E8F2FF;
    border-color: rgba(47, 125, 246, 150);
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border-left: 1px solid rgba(118, 134, 159, 38);
    border-top-right-radius: {TOKENS.radius_input}px;
    border-bottom-right-radius: {TOKENS.radius_input}px;
    background: rgba(248, 250, 253, 210);
}}

QComboBox::drop-down:hover {{
    background: #E8F2FF;
    border-left-color: rgba(47, 125, 246, 80);
}}

QComboBox::down-arrow {{
    image: url("{CHEVRON_DOWN}");
    width: 14px;
    height: 14px;
}}

QComboBox::down-arrow:hover {{
    image: url("{CHEVRON_DOWN_HOVER}");
}}

QLabel#DimensionSeparator {{
    color: #000000;
    font-size: 20px;
    font-weight: 760;
}}

QTextEdit {{
    font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei UI";
    color: #283548;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    min-height: 26px;
}}

QSpinBox, QDoubleSpinBox {{
    padding-right: 38px;
}}

QSpinBox::up-button,
QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 32px;
    margin: 0px;
    border-left: 1px solid rgba(118, 134, 159, 48);
    border-bottom: 1px solid rgba(118, 134, 159, 28);
    border-top-right-radius: {TOKENS.radius_input}px;
    border-bottom-right-radius: 0px;
    background: rgba(248, 250, 253, 210);
}}

QSpinBox::down-button,
QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 32px;
    margin: 0px;
    border-left: 1px solid rgba(118, 134, 159, 48);
    border-top: 0;
    border-top-right-radius: 0px;
    border-bottom-right-radius: {TOKENS.radius_input}px;
    background: rgba(248, 250, 253, 210);
}}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover {{
    background: #E8F2FF;
    border-left-color: rgba(47, 125, 246, 80);
}}

QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow {{
    image: url("{CHEVRON_UP}");
    width: 12px;
    height: 12px;
}}

QSpinBox::up-arrow:hover,
QDoubleSpinBox::up-arrow:hover {{
    image: url("{CHEVRON_UP_HOVER}");
}}

QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow {{
    image: url("{CHEVRON_DOWN_SMALL}");
    width: 12px;
    height: 12px;
}}

QSpinBox::down-arrow:hover,
QDoubleSpinBox::down-arrow:hover {{
    image: url("{CHEVRON_DOWN_SMALL_HOVER}");
}}

QComboBox QAbstractItemView {{
    background: white;
    border: 1px solid {TOKENS.border_soft};
    selection-background-color: #E8F2FF;
    outline: 0;
}}

QComboBox QAbstractItemView::item {{
    min-height: 24px;
    padding: 5px 8px;
}}

QCheckBox {{
    min-height: 24px;
    spacing: 8px;
}}

QCheckBox:hover,
QRadioButton:hover {{
    color: #0F3575;
}}

QCheckBox::indicator,
QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid rgba(118, 134, 159, 90);
    background: rgba(255, 255, 255, 210);
}}

QCheckBox::indicator {{
    border-radius: 5px;
}}

QRadioButton::indicator {{
    border-radius: 9px;
}}

QCheckBox::indicator:hover,
QRadioButton::indicator:hover {{
    border-color: rgba(47, 125, 246, 150);
    background: #E8F2FF;
}}

QCheckBox::indicator:checked,
QRadioButton::indicator:checked {{
    border-color: rgba(47, 125, 246, 180);
    background: #2F7DF6;
}}

QCheckBox::indicator:pressed,
QRadioButton::indicator:pressed {{
    border-color: rgba(47, 125, 246, 190);
    background: #D8EAFE;
}}

QCheckBox::indicator:disabled,
QRadioButton::indicator:disabled {{
    border-color: rgba(118, 134, 159, 45);
    background: rgba(224, 231, 242, 150);
}}

QListWidget {{
    outline: 0;
}}

QListWidget::item {{
    padding: 4px;
    border-radius: 14px;
}}

QListWidget::item:selected {{
    background: rgba(47, 125, 246, 28);
}}

QWidget#TaskQueueItem {{
    background: transparent;
}}

QLabel#QueueStatPill {{
    background: rgba(232, 242, 255, 190);
    color: #1F66D1;
    border: 1px solid rgba(47, 125, 246, 38);
    border-radius: 12px;
    padding: 6px 8px;
    font-size: 12px;
    font-weight: 700;
}}

QLabel#TaskThumb {{
    background: rgba(225, 234, 247, 210);
    border: 1px solid rgba(118, 134, 159, 48);
    border-radius: 12px;
    color: #667085;
    font-size: 10px;
    font-weight: 800;
}}

QLabel#TaskName {{
    color: #1D2939;
    font-size: 12px;
    font-weight: 700;
}}

QLabel#TaskStatus {{
    color: #667085;
    font-size: 11px;
}}

QProgressBar,
QProgressBar#TaskMiniProgress {{
    background: rgba(225, 234, 247, 210);
    border: 0;
    border-radius: 8px;
    height: 10px;
    text-align: center;
}}

QProgressBar::chunk,
QProgressBar#TaskMiniProgress::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2F7DF6,
        stop:1 #35C28C);
    border-radius: 8px;
}}

QProgressBar#TaskMiniProgress {{
    border-radius: 5px;
}}

QProgressBar#TaskMiniProgress::chunk {{
    border-radius: 5px;
}}

QSlider::groove:horizontal {{
    background: rgba(206, 216, 230, 210);
    height: 5px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {TOKENS.accent};
    border: 1px solid rgba(255, 255, 255, 180);
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: #1F6DF0;
    border-color: rgba(232, 242, 255, 240);
}}

QSlider::handle:horizontal:pressed {{
    background: #185BD4;
}}

QSlider::groove:horizontal:hover {{
    background: rgba(198, 222, 255, 230);
}}

QFrame#LiquidGlassCard {{
    border-radius: {TOKENS.radius_card}px;
}}

QFrame#LiquidGlassCard[variant="blue"] {{
    background: #EBF5FF;
}}

QFrame#LiquidGlassCard[variant="green"] {{
    background: #EDFBF4;
}}

QFrame#LiquidGlassCard[variant="purple"] {{
    background: #F6F0FF;
}}

QFrame#LiquidTaskList {{
    background: #FFFFFF;
    border: 1px solid {TOKENS.border_soft};
    border-radius: 16px;
}}

QFrame#LiquidTaskHeaderRow {{
    background: #E8F2FF;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
}}

QFrame#LiquidTaskRow {{
    background: #FFFFFF;
    border-bottom: 1px solid rgba(65, 93, 132, 20);
}}

QLabel#LiquidTaskHeaderText {{
    color: #63708A;
    font-size: 12px;
    font-weight: 700;
}}

QLabel#LiquidTaskText {{
    color: #21314D;
    font-size: 13px;
}}

QWidget#SuperResolutionWorkbench {{
    background: transparent;
}}

QScrollArea {{
    background: transparent;
    border: 0;
}}

QScrollBar:vertical {{
    background: rgba(255, 255, 255, 80);
    width: 12px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: rgba(118, 134, 159, 120);
    border-radius: 6px;
    min-height: 44px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(47, 125, 246, 150);
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QFrame#SuperMainColumn {{
    background: transparent;
    border: 0;
}}

QFrame#SuperGlassCard,
QFrame#SuperModeBar,
QFrame#SuperTaskCenter,
QFrame#SuperWorkflowBar,
QFrame#SuperStatusBar {{
    background: #FFFFFF;
    border: 1px solid rgba(118, 134, 159, 46);
    border-radius: 16px;
}}

QFrame#SuperWorkflowBar {{
    border-radius: 14px;
}}

QFrame#SuperStatusBar {{
    border-radius: 12px;
}}

QFrame#SuperTaskCenter {{
    border-radius: {TOKENS.radius_shell}px;
}}

QFrame#SuperAdvancedPanel {{
    background: #F5F7FB;
    border: 0;
    border-radius: 12px;
}}

QLabel#SuperDropZone {{
    background: #F5F7FB;
    border: 1px dashed rgba(118, 134, 159, 90);
    border-radius: 14px;
    color: #667085;
    font-weight: 600;
}}

QTableWidget#SuperFileTable {{
    background: #FFFFFF;
    gridline-color: rgba(118, 134, 159, 30);
    border-radius: 12px;
}}

QHeaderView::section {{
    background: rgba(232, 242, 255, 180);
    border: 0;
    border-right: 1px solid rgba(118, 134, 159, 35);
    color: #475467;
    font-weight: 700;
    padding: 7px 8px;
}}

QRadioButton#TaskModeRadio {{
    color: #344054;
    font-weight: 700;
    spacing: 8px;
}}

QLabel#SuperWorkflowText {{
    color: #1D2939;
    font-size: 13px;
    font-weight: 700;
}}

QLabel#SuperTaskEmpty {{
    background: #F5F7FB;
    border: 1px dashed rgba(118, 134, 159, 70);
    border-radius: 14px;
    color: #667085;
    font-weight: 600;
}}

QPlainTextEdit#SuperRecentLog {{
    background: #F5F7FB;
    border: 1px solid rgba(118, 134, 159, 45);
    border-radius: 12px;
    color: #344054;
    font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei UI";
    font-size: 12px;
    padding: 8px;
}}
"""

DARK_THEME = LIGHT_THEME
