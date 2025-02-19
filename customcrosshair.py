import sys
import cv2
import numpy as np
import re
import json
import os
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QColor, QCursor, QShortcut, QKeySequence
from PyQt6.QtWidgets import (QApplication, QLabel, QWidget, QSlider, QVBoxLayout, 
                           QColorDialog, QPushButton, QLineEdit, QFileDialog, QGridLayout, QCheckBox)

class CrosshairOverlay(QWidget):
    def __init__(self, settings_window):
        super().__init__()
        self.settings_window = settings_window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.X11BypassWindowManagerHint  # Better Linux support
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)  # Prevent focus stealing
        
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Cache for the last drawn crosshair
        self._last_params = None
        self._cached_pixmap = None
        
        # Initialize crosshair_image
        self.crosshair_image = None
        
        # Enhanced crosshair properties
        self.size = 100
        self.color = (0, 255, 0)
        self.outline_color = (0, 0, 0)
        self.thickness = 2
        self.outline_thickness = 1
        self.show_outline = False
        
        # Inner line properties
        self.inner_length = 4
        self.inner_opacity = 1.0
        self.show_inner = True
        
        # Outer line properties
        self.outer_length = 0
        self.outer_opacity = 1.0
        self.show_outer = True
        
        # Center dot properties
        self.show_dot = False
        self.dot_opacity = 1.0
        self.dot_size = 2

        self.update_crosshair()
        self.center_on_screen()

    def update_crosshair(self):
        try:
            print("Starting update_crosshair")
            
            if self.crosshair_image is not None:
                print(f"Crosshair image shape: {self.crosshair_image.shape}")
                
                # Create a new image with padding (increased for better visibility)
                padding = 32  # Increased from 21 to 32
                img_size = max(self.size + padding, self.crosshair_image.shape[0] + padding)
                if img_size % 2 == 0:
                    img_size += 1
                
                print(f"Creating image of size: {img_size}x{img_size}")
                
                img = np.zeros((img_size, img_size, 4), dtype=np.uint8)
                
                # Calculate center position
                y_offset = (img_size - self.crosshair_image.shape[0]) // 2
                x_offset = (img_size - self.crosshair_image.shape[1]) // 2
                
                print(f"Offsets: x={x_offset}, y={y_offset}")
                
                # Scale the crosshair image to be larger
                scale_factor = 2  # Increase size by 2x
                scaled_size = (self.crosshair_image.shape[1] * scale_factor,
                             self.crosshair_image.shape[0] * scale_factor)
                scaled_image = cv2.resize(self.crosshair_image, scaled_size,
                                        interpolation=cv2.INTER_LINEAR)
                
                # Recalculate offsets for scaled image
                y_offset = (img_size - scaled_image.shape[0]) // 2
                x_offset = (img_size - scaled_image.shape[1]) // 2
                
                # Copy the scaled crosshair image to the center
                img[y_offset:y_offset+scaled_image.shape[0], 
                    x_offset:x_offset+scaled_image.shape[1]] = scaled_image
                
                # Convert to QImage and display
                qimg = QImage(img.data, img.shape[1], img.shape[0], 
                             img.shape[1] * 4, QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimg)
                
                print("Created QPixmap")
                
                self.label.setPixmap(pixmap)
                self.resize(img_size, img_size)
                
                print("Crosshair updated successfully")
                
            else:
                print("No crosshair image loaded")
                
        except Exception as e:
            print(f"Error in update_crosshair: {e}")
            import traceback
            traceback.print_exc()

    def center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        window_width = self.width()
        window_height = self.height()
        
        x = (screen_width - window_width) // 2 - 1
        y = (screen_height - window_height) // 2 - 1
        
        self.move(x, y)
        
        if hasattr(self, 'center_timer'):
            self.center_timer.stop()
        
        self.center_timer = QTimer(self)
        self.center_timer.timeout.connect(lambda: self.move(x, y))
        self.center_timer.start(16)

    def convert_to_recommended_resolution(self, image):
        try:
            print("Starting image conversion")  # Debug print
            
            # Target size for crosshair (increased for better visibility)
            target_size = 64  # Changed from 32 to 64 for better visibility
            
            # Convert to BGRA if needed
            if len(image.shape) == 2:  # Grayscale
                print("Converting grayscale to BGRA")
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
            elif len(image.shape) == 3 and image.shape[2] == 3:  # BGR
                print("Converting BGR to BGRA")
                image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
            
            print(f"Image shape before resize: {image.shape}")
            
            # Resize to target size
            image = cv2.resize(image, (target_size, target_size), 
                              interpolation=cv2.INTER_AREA)
            
            # Enhance contrast and brightness
            color_channels = image[:, :, :3]
            alpha_channel = image[:, :, 3]
            
            # Increase contrast and brightness
            color_channels = cv2.convertScaleAbs(color_channels, alpha=1.5, beta=30)
            
            # Merge back with alpha channel
            image = cv2.merge([color_channels[:,:,0], 
                              color_channels[:,:,1], 
                              color_channels[:,:,2], 
                              alpha_channel])
            
            print(f"Image shape after resize: {image.shape}")
            
            return image
            
        except Exception as e:
            print(f"Error in convert_to_recommended_resolution: {e}")
            import traceback
            traceback.print_exc()
            return None

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crosshair Settings")
        
        # Add hotkey support
        self.hidden = False
        
        self.init_ui()
        self.crosshair = CrosshairOverlay(self)
        self.crosshair.show()
        
        # Load saved settings on startup
        self.load_settings()
        
        # Setup hotkeys
        QShortcut(QKeySequence("H"), self, self.toggle_visibility)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Create grid layout for controls
        grid = QGridLayout()
        current_row = 0

        # Basic Settings Section
        basic_settings_label = QLabel("Basic Settings")
        basic_settings_label.setStyleSheet("font-weight: bold;")
        grid.addWidget(basic_settings_label, current_row, 0, 1, 3)
        current_row += 1
        
        # Size control
        size_label = QLabel("Size:")
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setMinimum(50)
        self.size_slider.setMaximum(200)
        self.size_slider.setValue(100)
        self.size_value = QLabel("100")
        self.size_slider.valueChanged.connect(self.update_size)
        grid.addWidget(size_label, current_row, 0)
        grid.addWidget(self.size_slider, current_row, 1)
        grid.addWidget(self.size_value, current_row, 2)
        current_row += 1
        
        # Thickness control
        thickness_label = QLabel("Thickness:")
        self.thickness_slider = QSlider(Qt.Orientation.Horizontal)
        self.thickness_slider.setMinimum(1)
        self.thickness_slider.setMaximum(10)
        self.thickness_slider.setValue(2)
        self.thickness_value = QLabel("2")
        self.thickness_slider.valueChanged.connect(self.update_thickness)
        grid.addWidget(thickness_label, current_row, 0)
        grid.addWidget(self.thickness_slider, current_row, 1)
        grid.addWidget(self.thickness_value, current_row, 2)
        current_row += 1

        # Color Settings Section
        color_settings_label = QLabel("Color Settings")
        color_settings_label.setStyleSheet("font-weight: bold;")
        grid.addWidget(color_settings_label, current_row, 0, 1, 3)
        current_row += 1
        
        # Color buttons
        self.color_button = QPushButton("Crosshair Color")
        self.color_button.clicked.connect(self.choose_color)
        grid.addWidget(self.color_button, current_row, 0, 1, 3)
        current_row += 1

        # Outline Settings Section
        outline_settings_label = QLabel("Outline Settings")
        outline_settings_label.setStyleSheet("font-weight: bold;")
        grid.addWidget(outline_settings_label, current_row, 0, 1, 3)
        current_row += 1
        
        # Outline toggle
        self.outline_check = QCheckBox("Show Outline")
        self.outline_check.stateChanged.connect(self.update_outline)
        grid.addWidget(self.outline_check, current_row, 0, 1, 3)
        current_row += 1
        
        # Outline color
        self.outline_color_button = QPushButton("Outline Color")
        self.outline_color_button.clicked.connect(self.choose_outline_color)
        grid.addWidget(self.outline_color_button, current_row, 0, 1, 3)
        current_row += 1

        # Inner Line Settings Section
        inner_settings_label = QLabel("Inner Line Settings")
        inner_settings_label.setStyleSheet("font-weight: bold;")
        grid.addWidget(inner_settings_label, current_row, 0, 1, 3)
        current_row += 1
        
        # Inner line toggle
        self.inner_check = QCheckBox("Show Inner Lines")
        self.inner_check.setChecked(True)
        self.inner_check.stateChanged.connect(self.update_inner_visibility)
        grid.addWidget(self.inner_check, current_row, 0, 1, 3)
        current_row += 1
        
        # Inner line opacity
        inner_opacity_label = QLabel("Inner Opacity:")
        self.inner_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.inner_opacity_slider.setMinimum(0)
        self.inner_opacity_slider.setMaximum(100)
        self.inner_opacity_slider.setValue(100)
        self.inner_opacity_value = QLabel("100")
        self.inner_opacity_slider.valueChanged.connect(
            lambda v: self.update_opacity('inner', v/100))
        grid.addWidget(inner_opacity_label, current_row, 0)
        grid.addWidget(self.inner_opacity_slider, current_row, 1)
        grid.addWidget(self.inner_opacity_value, current_row, 2)
        current_row += 1

        # Outer Line Settings Section
        outer_settings_label = QLabel("Outer Line Settings")
        outer_settings_label.setStyleSheet("font-weight: bold;")
        grid.addWidget(outer_settings_label, current_row, 0, 1, 3)
        current_row += 1
        
        # Outer line toggle
        self.outer_check = QCheckBox("Show Outer Lines")
        self.outer_check.setChecked(True)
        self.outer_check.stateChanged.connect(self.update_outer_visibility)
        grid.addWidget(self.outer_check, current_row, 0, 1, 3)
        current_row += 1
        
        # Outer line opacity
        outer_opacity_label = QLabel("Outer Opacity:")
        self.outer_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.outer_opacity_slider.setMinimum(0)
        self.outer_opacity_slider.setMaximum(100)
        self.outer_opacity_slider.setValue(100)
        self.outer_opacity_value = QLabel("100")
        self.outer_opacity_slider.valueChanged.connect(
            lambda v: self.update_opacity('outer', v/100))
        grid.addWidget(outer_opacity_label, current_row, 0)
        grid.addWidget(self.outer_opacity_slider, current_row, 1)
        grid.addWidget(self.outer_opacity_value, current_row, 2)
        current_row += 1

        # Center Dot Settings Section
        dot_settings_label = QLabel("Center Dot Settings")
        dot_settings_label.setStyleSheet("font-weight: bold;")
        grid.addWidget(dot_settings_label, current_row, 0, 1, 3)
        current_row += 1
        
        # Center dot toggle
        self.dot_check = QCheckBox("Show Center Dot")
        self.dot_check.stateChanged.connect(self.update_dot_visibility)
        grid.addWidget(self.dot_check, current_row, 0, 1, 3)
        current_row += 1
        
        # Center dot opacity
        dot_opacity_label = QLabel("Dot Opacity:")
        self.dot_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.dot_opacity_slider.setMinimum(0)
        self.dot_opacity_slider.setMaximum(100)
        self.dot_opacity_slider.setValue(100)
        self.dot_opacity_value = QLabel("100")
        self.dot_opacity_slider.valueChanged.connect(
            lambda v: self.update_opacity('dot', v/100))
        grid.addWidget(dot_opacity_label, current_row, 0)
        grid.addWidget(self.dot_opacity_slider, current_row, 1)
        grid.addWidget(self.dot_opacity_value, current_row, 2)
        current_row += 1

        # Add the grid to the main layout
        layout.addLayout(grid)
        
        # Valorant Code Input
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Paste Valorant crosshair code here")
        self.code_input.returnPressed.connect(self.parse_valorant_code)
        layout.addWidget(self.code_input)
        
        # Buttons at the bottom
        self.load_image_button = QPushButton("Load Custom Crosshair")
        self.load_image_button.clicked.connect(self.load_crosshair_image)
        layout.addWidget(self.load_image_button)
        
        save_button = QPushButton("Save Crosshair")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)
        
        load_button = QPushButton("Load Crosshair")
        load_button.clicked.connect(self.load_settings)
        layout.addWidget(load_button)
        
        # Connect slider value changes
        self.size_slider.valueChanged.connect(self.update_size)
        self.thickness_slider.valueChanged.connect(self.update_thickness)
        self.inner_opacity_slider.valueChanged.connect(
            lambda v: self.update_opacity('inner', v/100))
        self.outer_opacity_slider.valueChanged.connect(
            lambda v: self.update_opacity('outer', v/100))
        self.dot_opacity_slider.valueChanged.connect(
            lambda v: self.update_opacity('dot', v/100))
        
        # Connect checkbox state changes
        self.outline_check.stateChanged.connect(self.update_outline)
        self.inner_check.stateChanged.connect(self.update_inner_visibility)
        self.outer_check.stateChanged.connect(self.update_outer_visibility)
        self.dot_check.stateChanged.connect(self.update_dot_visibility)
        
        # Connect color buttons
        self.color_button.clicked.connect(self.choose_color)
        self.outline_color_button.clicked.connect(self.choose_outline_color)
        
        self.setLayout(layout)

    def toggle_visibility(self):
        if self.hidden:
            self.show()
            self.crosshair.show()
        else:
            self.hide()
            self.crosshair.hide()
        self.hidden = not self.hidden

    def update_size(self, value):
        self.size_value.setText(str(value))
        self.crosshair.size = value
        self.crosshair.update_crosshair()
        self.crosshair.center_on_screen()  # Recenter after size change

    def update_thickness(self, value):
        self.thickness_value.setText(str(value))
        self.crosshair.thickness = value
        self.crosshair.update_crosshair()

    def update_outline(self, state):
        self.crosshair.show_outline = bool(state)
        self.crosshair.update_crosshair()

    def update_inner_visibility(self, state):
        self.crosshair.show_inner = bool(state)
        self.crosshair.update_crosshair()

    def update_outer_visibility(self, state):
        self.crosshair.show_outer = bool(state)
        self.crosshair.update_crosshair()

    def update_dot_visibility(self, state):
        self.crosshair.show_dot = bool(state)
        self.crosshair.update_crosshair()

    def update_opacity(self, element, value):
        if element == 'inner':
            self.crosshair.inner_opacity = value
            self.inner_opacity_value.setText(str(int(value * 100)))
        elif element == 'outer':
            self.crosshair.outer_opacity = value
            self.outer_opacity_value.setText(str(int(value * 100)))
        elif element == 'dot':
            self.crosshair.dot_opacity = value
            self.dot_opacity_value.setText(str(int(value * 100)))
        self.crosshair.update_crosshair()

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.crosshair.color = (color.red(), color.green(), color.blue())
            self.crosshair.update_crosshair()

    def choose_outline_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.crosshair.outline_color = (color.red(), color.green(), color.blue())
            self.crosshair.update_crosshair()

    def parse_valorant_code(self):
        code = self.code_input.text()
        if not code:
            return
        
        # Pattern explanation:
        # 0;P - Primary settings
        # h;0 - Hide/Show (0 = show)
        # f;0 - Fade (0 = no fade)
        # 0t;1 - Primary outline (1 = enabled)
        # 0l;4 - Inner line length (4 units)
        # 0o;1 - Outer line length (1 unit)
        # 0a;1 - Inner line opacity (1 = 100%)
        # 0f;0 - Inner line offset
        # 1t;3 - Outline thickness (3 units)
        # 1o;2 - Outer line opacity (2 = 50%)
        # 1a;1 - Outer line opacity multiplier
        # 1m;0 - Movement error
        # 1f;0 - Firing error
        
        try:
            # Parse the code using regex
            pattern = r'0;P;.*?0t;(\d+);0l;(\d+);0o;(\d+);0a;(\d+);0f;(\d+);1t;(\d+);1o;(\d+);1a;(\d+)'
            match = re.search(pattern, code)
            
            if match:
                # Extract values
                outline_enabled = int(match.group(1))
                inner_length = int(match.group(2))
                outer_length = int(match.group(3))
                inner_opacity = int(match.group(4))
                inner_offset = int(match.group(5))
                outline_thickness = int(match.group(6))
                outer_opacity = int(match.group(7))
                outer_opacity_mult = int(match.group(8))
                
                # Update crosshair properties
                self.crosshair.show_outline = bool(outline_enabled)
                self.crosshair.inner_length = inner_length * 2
                self.crosshair.outer_length = outer_length * 2
                self.crosshair.inner_opacity = inner_opacity / 100
                self.crosshair.outline_thickness = outline_thickness
                self.crosshair.outer_opacity = (outer_opacity * outer_opacity_mult) / 100
                
                # Update UI elements
                self.outline_check.setChecked(self.crosshair.show_outline)
                self.inner_opacity_slider.setValue(int(inner_opacity))
                self.outer_opacity_slider.setValue(int(outer_opacity * outer_opacity_mult))
                
                # Update crosshair display
                self.crosshair.update_crosshair()
                print("Valorant crosshair code applied successfully!")
            else:
                print("Invalid Valorant crosshair code format")
        except Exception as e:
            print(f"Error parsing crosshair code: {e}")
    
    def load_crosshair_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Crosshair Image (Recommended: 32x32 or 64x64 PNG)",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            try:
                print(f"Loading image from: {file_path}")  # Debug print
                
                # Load original image with alpha channel
                image = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
                
                if image is None:
                    print("Failed to load image")
                    return
                
                print(f"Original image shape: {image.shape}")  # Debug print
                
                # Convert to recommended format
                converted_image = self.crosshair.convert_to_recommended_resolution(image)
                
                if converted_image is None:
                    print("Failed to convert image")
                    return
                
                print(f"Converted image shape: {converted_image.shape}")  # Debug print
                
                # Store the image and update the display
                self.crosshair.crosshair_image = converted_image
                print("Image stored in crosshair object")  # Debug print
                
                # Force an update
                self.crosshair.update_crosshair()
                print("Update crosshair called")  # Debug print
                
                # Center the crosshair
                self.crosshair.center_on_screen()
                print("Centered on screen")  # Debug print
                
            except Exception as e:
                print(f"Error in load_crosshair_image: {e}")
                import traceback
                traceback.print_exc()

    def save_settings(self):
        settings = {
            'size': self.crosshair.size,
            'color': self.crosshair.color,
            'outline_color': self.crosshair.outline_color,
            'thickness': self.crosshair.thickness,
            'outline_thickness': self.crosshair.outline_thickness,
            'show_outline': self.crosshair.show_outline,
            'inner_length': self.crosshair.inner_length,
            'inner_opacity': self.crosshair.inner_opacity,
            'show_inner': self.crosshair.show_inner,
            'outer_length': self.crosshair.outer_length,
            'outer_opacity': self.crosshair.outer_opacity,
            'show_outer': self.crosshair.show_outer,
            'show_dot': self.crosshair.show_dot,
            'dot_opacity': self.crosshair.dot_opacity,
            'dot_size': self.crosshair.dot_size
        }
        
        try:
            with open('crosshair_settings.json', 'w') as f:
                json.dump(settings, f)
            print("Settings saved successfully!")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self):
        if not os.path.exists('crosshair_settings.json'):
            return
            
        try:
            with open('crosshair_settings.json', 'r') as f:
                settings = json.load(f)
                
            self.crosshair.size = settings.get('size', 100)
            self.crosshair.color = tuple(settings.get('color', (0, 255, 0)))
            self.crosshair.thickness = settings.get('thickness', 2)
            self.crosshair.outline_thickness = settings.get('outline_thickness', 1)
            self.crosshair.show_outline = settings.get('show_outline', False)
            self.crosshair.inner_length = settings.get('inner_length', 4)
            self.crosshair.inner_opacity = settings.get('inner_opacity', 1.0)
            self.crosshair.show_inner = settings.get('show_inner', True)
            self.crosshair.outer_length = settings.get('outer_length', 0)
            self.crosshair.outer_opacity = settings.get('outer_opacity', 1.0)
            self.crosshair.show_outer = settings.get('show_outer', True)
            self.crosshair.show_dot = settings.get('show_dot', False)
            self.crosshair.dot_opacity = settings.get('dot_opacity', 1.0)
            self.crosshair.dot_size = settings.get('dot_size', 2)
            
            # Update UI elements
            self.size_slider.setValue(self.crosshair.size)
            self.thickness_slider.setValue(self.crosshair.thickness)
            self.inner_opacity_slider.setValue(int(self.crosshair.inner_opacity * 100))
            self.outer_opacity_slider.setValue(int(self.crosshair.outer_opacity * 100))
            self.outline_check.setChecked(self.crosshair.show_outline)
            self.inner_check.setChecked(self.crosshair.show_inner)
            self.outer_check.setChecked(self.crosshair.show_outer)
            self.dot_check.setChecked(self.crosshair.show_dot)
            
            # Update crosshair display
            self.crosshair.update_crosshair()
            print("Settings loaded successfully!")
        except Exception as e:
            print(f"Error loading settings: {e}")

    def closeEvent(self, event):
        # Clean up when closing
        if hasattr(self.crosshair, 'center_timer'):
            self.crosshair.center_timer.stop()
        self.crosshair.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    settings = SettingsWindow()
    settings.show()
    sys.exit(app.exec())