import tkinter as tk

def show_popup(duration=3):
    print("Starting popup...")
    root = tk.Tk()
    root.overrideredirect(True) # Borderless
    root.attributes("-topmost", True) # Always on top
    root.attributes("-alpha", 0.9)
    
    # Position at bottom right corner
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    width = 200
    height = 200
    x = screen_width - width - 40 # 40px padding from the right
    y = screen_height - height - 80 # 80px padding from the bottom (above taskbar)
    
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.configure(bg='#1c1c1e')
    
    lbl = tk.Label(root, text="HELIOS\nListening...", font=("Segoe UI", 16, "bold"), bg="#1c1c1e", fg="#ff2a85")
    lbl.pack(expand=True, fill='both')
    
    # Schedule the popup to close after 'duration' seconds
    root.after(duration * 1000, root.destroy)
    
    # Run the window
    root.mainloop()
    print("Popup closed.")

if __name__ == "__main__":
    show_popup()
