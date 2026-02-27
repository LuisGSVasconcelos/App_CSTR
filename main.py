import tkinter as tk
import ctypes
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd
from PIL import Image, ImageTk, ImageGrab
from model import CSTR                      # <-- substituído
from pid import PIDController
from components.tank_widget import TankWidget
from components.faceplate import Faceplate

class CSTRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador de Reator CSTR Não Isotérmico - Sala de Controle")
        self.root.geometry("1400x850")       # um pouco maior para acomodar os novos gráficos
        
        # parâmetros de simulação
        self.dt = 0.1                         # 100 ms
        self.sim_time = 0.0
        
        # ========== NOVO MODELO CSTR ==========
        # Parâmetros: área (m²), altura máxima (m), Cv saída,
        # propriedades físicas (rho, Cp) e constantes cinéticas
        self.model = CSTR(
            Area=2.0, H_max=5.0, Cv_out=0.05,
            rho=1000.0, Cp=4184.0,
            A1=1.0e6, E1=50000.0,       # A + B -> C
            A2=1.0e8, E2=60000.0,        # A + C -> D
            deltaH1=-50000.0,             # J/mol, exotérmica
            deltaH2=-70000.0,              # J/mol
            R=8.314
        )
        
        # Controladores (mantidos, mas TC agora manipula potência térmica)
        # Nível: ação reversa (Kp negativo) -> válvula de saída
        self.lc = PIDController(Kp=-50.0, Ki=-5.0, Kd=-0.5, dt=self.dt, output_limits=(0, 100))
        # Temperatura: ação direta (Kp positivo) -> potência de aquecimento/resfriamento
        self.tc = PIDController(Kp=5.0, Ki=0.5, Kd=0.1, dt=self.dt, output_limits=(0, 100))
        
        # Perturbações / entradas
        self.F_in_nominal = 0.02             # vazão de alimentação (m³/s)
        self.T_in_nominal = 30.0              # °C (convertido para K no modelo)
        self.CA_in_nominal = 1000.0            # mol/m³
        self.CB_in_nominal = 1000.0            # mol/m³
        
        # Histórico para gráficos (300 pontos)
        self.history_len = 300
        self.t_data = list(range(self.history_len))
        
        # Nível
        self.level_pv = [0.0] * self.history_len
        self.level_sp = [2.0] * self.history_len
        self.level_op = [0.0] * self.history_len
        
        # Temperatura
        self.temp_pv = [self.T_in_nominal] * self.history_len
        self.temp_sp = [60.0] * self.history_len      # setpoint em °C
        self.temp_op = [0.0] * self.history_len       # sinal do controlador (0-100%)
        
        # Concentrações (apenas PV, sem SP por enquanto)
        self.CA_pv = [0.0] * self.history_len
        self.CC_pv = [0.0] * self.history_len
        
        self.is_paused = False
        
        self.setup_ui()
        self.start_loop()
        
    def setup_ui(self):
        # cabeçalho (adaptado para reator)
        header = ttk.Frame(self.root, bootstyle="danger", padding=10)
        header.pack(fill="x", side="top")
        
        title_frame = ttk.Frame(header, bootstyle="danger")
        title_frame.pack(side="left", padx=20)
        
        # logo (mesmo código, mantido)
        try:
            pil_img = Image.open("UFCG_logo_png.png")
            h_size = 90
            w_size = int((h_size / float(pil_img.size[1])) * float(pil_img.size[0]))
            pil_img = pil_img.resize((w_size, h_size), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(pil_img)
            ttk.Label(title_frame, image=self.logo_img, bootstyle="inverse-danger").pack(side="left", padx=(0, 10))
            ttk.Label(title_frame, text="LARCA", font=("Arial", 16, "bold"), bootstyle="inverse-danger").pack(side="left", padx=(0, 20))
        except Exception as e:
            print(f"Erro ao carregar logo: {e}")
            
        ttk.Label(title_frame, text="REATOR CSTR NÃO ISOTÉRMICO R-101", font=("Arial", 20, "bold"), bootstyle="inverse-danger").pack(side="left", pady=10)
        
        # botões de controle
        btn_frame = ttk.Frame(header, bootstyle="danger")
        btn_frame.pack(side="right", padx=20)
        
        self.btn_pause = ttk.Button(btn_frame, text="PAUSAR", bootstyle="warning", width=10, command=self.toggle_pause)
        self.btn_pause.pack(side="left", padx=5)
        
        btn_reset = ttk.Button(btn_frame, text="RESETAR", bootstyle="secondary", width=10, command=self.reset_sim)
        btn_reset.pack(side="left", padx=5)
        
        btn_save = ttk.Button(btn_frame, text="SALVAR DADOS", bootstyle="dark", width=15, command=self.save_history_csv)
        btn_save.pack(side="left", padx=5)

        btn_screenshot = ttk.Button(btn_frame, text="CAPTURA", bootstyle="info", width=10, command=self.take_screenshot)
        btn_screenshot.pack(side="left", padx=5)
        
        # rodapé
        footer = ttk.Frame(self.root, bootstyle="secondary", padding=5)
        footer.pack(fill="x", side="bottom")
        ttk.Label(footer, text="Autor: Luis Vasconcelos (adaptado) | Powered by Antigravity & Gemini 3 Pro", font=("Arial", 10), bootstyle="inverse-secondary").pack(side="right", padx=20)
        
        # notebook com abas
        self.notebook = ttk.Notebook(self.root, bootstyle="danger")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_operation = ttk.Frame(self.notebook)
        self.tab_tuning = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_operation, text="  Operação  ")
        self.notebook.add(self.tab_tuning, text="  Configurações  ")
        
        self.setup_operation_tab(self.tab_operation)
        self.setup_tuning_tab(self.tab_tuning)
        
    def setup_operation_tab(self, parent):
        paned = ttk.Panedwindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Painel esquerdo: tanque e entradas
        left_panel = ttk.Frame(paned, padding=10)
        paned.add(left_panel, weight=1)
        
        # Widget do tanque (representa o reator)
        self.tank_display = TankWidget(left_panel, width=200, height=350, max_level=5.0)
        self.tank_display.pack(pady=20)
        
        # Informações do processo
        info_frame = ttk.Frame(left_panel)
        info_frame.pack(fill="x", padx=20)
        
        # Vazão de entrada
        self.lbl_dist_flow = ttk.Label(info_frame, text=f"Vazão Entrada: {self.F_in_nominal:.3f} m³/s", font=("Arial", 10))
        self.lbl_dist_flow.pack(anchor="w")
        ttk.Label(info_frame, text="Ajustar Vazão Entrada:").pack(anchor="w", pady=5)
        self.scale_dist_flow = ttk.Scale(info_frame, from_=0.0, to=0.025, orient='horizontal',
                                         command=self.updated_dist_flow, bootstyle="info")
        self.scale_dist_flow.set(self.F_in_nominal)
        self.scale_dist_flow.pack(fill="x")
        
        # Temperatura de entrada
        ttk.Label(info_frame, text="Ajustar Temp. Entrada (°C):").pack(anchor="w", pady=(10,0))
        self.lbl_dist_temp = ttk.Label(info_frame, text=f"Temp. Entrada: {self.T_in_nominal:.1f} °C", font=("Arial", 10))
        self.lbl_dist_temp.pack(anchor="w")
        self.scale_dist_temp = ttk.Scale(info_frame, from_=10.0, to=80.0, orient="horizontal",
                                         command=self.updated_dist_temp, bootstyle="info")
        self.scale_dist_temp.set(self.T_in_nominal)
        self.scale_dist_temp.pack(fill="x")
        
        # Concentração de A na entrada
        ttk.Label(info_frame, text="Ajustar CA entrada (mol/m³):").pack(anchor="w", pady=(10,0))
        self.lbl_dist_CA = ttk.Label(info_frame, text=f"CA_in: {self.CA_in_nominal:.1f} mol/m³", font=("Arial", 10))
        self.lbl_dist_CA.pack(anchor="w")
        self.scale_dist_CA = ttk.Scale(info_frame, from_=0.0, to=2000.0, orient="horizontal",
                                       command=self.updated_dist_CA, bootstyle="info")
        self.scale_dist_CA.set(self.CA_in_nominal)
        self.scale_dist_CA.pack(fill="x")
        
        # Concentração de B na entrada
        ttk.Label(info_frame, text="Ajustar CB entrada (mol/m³):").pack(anchor="w", pady=(10,0))
        self.lbl_dist_CB = ttk.Label(info_frame, text=f"CB_in: {self.CB_in_nominal:.1f} mol/m³", font=("Arial", 10))
        self.lbl_dist_CB.pack(anchor="w")
        self.scale_dist_CB = ttk.Scale(info_frame, from_=0.0, to=2000.0, orient="horizontal",
                                       command=self.updated_dist_CB, bootstyle="info")
        self.scale_dist_CB.set(self.CB_in_nominal)
        self.scale_dist_CB.pack(fill="x")
        
        # Leituras digitais de concentração no reator
        self.lbl_CA_reactor = ttk.Label(info_frame, text="CA = 0.0 mol/m³", font=("Arial", 10))
        self.lbl_CA_reactor.pack(anchor="w", pady=(10,0))
        self.lbl_CB_reactor = ttk.Label(info_frame, text="CB = 0.0 mol/m³", font=("Arial", 10))
        self.lbl_CB_reactor.pack(anchor="w")
        self.lbl_CC_reactor = ttk.Label(info_frame, text="CC = 0.0 mol/m³", font=("Arial", 10))
        self.lbl_CC_reactor.pack(anchor="w")
        self.lbl_CD_reactor = ttk.Label(info_frame, text="CD = 0.0 mol/m³", font=("Arial", 10))
        self.lbl_CD_reactor.pack(anchor="w")
        
        # Painel direito: faceplates e gráficos
        right_panel = ttk.Frame(paned, padding=10)
        paned.add(right_panel, weight=2)
        
        # Faceplates
        faceplate_frame = ttk.Frame(right_panel)
        faceplate_frame.pack(fill="x", pady=5)
        
        self.fp_level = Faceplate(faceplate_frame, "LIC-101 (Nível)", self.lc, min_sp=0, max_sp=5.0, unit="m", resolution=0.01)
        self.fp_level.sp_var.set(2.0)
        self.fp_level.pack(side="left", padx=10, fill="y")
        
        self.fp_temp = Faceplate(faceplate_frame, "TIC-101 (Temperatura)", self.tc, min_sp=20, max_sp=150, unit="°C", resolution=0.1)
        self.fp_temp.sp_var.set(60.0)
        self.fp_temp.pack(side="left", padx=10, fill="y")
        
        # Gráficos (agora 2x3)
        chart_frame = ttk.Frame(right_panel)
        chart_frame.pack(fill="both", expand=True, pady=10, padx=10)
        
        plt.style.use('dark_background')
        plt.rcParams.update({
            "axes.facecolor": "#34495e",
            "figure.facecolor": "#2b3e50",
            "grid.color": "#bdc3c7",
            "grid.linestyle": "--",
            "grid.linewidth": 0.5,
            "grid.alpha": 0.2
        })
        
        self.fig, axs = plt.subplots(2, 3, figsize=(10, 5), dpi=100)
        self.fig.patch.set_facecolor('#2b3e50')
        
        # Linha superior
        self.ax_level = axs[0, 0]
        self.ax_temp = axs[0, 1]
        self.ax_CA = axs[0, 2]
        
        # Linha inferior
        self.ax_level_op = axs[1, 0]
        self.ax_temp_op = axs[1, 1]
        self.ax_CC = axs[1, 2]
        
        # Configuração de cada eixo
        # Nível PV/SP
        self.line_level_pv, = self.ax_level.plot(self.t_data, self.level_pv, 'g-', label='PV')
        self.line_level_sp, = self.ax_level.plot(self.t_data, self.level_sp, 'w--', label='SP')
        self.ax_level.set_title("Nível (m)")
        self.ax_level.set_ylim(0, 5.5)
        self.ax_level.set_xlim(0, self.history_len)
        self.ax_level.legend(loc='upper right', fontsize='small')
        self.ax_level.grid(True)
        
        # Temperatura PV/SP
        self.line_temp_pv, = self.ax_temp.plot(self.t_data, self.temp_pv, 'r-', label='PV')
        self.line_temp_sp, = self.ax_temp.plot(self.t_data, self.temp_sp, 'w--', label='SP')
        self.ax_temp.set_title("Temperatura (°C)")
        self.ax_temp.set_ylim(0, 150)
        self.ax_temp.set_xlim(0, self.history_len)
        self.ax_temp.legend(loc='upper right', fontsize='small')
        self.ax_temp.grid(True)
        
        # Concentração de A
        self.line_CA, = self.ax_CA.plot(self.t_data, self.CA_pv, 'b-', label='CA')
        self.ax_CA.set_title("Concentração de A (mol/m³)")
        self.ax_CA.set_ylim(0, 2000)
        self.ax_CA.set_xlim(0, self.history_len)
        self.ax_CA.grid(True)
        
        # Nível OP (válvula de saída)
        self.line_level_op, = self.ax_level_op.plot(self.t_data, self.level_op, 'y-', label='OP')
        self.ax_level_op.set_title("Válvula Saída (%)")
        self.ax_level_op.set_ylim(0, 105)
        self.ax_level_op.set_xlim(0, self.history_len)
        self.ax_level_op.grid(True)
        
        # Temperatura OP (potência térmica)
        self.line_temp_op, = self.ax_temp_op.plot(self.t_data, self.temp_op, 'y-', label='OP')
        self.ax_temp_op.set_title("Potência Térmica (%)")
        self.ax_temp_op.set_ylim(0, 105)
        self.ax_temp_op.set_xlim(0, self.history_len)
        self.ax_temp_op.grid(True)
        
        # Concentração de C
        self.line_CC, = self.ax_CC.plot(self.t_data, self.CC_pv, 'm-', label='CC')
        self.ax_CC.set_title("Concentração de C (mol/m³)")
        self.ax_CC.set_ylim(0, 2000)
        self.ax_CC.set_xlim(0, self.history_len)
        self.ax_CC.grid(True)
        
        self.fig.tight_layout()
        self.plt_canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.plt_canvas.get_tk_widget().pack(fill="both", expand=True)
        
    def setup_tuning_tab(self, parent):
        container = ttk.Frame(parent, padding=20)
        container.pack(fill="both", expand=True)
        
        ttk.Label(container, text="Ajuste de Parâmetros", font=("Arial", 16, "bold"), bootstyle="danger").pack(pady=(0, 20))
        
        # Controlador de nível
        frame_lc = ttk.LabelFrame(container, text="Controlador de Nível (LIC-101)")
        frame_lc.pack(fill="x", pady=10)
        
        # Controlador de temperatura
        frame_tc = ttk.LabelFrame(container, text="Controlador de Temperatura (TIC-101)")
        frame_tc.pack(fill="x", pady=10)
        
        # Parâmetros do processo (incluindo cinética)
        frame_process = ttk.LabelFrame(container, text="Parâmetros do Reator e Cinética")
        frame_process.pack(fill="x", pady=10)
        
        # LC
        self.lc_kp_var = tk.DoubleVar(value=self.lc.Kp)
        self.lc_ki_var = tk.DoubleVar(value=self.lc.Ki)
        self.lc_kd_var = tk.DoubleVar(value=self.lc.Kd)
        self.create_tuning_row(frame_lc, "Kp:", self.lc_kp_var, 0)
        self.create_tuning_row(frame_lc, "Ki:", self.lc_ki_var, 1)
        self.create_tuning_row(frame_lc, "Kd:", self.lc_kd_var, 2)
        
        # TC
        self.tc_kp_var = tk.DoubleVar(value=self.tc.Kp)
        self.tc_ki_var = tk.DoubleVar(value=self.tc.Ki)
        self.tc_kd_var = tk.DoubleVar(value=self.tc.Kd)
        self.create_tuning_row(frame_tc, "Kp:", self.tc_kp_var, 0)
        self.create_tuning_row(frame_tc, "Ki:", self.tc_ki_var, 1)
        self.create_tuning_row(frame_tc, "Kd:", self.tc_kd_var, 2)
        
        # Processo
        self.cv_var = tk.DoubleVar(value=self.model.Cv_out)
        self.area_var = tk.DoubleVar(value=self.model.Area)
        self.A1_var = tk.DoubleVar(value=self.model.A1)
        self.E1_var = tk.DoubleVar(value=self.model.E1)
        self.A2_var = tk.DoubleVar(value=self.model.A2)
        self.E2_var = tk.DoubleVar(value=self.model.E2)
        self.dH1_var = tk.DoubleVar(value=self.model.deltaH1)
        self.dH2_var = tk.DoubleVar(value=self.model.deltaH2)
        
        self.create_tuning_row(frame_process, "Cv Saída:", self.cv_var, 0)
        self.create_tuning_row(frame_process, "Área (m²):", self.area_var, 1)
        self.create_tuning_row(frame_process, "A1 (r1):", self.A1_var, 2)
        self.create_tuning_row(frame_process, "E1 (J/mol):", self.E1_var, 3)
        self.create_tuning_row(frame_process, "A2 (r2):", self.A2_var, 4)
        self.create_tuning_row(frame_process, "E2 (J/mol):", self.E2_var, 5)
        self.create_tuning_row(frame_process, "ΔH1 (J/mol):", self.dH1_var, 6)
        self.create_tuning_row(frame_process, "ΔH2 (J/mol):", self.dH2_var, 7)
        
        btn_apply = ttk.Button(container, text="Aplicar Parâmetros", bootstyle="success", command=self.apply_tunings)
        btn_apply.pack(pady=20)
        
    def create_tuning_row(self, parent, label_text, var, row):
        ttk.Label(parent, text=label_text, width=15, anchor="e").grid(row=row, column=0, padx=5, pady=5)
        ttk.Entry(parent, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=5)
        
    def apply_tunings(self):
        try:
            self.lc.set_tunings(self.lc_kp_var.get(), self.lc_ki_var.get(), self.lc_kd_var.get())
            self.tc.set_tunings(self.tc_kp_var.get(), self.tc_ki_var.get(), self.tc_kd_var.get())
            
            self.model.Cv_out = self.cv_var.get()
            self.model.Area = self.area_var.get()
            self.model.A1 = self.A1_var.get()
            self.model.E1 = self.E1_var.get()
            self.model.A2 = self.A2_var.get()
            self.model.E2 = self.E2_var.get()
            self.model.deltaH1 = self.dH1_var.get()
            self.model.deltaH2 = self.dH2_var.get()
            
            print("Parâmetros atualizados!")
        except Exception as e:
            print(f"Erro: {e}")
    
    # Métodos para atualização das perturbações
    def updated_dist_flow(self, val):
        self.F_in_nominal = float(val)
        self.lbl_dist_flow.config(text=f"Vazão Entrada: {self.F_in_nominal:.3f} m³/s")
        
    def updated_dist_temp(self, val):
        self.T_in_nominal = float(val)
        self.lbl_dist_temp.config(text=f"Temp. Entrada: {self.T_in_nominal:.1f} °C")
        
    def updated_dist_CA(self, val):
        self.CA_in_nominal = float(val)
        self.lbl_dist_CA.config(text=f"CA_in: {self.CA_in_nominal:.1f} mol/m³")
        
    def updated_dist_CB(self, val):
        self.CB_in_nominal = float(val)
        self.lbl_dist_CB.config(text=f"CB_in: {self.CB_in_nominal:.1f} mol/m³")
        
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.btn_pause.configure(text="RESUMIR" if self.is_paused else "PAUSAR",
                                 bootstyle="success" if self.is_paused else "warning")
    
    def reset_sim(self):
        # Reinicia o modelo com os parâmetros atuais (usando os valores das variáveis de entrada)
        self.model = CSTR(
            Area=self.area_var.get() if hasattr(self, 'area_var') else 2.0,
            H_max=5.0,
            Cv_out=self.cv_var.get() if hasattr(self, 'cv_var') else 0.05,
            A1=self.A1_var.get() if hasattr(self, 'A1_var') else 1e6,
            E1=self.E1_var.get() if hasattr(self, 'E1_var') else 50000,
            A2=self.A2_var.get() if hasattr(self, 'A2_var') else 1e8,
            E2=self.E2_var.get() if hasattr(self, 'E2_var') else 60000,
            deltaH1=self.dH1_var.get() if hasattr(self, 'dH1_var') else -50000,
            deltaH2=self.dH2_var.get() if hasattr(self, 'dH2_var') else -70000
        )
        self.lc.reset()
        self.tc.reset()
        self.sim_time = 0.0
        
        # Zera históricos
        self.level_pv = [0.0] * self.history_len
        self.level_sp = [self.fp_level.sp_var.get()] * self.history_len
        self.level_op = [0.0] * self.history_len
        
        self.temp_pv = [self.T_in_nominal] * self.history_len
        self.temp_sp = [self.fp_temp.sp_var.get()] * self.history_len
        self.temp_op = [0.0] * self.history_len
        
        self.CA_pv = [0.0] * self.history_len
        self.CC_pv = [0.0] * self.history_len
        
        self.plt_canvas.draw()
        self.tank_display.update_level(0, self.T_in_nominal)
        
    def save_history_csv(self):
        try:
            data = {
                'Time_s': self.t_data,
                'Level_PV_m': self.level_pv,
                'Level_SP_m': self.level_sp,
                'Level_OP_pct': self.level_op,
                'Temp_PV_C': self.temp_pv,
                'Temp_SP_C': self.temp_sp,
                'Temp_OP_pct': self.temp_op,
                'CA_PV_mol/m3': self.CA_pv,
                'CC_PV_mol/m3': self.CC_pv
            }
            df = pd.DataFrame(data)
            filename = filedialog.asksaveasfilename(
                title="Salvar Histórico", defaultextension=".csv",
                filetypes=[("CSV", "*.csv")], initialfile="historico_reator.csv"
            )
            if filename:
                df.to_csv(filename, index=False)
                tk.messagebox.showinfo("Sucesso", f"Dados salvos em:\n{filename}")
        except Exception as e:
            tk.messagebox.showerror("Erro", f"Falha ao salvar:\n{e}")

    def take_screenshot(self):
        try:
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            
            filename = filedialog.asksaveasfilename(
                title="Salvar Captura", defaultextension=".png",
                filetypes=[("PNG", "*.png")], initialfile="captura_reator.png"
            )
            
            if filename:
                img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
                img.save(filename)
                tk.messagebox.showinfo("Sucesso", f"Salvo em:\n{filename}")
        except Exception as e:
            print(f"Screenshot falhou: {e}")
    
    def start_loop(self):
        self.update()
        
    def update(self):
        if self.is_paused:
            self.root.after(100, self.update)
            return
        
        # Obtém variáveis do modelo
        current_level = self.model.Volume / self.model.Area
        current_temp_C = self.model.Temperature - 273.15   # modelo usa K, exibimos °C
        
        # Controlador de nível -> válvula de saída
        op_level = self.fp_level.update(current_level)
        
        # Controlador de temperatura -> sinal 0-100% que será convertido em potência térmica
        op_temp = self.fp_temp.update(current_temp_C)
        
        # Mapeia op_temp (0-100%) para potência (W). Ex.: -100 kW a +100 kW
        # 0% -> -100 kW (resfriamento máximo), 50% -> 0, 100% -> +100 kW (aquecimento máximo)
        Q_heating = (op_temp - 50.0) * 2000.0   # 2000 W por %? Ajuste: (0-100) -> -100000 a +100000 W
        # Mais intuitivo: -100kW a +100kW
        Q_heating = (op_temp - 50.0) * 2000.0   # 2000 W por %? Na verdade queremos 2000 W por %? 100% * 2000 = 200kW, muito. Vamos ajustar:
        # Para -100kW a +100kW, o intervalo é 200kW, então cada % vale 2000 W. Correto: 100% * 2000 = 200kW, então -100 a +100.
        # Vamos usar isso.
        
        # Passo de integração do modelo
        # Converte T_in de °C para K
        T_in_K = self.T_in_nominal + 273.15
        
        level, temp_K, F_out, CA, CB, CC, CD = self.model.step(
            dt=self.dt,
            F_in=self.F_in_nominal,
            T_in=T_in_K,
            CA_in=self.CA_in_nominal,
            CB_in=self.CB_in_nominal,
            Valve_Open_Pct=op_level,
            Q_heating=Q_heating
        )
        
        temp_C = temp_K - 273.15
        
        # Atualiza tempo e display do tanque
        self.sim_time += self.dt
        self.tank_display.update_level(level, temp_C)
        
        # Atualiza labels de concentração
        self.lbl_CA_reactor.config(text=f"CA = {CA:.1f} mol/m³")
        self.lbl_CB_reactor.config(text=f"CB = {CB:.1f} mol/m³")
        self.lbl_CC_reactor.config(text=f"CC = {CC:.1f} mol/m³")
        self.lbl_CD_reactor.config(text=f"CD = {CD:.1f} mol/m³")
        
        # Atualiza históricos
        self.level_pv.append(level); self.level_pv.pop(0)
        self.level_sp.append(self.fp_level.sp_var.get()); self.level_sp.pop(0)
        self.level_op.append(op_level); self.level_op.pop(0)
        
        self.temp_pv.append(temp_C); self.temp_pv.pop(0)
        self.temp_sp.append(self.fp_temp.sp_var.get()); self.temp_sp.pop(0)
        self.temp_op.append(op_temp); self.temp_op.pop(0)
        
        self.CA_pv.append(CA); self.CA_pv.pop(0)
        self.CC_pv.append(CC); self.CC_pv.pop(0)
        
        # Atualiza gráficos a cada 5 passos (para não sobrecarregar)
        if int(self.sim_time * 10) % 5 == 0:
            self.line_level_pv.set_ydata(self.level_pv)
            self.line_level_sp.set_ydata(self.level_sp)
            self.line_level_op.set_ydata(self.level_op)
            
            self.line_temp_pv.set_ydata(self.temp_pv)
            self.line_temp_sp.set_ydata(self.temp_sp)
            self.line_temp_op.set_ydata(self.temp_op)
            
            self.line_CA.set_ydata(self.CA_pv)
            self.line_CC.set_ydata(self.CC_pv)
            
            self.plt_canvas.draw_idle()
        
        self.root.after(int(self.dt * 1000), self.update)

# ==========================
# Modelo CSTR (deve estar em model.py ou incluso aqui)
# ==========================
class CSTR:
    def __init__(self, Area=2.0, H_max=5.0, Cv_out=0.05,
                 rho=1000.0, Cp=4184.0,
                 A1=1e6, E1=50000.0,
                 A2=1e8, E2=60000.0,
                 deltaH1=-50000.0, deltaH2=-70000.0,
                 R=8.314):
        self.Area = Area
        self.H_max = H_max
        self.Cv_out = Cv_out
        self.rho = rho
        self.Cp = Cp
        self.A1 = A1
        self.E1 = E1
        self.A2 = A2
        self.E2 = E2
        self.deltaH1 = deltaH1
        self.deltaH2 = deltaH2
        self.R = R
        
        # Estados iniciais
        self.Volume = 0.0
        self.Temperature = 300.0      # K
        self.CA = 0.0
        self.CB = 0.0
        self.CC = 0.0
        self.CD = 0.0
        
    def step(self, dt, F_in, T_in, CA_in, CB_in, Valve_Open_Pct, Q_heating):
        # Válvula de saída (0-100%)
        valve_frac = Valve_Open_Pct / 100.0
        level = self.Volume / self.Area if self.Area > 0 else 0
        F_out = self.Cv_out * valve_frac * np.sqrt(max(level, 0))
        
        # Velocidades específicas (Arrhenius)
        T = self.Temperature
        k1 = self.A1 * np.exp(-self.E1 / (self.R * T))
        k2 = self.A2 * np.exp(-self.E2 / (self.R * T))
        
        # Taxas de reação
        r1 = k1 * self.CA * self.CB
        r2 = k2 * self.CA * self.CC
        
        V = self.Volume
        if V > 1e-6:
            # Balanços de massa
            dCA_dt = (F_in * CA_in - F_out * self.CA) / V - r1 - r2
            dCB_dt = (F_in * CB_in - F_out * self.CB) / V - r1
            dCC_dt = (-F_out * self.CC) / V + r1 - r2
            dCD_dt = (-F_out * self.CD) / V + r2
            
            # Balanço de energia
            Q_rxn = (-self.deltaH1) * r1 * V + (-self.deltaH2) * r2 * V
            Q_inflow = F_in * self.rho * self.Cp * (T_in - T)
            Q_total = Q_inflow + Q_rxn + Q_heating
            dT_dt = Q_total / (self.rho * self.Cp * V)
        else:
            dCA_dt = dCB_dt = dCC_dt = dCD_dt = dT_dt = 0
        
        # Balanço de volume
        dV_dt = F_in - F_out
        
        # Integração Euler
        self.Volume += dV_dt * dt
        self.Temperature += dT_dt * dt
        self.CA += dCA_dt * dt
        self.CB += dCB_dt * dt
        self.CC += dCC_dt * dt
        self.CD += dCD_dt * dt
        
        # Garantir não negatividade
        self.Volume = max(self.Volume, 0)
        self.CA = max(self.CA, 0)
        self.CB = max(self.CB, 0)
        self.CC = max(self.CC, 0)
        self.CD = max(self.CD, 0)
        
        level = self.Volume / self.Area if self.Area > 0 else 0
        return level, self.Temperature, F_out, self.CA, self.CB, self.CC, self.CD

if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    root = ttk.Window(themename="superhero")
    app = CSTRApp(root)
    root.mainloop()