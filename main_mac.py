import sys
from PySide2.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QGraphicsDropShadowEffect
from PySide2.QtGui import QColor
from qt_material import apply_stylesheet

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Create a vertical layout
        layout = QVBoxLayout()

        # Text input field with placeholder text
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter text to connect")
        
        # Connect button with shadow effect
        self.connect_button = QPushButton("Connect")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 160))  # Semi-transparent black shadow
        shadow.setOffset(0, 2)  # Slight vertical offset for elevation
        self.connect_button.setGraphicsEffect(shadow)

        # Add widgets to the layout
        layout.addWidget(self.input_field)
        layout.addWidget(self.connect_button)

        # Set layout spacing and margins for better appearance
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # Apply the layout to the window
        self.setLayout(layout)
        self.setWindowTitle("Connect App")

if __name__ == "__main__":
    # Initialize the application
    app = QApplication(sys.argv)
    
    # Apply Material Design theme
    apply_stylesheet(app, theme='dark_teal.xml')
    
    # Create and show the window
    window = MainWindow()
    window.show()
    
    # Run the application
    sys.exit(app.exec_())
