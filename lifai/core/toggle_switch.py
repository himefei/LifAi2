import tkinter as tk
from tkinter import ttk
import logging
import time

class ToggleSwitch(ttk.Frame):
    def __init__(self, parent, text, command=None, width=60, height=28):
        super().__init__(parent)
        
        # Variables
        self.width = width
        self.height = height
        self.command = command
        self.enabled = tk.BooleanVar(value=False)
        
        # Animation variables
        self.animation_running = False
        self.animation_steps = 10
        self.animation_speed = 16  # milliseconds per step (60fps)
        
        # Configure style for the switch
        self.style = ttk.Style()
        self.style.configure('Switch.TFrame', background='#ffffff')
        self.style.configure('SwitchLabel.TLabel', 
                           background='#ffffff',
                           font=('Segoe UI', 10))
        
        # Main container
        self.container = ttk.Frame(self, style='Switch.TFrame')
        self.container.pack(fill=tk.X, padx=5, pady=2)
        
        # Label
        self.label = ttk.Label(self.container, 
                              text=text, 
                              style='SwitchLabel.TLabel')
        self.label.pack(side=tk.LEFT, padx=(5, 10))
        
        # Create canvas for custom switch
        self.canvas = tk.Canvas(
            self.container,
            width=self.width,
            height=self.height,
            bg='#ffffff',
            bd=0,
            highlightthickness=0
        )
        self.canvas.pack(side=tk.RIGHT, padx=5)
        
        # Current circle position
        self.circle_pos = 6  # Starting position
        
        # Draw initial switch state
        self._draw_switch()
        
        # Bind events
        self.canvas.bind('<Button-1>', self._toggle)
        self.canvas.bind('<Enter>', self._on_enter)
        self.canvas.bind('<Leave>', self._on_leave)

    def _draw_switch(self, hover=False, circle_x=None):
        self.canvas.delete('all')
        
        # Colors
        if self.enabled.get():
            bg_color = '#34c759' if not hover else '#2fb350'  # Green
        else:
            bg_color = '#e9e9ea' if not hover else '#dedede'  # Gray
            
        switch_color = '#ffffff'  # White
        shadow_color = '#dddddd'  # Light gray for shadow
        
        # Draw background (rounded rectangle)
        radius = self.height // 2
        self.canvas.create_rounded_rect(
            2, 2,
            self.width - 2, self.height - 2,
            radius,
            fill=bg_color,
            outline=''
        )
        
        # Draw switch circle
        circle_diameter = self.height - 8
        circle_x = circle_x if circle_x is not None else self.circle_pos
            
        # Add shadow effect (multiple circles with decreasing opacity)
        shadow_layers = 3
        for i in range(shadow_layers):
            offset = i * 0.5
            self.canvas.create_oval(
                circle_x + offset, 4 + offset,
                circle_x + circle_diameter + offset, 4 + circle_diameter + offset,
                fill=shadow_color,
                outline=''
            )
        
        # Draw main circle
        self.canvas.create_oval(
            circle_x, 4,
            circle_x + circle_diameter, 4 + circle_diameter,
            fill=switch_color,
            outline=''
        )

    def _animate_switch(self, start_pos, end_pos):
        if self.animation_running:
            return
            
        self.animation_running = True
        steps = self.animation_steps
        
        # Add easing function for smoother animation
        def ease_in_out(t):
            # Cubic easing
            t *= 2
            if t < 1:
                return 0.5 * t * t * t
            t -= 2
            return 0.5 * (t * t * t + 2)
        
        def animate_step(step):
            if step <= steps:
                progress = ease_in_out(step / steps)
                current_pos = start_pos + (end_pos - start_pos) * progress
                self._draw_switch(circle_x=current_pos)
                self.after(self.animation_speed, lambda: animate_step(step + 1))
            else:
                self.circle_pos = end_pos
                self._draw_switch()
                self.animation_running = False
                if self.command:
                    self.command()
        
        animate_step(0)

    def _toggle(self, event=None):
        if self.animation_running:
            return
            
        self.enabled.set(not self.enabled.get())
        
        # Calculate start and end positions
        start_pos = self.circle_pos
        end_pos = self.width - self.height + 2 if self.enabled.get() else 6
        
        # Start animation
        self._animate_switch(start_pos, end_pos)

    def _on_enter(self, event):
        self._draw_switch(hover=True, circle_x=self.circle_pos)

    def _on_leave(self, event):
        self._draw_switch(hover=False, circle_x=self.circle_pos)

    def get(self):
        return self.enabled.get()

    def set(self, value):
        if value != self.enabled.get():
            self.enabled.set(bool(value))
            end_pos = self.width - self.height + 2 if value else 6
            self._animate_switch(self.circle_pos, end_pos)
        else:
            self._draw_switch()

# Add rounded rectangle capability to Canvas
def _create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1
    ]
    return self.create_polygon(points, smooth=True, **kwargs)

tk.Canvas.create_rounded_rect = _create_rounded_rect