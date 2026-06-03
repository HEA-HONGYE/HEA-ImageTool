DARK_THEME = """
* {
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
    letter-spacing: 0px;
}

QMainWindow, QWidget {
    background: #15181d;
    color: #eef2f7;
}

QFrame#Sidebar {
    background: #101318;
    border-right: 1px solid #252b34;
}

QFrame#RightPanel, QFrame#BottomPanel {
    background: #181c22;
    border: 1px solid #2a313b;
}

QLabel#HeroTitle {
    font-size: 34px;
    font-weight: 700;
}

QLabel#PanelTitle {
    font-size: 24px;
    font-weight: 700;
}

QLabel#CardTitle {
    font-size: 17px;
    font-weight: 700;
}

QLabel#MutedText {
    color: #9aa6b2;
}

QLabel#IntroText {
    color: #c8d1dc;
    font-size: 15px;
}

QPushButton {
    background: #2c73d2;
    border: 0;
    border-radius: 6px;
    padding: 8px 12px;
    color: white;
    font-weight: 600;
}

QPushButton:hover {
    background: #3782e6;
}

QPushButton:pressed {
    background: #1f5fb4;
}

QPushButton#NavButton {
    background: transparent;
    color: #c8d1dc;
    text-align: left;
    padding: 10px 14px;
    border-radius: 6px;
}

QPushButton#NavButton:hover {
    background: #1c222b;
}

QPushButton#NavButton:checked {
    background: #243144;
    color: #ffffff;
}

QPushButton#GhostButton {
    background: #222832;
    color: #d8dee8;
}

QPushButton#GhostButton:hover {
    background: #2b3340;
}

QFrame#FeatureCard, QGroupBox {
    background: #1b2028;
    border: 1px solid #2d3541;
    border-radius: 8px;
}

QGroupBox {
    margin-top: 10px;
    padding: 18px 14px 14px 14px;
    font-weight: 700;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 5px;
}

QLineEdit, QComboBox, QTextEdit, QListWidget {
    background: #11151b;
    border: 1px solid #303946;
    border-radius: 6px;
    padding: 7px 9px;
    color: #eef2f7;
}

QListWidget::item {
    padding: 8px;
    border-radius: 5px;
}

QListWidget::item:selected {
    background: #26384f;
}

QProgressBar {
    background: #101318;
    border: 1px solid #303946;
    border-radius: 5px;
    height: 10px;
    text-align: center;
}

QProgressBar::chunk {
    background: #41b883;
    border-radius: 5px;
}

QSlider::groove:horizontal {
    background: #303946;
    height: 5px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #41b883;
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
"""
