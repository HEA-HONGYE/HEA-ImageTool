from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeTokens:
    background: str = "#F5F7FB"
    surface: str = "rgba(255, 255, 255, 199)"
    surface_strong: str = "rgba(255, 255, 255, 230)"
    surface_soft: str = "rgba(255, 255, 255, 150)"
    border: str = "rgba(255, 255, 255, 64)"
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
    border-radius: {TOKENS.radius_card}px;
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
}}

QPushButton:disabled {{
    background: rgba(224, 231, 242, 180);
    color: #98A2B3;
}}

QPushButton#GhostButton,
QPushButton#LiquidPillButton {{
    background: rgba(255, 255, 255, 180);
    border: 1px solid {TOKENS.border_soft};
    color: #21314D;
}}

QPushButton#GhostButton:hover,
QPushButton#LiquidPillButton:hover {{
    background: rgba(255, 255, 255, 230);
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
    background: transparent;
    border: 0;
    color: #344054;
    text-align: left;
    padding: 10px 14px;
    border-radius: 999px;
    min-height: 28px;
}}

QPushButton#NavButton:hover {{
    background: rgba(255, 255, 255, 175);
}}

QPushButton#NavButton:checked {{
    background: rgba(47, 125, 246, 210);
    color: white;
}}

QFrame#FeatureCard,
QGroupBox {{
    background: rgba(255, 255, 255, 178);
    border: 1px solid {TOKENS.border_soft};
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

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QListWidget {{
    background: rgba(255, 255, 255, 205);
    border: 1px solid {TOKENS.border_soft};
    border-radius: {TOKENS.radius_input}px;
    color: {TOKENS.text};
    padding: 7px 10px;
    selection-background-color: #CCE0FF;
}}

QTextEdit {{
    font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei UI";
    color: #283548;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    min-height: 26px;
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
    border-radius: 5px;
    height: 10px;
    text-align: center;
}}

QProgressBar::chunk,
QProgressBar#TaskMiniProgress::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2F7DF6,
        stop:1 #35C28C);
    border-radius: 5px;
}}

QSlider::groove:horizontal {{
    background: rgba(206, 216, 230, 210);
    height: 5px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {TOKENS.accent};
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QFrame#LiquidGlassCard {{
    border-radius: {TOKENS.radius_card}px;
}}

QFrame#LiquidGlassCard[variant="blue"] {{
    background: rgba(235, 245, 255, 214);
}}

QFrame#LiquidGlassCard[variant="green"] {{
    background: rgba(237, 251, 244, 214);
}}

QFrame#LiquidGlassCard[variant="purple"] {{
    background: rgba(246, 240, 255, 214);
}}

QFrame#LiquidTaskList {{
    background: rgba(255, 255, 255, 150);
    border: 1px solid {TOKENS.border_soft};
    border-radius: 16px;
}}

QFrame#LiquidTaskHeaderRow {{
    background: rgba(232, 242, 255, 170);
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
}}

QFrame#LiquidTaskRow {{
    background: rgba(255, 255, 255, 95);
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
"""

DARK_THEME = LIGHT_THEME
