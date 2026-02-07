#!/usr/bin/env python3
"""
Test script to demonstrate the modern theme styling
This creates a demo window with various Qt widgets to showcase the new styling
"""

import sys
from pathlib import Path

# Add Nagstamon to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox, QRadioButton,
        QGroupBox, QTextEdit, QSlider, QSpinBox, QProgressBar, QTabWidget
    )
    from PyQt6.QtCore import Qt
    
    # Load the modern theme
    from Nagstamon.config import RESOURCES
    from os import sep
    
    class DemoWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Nagstamon Modern Theme Demo")
            self.setGeometry(100, 100, 800, 600)
            
            # Central widget
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            
            # Main layout
            main_layout = QVBoxLayout(central_widget)
            main_layout.setSpacing(15)
            
            # Header with title
            header = QLabel("Modern Theme Demo - Qt6 Styling")
            header.setStyleSheet("font-size: 18pt; font-weight: bold; padding: 10px;")
            main_layout.addWidget(header)
            
            # Buttons Section
            button_group = QGroupBox("Buttons")
            button_layout = QHBoxLayout()
            button_layout.setSpacing(10)
            
            btn1 = QPushButton("Primary Button")
            btn2 = QPushButton("Secondary Button")
            btn3 = QPushButton("Disabled Button")
            btn3.setEnabled(False)
            
            button_layout.addWidget(btn1)
            button_layout.addWidget(btn2)
            button_layout.addWidget(btn3)
            button_group.setLayout(button_layout)
            main_layout.addWidget(button_group)
            
            # Input Fields Section
            input_group = QGroupBox("Input Fields")
            input_layout = QVBoxLayout()
            input_layout.setSpacing(10)
            
            # Text input
            text_label = QLabel("Text Input:")
            text_input = QLineEdit()
            text_input.setPlaceholderText("Enter text here...")
            input_layout.addWidget(text_label)
            input_layout.addWidget(text_input)
            
            # ComboBox
            combo_label = QLabel("Dropdown:")
            combo = QComboBox()
            combo.addItems(["Option 1", "Option 2", "Option 3", "Option 4"])
            input_layout.addWidget(combo_label)
            input_layout.addWidget(combo)
            
            input_group.setLayout(input_layout)
            main_layout.addWidget(input_group)
            
            # Checkboxes and Radio Buttons
            check_group = QGroupBox("Selection Controls")
            check_layout = QHBoxLayout()
            
            check_vlayout1 = QVBoxLayout()
            check_vlayout1.addWidget(QLabel("Checkboxes:"))
            check1 = QCheckBox("Option A")
            check2 = QCheckBox("Option B")
            check2.setChecked(True)
            check_vlayout1.addWidget(check1)
            check_vlayout1.addWidget(check2)
            
            check_vlayout2 = QVBoxLayout()
            check_vlayout2.addWidget(QLabel("Radio Buttons:"))
            radio1 = QRadioButton("Choice 1")
            radio2 = QRadioButton("Choice 2")
            radio1.setChecked(True)
            check_vlayout2.addWidget(radio1)
            check_vlayout2.addWidget(radio2)
            
            check_layout.addLayout(check_vlayout1)
            check_layout.addLayout(check_vlayout2)
            check_group.setLayout(check_layout)
            main_layout.addWidget(check_group)
            
            # Slider and SpinBox
            slider_group = QGroupBox("Numeric Controls")
            slider_layout = QHBoxLayout()
            
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(50)
            
            spinbox = QSpinBox()
            spinbox.setRange(0, 100)
            spinbox.setValue(25)
            
            slider_layout.addWidget(QLabel("Slider:"))
            slider_layout.addWidget(slider)
            slider_layout.addWidget(QLabel("SpinBox:"))
            slider_layout.addWidget(spinbox)
            slider_group.setLayout(slider_layout)
            main_layout.addWidget(slider_group)
            
            # Progress Bar
            progress_group = QGroupBox("Progress")
            progress_layout = QVBoxLayout()
            progress = QProgressBar()
            progress.setValue(65)
            progress_layout.addWidget(progress)
            progress_group.setLayout(progress_layout)
            main_layout.addWidget(progress_group)
            
            # Text Area
            text_group = QGroupBox("Text Area")
            text_layout = QVBoxLayout()
            text_edit = QTextEdit()
            text_edit.setPlaceholderText("This is a multi-line text area with modern styling...")
            text_edit.setMaximumHeight(100)
            text_layout.addWidget(text_edit)
            text_group.setLayout(text_layout)
            main_layout.addWidget(text_group)
            
            # Info Label
            info_label = QLabel("✓ Theme applied: Rounded corners, bigger buttons, increased spacing!")
            info_label.setStyleSheet("color: #4a90e2; font-weight: bold; padding: 10px;")
            main_layout.addWidget(info_label)
            
            main_layout.addStretch()
    
    # Create application
    app = QApplication(sys.argv)
    
    # Load and apply the modern theme stylesheet
    modern_theme_path = f'{RESOURCES}{sep}modern_theme.qss'
    try:
        with open(modern_theme_path, 'r', encoding='utf-8') as qss_file:
            modern_stylesheet = qss_file.read()
        app.setStyleSheet(modern_stylesheet)
        print(f"✓ Modern theme loaded from: {modern_theme_path}")
    except FileNotFoundError:
        print(f"✗ Could not find theme file at: {modern_theme_path}")
        print("  Using default Qt styling")
    
    # Create and show window
    window = DemoWindow()
    window.show()
    
    print("\n" + "="*60)
    print("Modern Theme Demo Window")
    print("="*60)
    print("\nKey styling features applied:")
    print("  • Buttons: 10px 20px padding, 8px border-radius")
    print("  • Inputs: 8px 12px padding, 6px border-radius")
    print("  • Spacing: 15px between elements (was 10px)")
    print("  • GroupBoxes: 16px padding, 8px border-radius")
    print("  • Modern color scheme with hover effects")
    print("\n" + "="*60 + "\n")
    
    sys.exit(app.exec())

except ImportError as e:
    print(f"Error: Missing required dependency - {e}")
    print("\nThis demo requires PyQt6. Install with:")
    print("  pip install PyQt6")
    sys.exit(1)
