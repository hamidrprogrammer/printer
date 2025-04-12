import tkinter as tk

class App(object):

    def __init__(self, parent):

        self.root = parent
        self.root.title("Main Frame")
        self.frame = tk.Frame(parent)
        self.frame.pack()
        label = tk.Label(self.frame, text = "This is the main frame")
        label.grid()
        btn = tk.Button(self.frame, text= "Open the popup window")
        btn.grid(row=1)
        
if __name__ == "__main__":
  
    root = tk.Tk()
    app = App(root)
    root.geometry("200x150")
    root.mainloop()
