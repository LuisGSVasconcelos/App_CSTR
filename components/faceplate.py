import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class Faceplate(ttk.LabelFrame):
    def __init__(self, parent, title, controller, min_sp=0, max_sp=100, unit="", resolution=0.1):
        super().__init__(parent, text=title)
        self.controller = controller
        self.min_sp = min_sp
        self.max_sp = max_sp
        self.unit = unit
        self.mode = "AUTO" # AUTO or MAN
        
        # Variables
        self.sp_var = tk.DoubleVar(value=0.0)
        self.pv_var = tk.DoubleVar(value=0.0)
        self.op_var = tk.DoubleVar(value=0.0)
        self.manual_op_var = tk.DoubleVar(value=0.0)
        
        # PV Display
        ttk.Label(self, text=f"PV ({unit}):", font=("Arial", 10)).grid(row=0, column=0, sticky="e")
        self.lbl_pv = ttk.Label(self, textvariable=self.pv_var, font=("Arial", 14, "bold"), bootstyle="success")
        self.lbl_pv.grid(row=0, column=1, sticky="w", padx=5)
        
        # SP Display/Entry
        ttk.Label(self, text="SP:", font=("Arial", 10)).grid(row=1, column=0, sticky="e")
        self.entry_sp = ttk.Entry(self, textvariable=self.sp_var, width=8)
        self.entry_sp.grid(row=1, column=1, sticky="w", padx=5)
        
        # OP Display
        ttk.Label(self, text="OP (%):", font=("Arial", 10)).grid(row=2, column=0, sticky="e")
        self.lbl_op = ttk.Label(self, textvariable=self.op_var, font=("Arial", 10))
        self.lbl_op.grid(row=2, column=1, sticky="w", padx=5)
        
        # SP Slider
        self.scale_sp = ttk.Scale(self, variable=self.sp_var, from_=min_sp, to=max_sp, orient="horizontal", length=150, bootstyle="info")
        self.scale_sp.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)
        
        # Manual OP Slider
        self.scale_op = ttk.Scale(self, variable=self.manual_op_var, from_=0, to=100, orient="horizontal", state="disabled", length=150, bootstyle="warning")
        self.scale_op.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)
        
        # Mode Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)
        self.btn_auto = ttk.Button(btn_frame, text="AUTO", bootstyle="success", width=8, command=lambda: self.set_mode("AUTO"))
        self.btn_auto.pack(side="left", padx=2)
        self.btn_man = ttk.Button(btn_frame, text="MANUAL", bootstyle="secondary", width=8, command=lambda: self.set_mode("MAN"))
        self.btn_man.pack(side="left", padx=2)

    def set_mode(self, mode):
        self.mode = mode
        if mode == "AUTO":
            self.btn_auto.configure(bootstyle="success")
            self.btn_man.configure(bootstyle="secondary")
            self.scale_op.configure(state="disabled")
            self.scale_sp.configure(state="normal")
            self.entry_sp.configure(state="normal")
            self.controller.reset()
        else:
            self.btn_auto.configure(bootstyle="secondary")
            self.btn_man.configure(bootstyle="warning")
            self.scale_op.configure(state="normal")
            self.scale_sp.configure(state="disabled")
            self.entry_sp.configure(state="disabled")
            # Initialize manual OP to current OP
            try:
                val = float(self.op_var.get())
                self.manual_op_var.set(val)
            except:
                pass

    def update(self, pv_value):
        # Update PV display
        self.pv_var.set(f"{pv_value:.2f}")
        
        current_sp = self.sp_var.get()
        
        if self.mode == "AUTO":
            op = self.controller.compute(current_sp, pv_value)
            self.op_var.set(f"{op:.1f}")
            return op
        else:
            op = self.manual_op_var.get()
            self.op_var.set(f"{op:.1f}")
            return op
