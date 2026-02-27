import tkinter as tk

class TankWidget(tk.Canvas):
    def __init__(self, parent, width=150, height=300, max_level=5.0):
        super().__init__(parent, width=width, height=height, bg="#2b3e50", highlightthickness=0)
        self.width = width
        self.height = height
        self.max_level = max_level
        
        # Tank dimensions (centered)
        self.tank_x = 20
        self.tank_y = 20
        self.tank_w = width - 40
        self.tank_h = height - 40
        
        # Draw Tank Outline
        self.create_rectangle(
            self.tank_x, self.tank_y, 
            self.tank_x + self.tank_w, self.tank_y + self.tank_h,
            outline="white", width=3
        )
        
        # Level Rectangle (initially empty)
        self.level_rect = self.create_rectangle(
            self.tank_x + 2, self.tank_y + self.tank_h,
            self.tank_x + self.tank_w - 2, self.tank_y + self.tank_h,
            fill="#3498db", outline=""
        )
        
        # Axis Labels
        self.create_text(10, self.tank_y, text=f"{max_level}m", anchor="e", font=("Arial", 8), fill="white")
        self.create_text(10, self.tank_y + self.tank_h, text="0m", anchor="e", font=("Arial", 8), fill="white")

    def _get_color_from_temp(self, temp):
        """
        Map temperature to color (Blue -> Red).
        20 C -> Blue
        100 C -> Red
        """
        # Clamp temp 20-100
        t = max(20, min(temp, 120))
        ratio = (t - 20) / 100.0 # 0 to 1
        
        # Blue: (0, 0, 255) -> Red: (255, 0, 0)
        r = int(ratio * 255)
        g = 0
        b = int((1 - ratio) * 255)
        
        return f"#{r:02x}{g:02x}{b:02x}"

    def update_level(self, current_level, current_temp):
        """
        Update the visual level height and color based on Temperature.
        
        Args:
            current_level (float): Current level in meters.
            current_temp (float): Current Temperature (deg C).
        """
        # Clamp level
        level = max(0, min(current_level, self.max_level))
        
        # Calculate pixel height
        px_per_m = self.tank_h / self.max_level
        fill_height = level * px_per_m
        
        # Update coordinates (y is inverted in screen coords)
        # Bottom is self.tank_y + self.tank_h
        top_y = (self.tank_y + self.tank_h) - fill_height
        
        self.coords(
            self.level_rect,
            self.tank_x + 2, top_y,
            self.tank_x + self.tank_w - 2, self.tank_y + self.tank_h
        )
        
        # Update color based on temperature
        color = self._get_color_from_temp(current_temp)
        self.itemconfig(self.level_rect, fill=color)
