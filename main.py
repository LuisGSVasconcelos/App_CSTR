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

# ============================================================
# 1. MODELO CSTR PARA ETOXILAÇÃO (CINÉTICA COMPLEXA)
# ============================================================

class CSTR:
    def __init__(self, Area=3.75, H_max=4.0, Cv_out=0.03,
                 rho=900.0, Cp=2500.0,
                 A1=5.0e6, E1=75000.0,  # Valores ajustados para estabilidade
                 A2=1.0e8, E2=90000.0,
                 deltaH1=-2.0*92000.0, deltaH2=-2.0*110000.0,
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
        
        
        
        # Reset oficial para estado estável
        self.reset_to_start()

    def reset_to_start(self):
        self.Volume = 0.5              # Começa com volume seguro
        self.Temperature = 310.15      # 37°C
        self.CA = 1000.0               # Álcool
        self.CB = 50.0                 # EO baixo (evita explosão inicial)
        self.CC = 0.0
        self.CD = 0.0

        #--- NOVAS VARIÁVEIS DO PLACAR ---
        self.accumulated_C = 0.0  # Mols totais de C exportados
        self.accumulated_D = 0.0  # Mols totais de D exportados

    def step(self, dt, F_in, T_in, CA_in, CB_in, Valve_Open_Pct, Q_cooling_signal):
        # Proteção contra passo de tempo muito grande
        sub_dt = dt / 5.0 
        for _ in range(5):
            valve_frac = Valve_Open_Pct / 100.0
            level = self.Volume / self.Area
            F_out = self.Cv_out * valve_frac * np.sqrt(max(level, 0.001))
            
            T = self.Temperature
            k1 = self.A1 * np.exp(-self.E1 / (self.R * T))
            k2 = self.A2 * np.exp(-self.E2 / (self.R * T))
            
            # Taxas moderadas para evitar instabilidade numérica
            r1 = k1 * self.CA * self.CB
            r2 = k2 * self.CC * self.CA
            
            V = max(self.Volume, 0.1)
            
            # Balanços de Massa Corrigidos (Válidos para Volume Variável e Constante)
            dCA_dt = (F_in * (CA_in - self.CA)) / V - r1 - r2
            dCB_dt = (F_in * (CB_in - self.CB)) / V - 2*r1
            dCC_dt = (F_in * (0.0 - self.CC)) / V + r1 - r2
            dCD_dt = (F_in * (0.0 - self.CD)) / V + r2
            
            # Controle Split-Range (Faixa Dividida)
            # Q_thermal_signal (Antigo Q_cooling_signal) varia de 0 a 100
            if Q_cooling_signal < 50.0:
                # Ação de RESFRIAMENTO (0 a 50%) -> Água Fria
                # op = 0 -> 1.0 (100% válvula aberta), op = 50 -> 0.0 (fechada)
                frac_cooling = (50.0 - Q_cooling_signal) / 50.0
                Q_thermal = frac_cooling * (-4000000.0) # Até -4 MW de resfriamento
            else:
                # Ação de AQUECIMENTO (50 a 100%) -> Vapor
                # op = 50 -> 0.0 (fechada), op = 100 -> 1.0 (100% válvula aberta)
                frac_heating = (Q_cooling_signal - 50.0) / 50.0
                Q_thermal = frac_heating * (2500000.0) # Até +2.5 MW de aquecimento com vapor

            # Usa o Q_thermal no balanço em vez do antigo Q_removido
            Q_rxn = (self.deltaH1 * r1 * V) + (self.deltaH2 * r2 * V)
            Q_inflow = F_in * self.rho * self.Cp * (T_in - T)
            
            dT_dt = (Q_inflow - Q_rxn + Q_thermal) / (self.rho * self.Cp * V)
            
            self.Volume = np.clip(self.Volume + (F_in - F_out) * sub_dt, 0.1, self.Area * self.H_max)
            self.Temperature += dT_dt * sub_dt
            self.CA = max(self.CA + dCA_dt * sub_dt, 0)
            self.CB = max(self.CB + dCB_dt * sub_dt, 0)            
            self.CC = max(self.CC + dCC_dt * sub_dt, 0)
            self.CD = max(self.CD + dCD_dt * sub_dt, 0)

            # Garante que as variáveis existam (trava de segurança)
            if not hasattr(self, 'accumulated_C'):
                self.accumulated_C = 0.0
                self.accumulated_D = 0.0
            
            # --- INTEGRAÇÃO DO PLACAR (Gamificação) ---
            # Multiplica a vazão de saída (m³/s) pela concentração (mol/m³) e pelo tempo (s)
            self.accumulated_C += F_out * self.CC * sub_dt
            self.accumulated_D += F_out * self.CD * sub_dt
            
        return self.Volume/self.Area, self.Temperature, F_out, self.CA, self.CB, self.CC, self.CD

# ============================================================
# 2. INTERFACE GRÁFICA (SALA DE CONTROLE)
# ============================================================
class CSTRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador Etoxilação R-101 - Advanced Process Control")
        self.root.geometry("1400x850")

        # --- ADICIONE ESTAS DUAS LINHAS ---
        self.is_running = True
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Parâmetros de Simulação
        self.dt = 0.1 
        self.sim_time = 0.0
        
        # Importação de componentes externos
        from pid import PIDController
        from components.tank_widget import TankWidget
        from components.faceplate import Faceplate

        # Inicialização do Modelo
        self.model = CSTR()

        # Controladores (Mantidos com ação reversa/direta correta)
        self.lc = PIDController(Kp=-60.0, Ki=-8.0, Kd=-1.0, dt=self.dt, output_limits=(0, 100))
        self.tc = PIDController(Kp=8.0, Ki=1.2, Kd=0.2, dt=self.dt, output_limits=(0, 100))

        # Variáveis Nominais de Operação
        self.F_in_nominal = 0.0012  # m³/s (~4.3 m³/h)
        self.T_in_nominal = 35.0    # °C
        self.CA_in_nominal = 1000.0 # mol/m³
        self.CB_in_nominal = 2000.0 # mol/m³

        # Histórico para Gráficos
        # Aumentamos o armazenamento total para manter um histórico longo
        self.max_history = 5000 
        self.current_view_len = 300 # Janela visual inicial
        self.t_data = list(range(self.max_history))
        self.level_pv = [2.66] * self.max_history
        self.level_sp = [2.66] * self.max_history
        self.level_op = [0.0] * self.max_history
        self.temp_pv = [150.0] * self.max_history
        self.temp_sp = [150.0] * self.max_history
        self.temp_op = [0.0] * self.max_history
        self.CA_pv = [1000.0] * self.max_history
        self.CC_pv = [0.0] * self.max_history

        self.is_paused = False
        self.setup_ui()
        self.start_loop()

    def update_history_window(self, val):
        self.current_view_len = int(float(val))
        self.lbl_history_val.config(text=f"{self.current_view_len} s")
        
        # Trava de segurança: Se os gráficos ainda não foram criados, pare por aqui.
        if not hasattr(self, 'ax_level'):
            return
        
        # Atualiza o limite do eixo X em todos os gráficos
        new_limit = self.current_view_len
        self.ax_level.set_xlim(0, new_limit)
        self.ax_temp.set_xlim(0, new_limit)
        self.ax_CA.set_xlim(0, new_limit)
        self.ax_level_op.set_xlim(0, new_limit)
        self.ax_temp_op.set_xlim(0, new_limit)
        self.ax_CC.set_xlim(0, new_limit)
        self.canvas.draw_idle()   

    def setup_ui(self):
        # 1. Frame de Cabeçalho
        header = ttk.Frame(self.root, bootstyle="danger", padding=10)
        header.pack(fill="x", side="top")
        
        title_frame = ttk.Frame(header, bootstyle="danger")
        title_frame.pack(side="left", padx=20)
        
        # Logo UFCG e LARCA
        try:
            pil_img = Image.open("UFCG_logo_png.png")
            h_size = 60
            w_size = int((h_size / float(pil_img.size[1])) * float(pil_img.size[0]))
            pil_img = pil_img.resize((w_size, h_size), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(pil_img)
            ttk.Label(title_frame, image=self.logo_img, bootstyle="inverse-danger").pack(side="left", padx=(0, 10))
            ttk.Label(title_frame, text="LARCA", font=("Arial", 16, "bold"), bootstyle="inverse-danger").pack(side="left", padx=(0, 20))
        except Exception as e:
            print(f"Aviso: Logo não encontrada. {e}")
            
        ttk.Label(title_frame, text="UNIDADE DE ETOXILAÇÃO R-101", font=("Arial", 22, "bold"), bootstyle="inverse-danger").pack(side="left")
        
        # 2. Botões de Operação
        btn_frame = ttk.Frame(header, bootstyle="danger")
        btn_frame.pack(side="right", padx=20)
        
        self.btn_pause = ttk.Button(btn_frame, text="PAUSAR", bootstyle="success", width=10, command=self.toggle_pause)
        self.btn_pause.pack(side="left", padx=5)
        
        ttk.Button(btn_frame, text="RESETAR", bootstyle="secondary", width=10, command=self.reset_sim).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="SALVAR DADOS", bootstyle="dark", width=15, command=self.save_history_csv).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="CAPTURA", bootstyle="info", width=10, command=self.take_screenshot).pack(side="left", padx=5)

        # 3. Rodapé (Footer) com Créditos
        footer = ttk.Frame(self.root, bootstyle="secondary", padding=5)
        footer.pack(fill="x", side="bottom")
        ttk.Label(footer, text="Autor: Luis Vasconcelos | Laboratório LARCA - UFCG | Process Control", font=("Arial", 10), bootstyle="inverse-secondary").pack(side="right", padx=20)

        # 4. Abas de Navegação (Notebook) - AS ABAS QUE FALTARAM VOLTAM AQUI!
        self.notebook = ttk.Notebook(self.root, bootstyle="danger")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_op = ttk.Frame(self.notebook)
        self.tab_config = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_op, text=" Painel de Operação ")
        self.notebook.add(self.tab_config, text=" Parâmetros e Sintonia ")
        
        # 5. Chama os métodos que constroem os gráficos e as configurações
        self.setup_operation_tab()
        self.setup_tuning_tab()

    def setup_operation_tab(self):
        paned = ttk.Panedwindow(self.tab_op, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # ====== PAINEL ESQUERDO (Tanque e Controles) ======
        left_panel = ttk.Frame(paned, padding=10)
        paned.add(left_panel, weight=1)

        # 1. O Tanque no topo (altura ajustada)
        from components.tank_widget import TankWidget
        self.tank_display = TankWidget(left_panel, width=220, height=300, max_level=4.0)
        self.tank_display.pack(pady=(0, 10))

        # 2. Sliders (Empilhados justos)
        self.lbl_flow_val = ttk.Label(left_panel, text=f"Vazão de Carga: {self.F_in_nominal:.4f} m³/s", font=("Arial", 10))
        self.lbl_flow_val.pack(anchor="w")
        self.sc_flow = ttk.Scale(left_panel, from_=0.0002, to=0.02, command=self.update_params, bootstyle="info")
        self.sc_flow.set(self.F_in_nominal)
        self.sc_flow.pack(fill="x", pady=(2, 10))

        ttk.Label(left_panel, text="Janela Histórico (s):", font=("Arial", 10, "bold")).pack(anchor="w")
        self.lbl_history_val = ttk.Label(left_panel, text="300 s")
        self.lbl_history_val.pack(anchor="w")
        self.sc_history = ttk.Scale(left_panel, from_=50, to=self.max_history, command=self.update_history_window, bootstyle="warning")
        self.sc_history.set(300)
        self.sc_history.pack(fill="x", pady=(2, 10))

        # 3. Monitores de Concentração
        ttk.Label(left_panel, text="Concentração no Reator:", font=("Arial", 9, "bold")).pack(anchor="w")
        self.lbl_ca = ttk.Label(left_panel, text="CA (Álcool): 0.0", font=("Arial", 9))
        self.lbl_ca.pack(anchor="w")
        self.lbl_cb = ttk.Label(left_panel, text="CB (Óxido Etileno): 0.0", font=("Arial", 9))
        self.lbl_cb.pack(anchor="w")
        self.lbl_cc = ttk.Label(left_panel, text="CC (Surfactante): 0.0", font=("Arial", 9))
        self.lbl_cc.pack(anchor="w")
        self.lbl_cd = ttk.Label(left_panel, text="CD (Subproduto): 0.0", font=("Arial", 9))
        self.lbl_cd.pack(anchor="w")

        # 4. Placar Final
        score_frame = ttk.LabelFrame(left_panel, text="🏆 Placar Final")
        score_frame.pack(fill="x", pady=(10, 0), ipadx=5, ipady=5)

        # ---> ADICIONE ESTAS DUAS LINHAS AQUI <---
        self.lbl_timer = ttk.Label(score_frame, text="⏱️ Tempo: 00:00:00", font=("Arial", 12, "bold"), foreground="#f39c12") # Laranja/Dourado
        self.lbl_timer.pack(anchor="w", pady=(0, 5))

        self.lbl_score_c = ttk.Label(score_frame, text="C: 0.0 mol", font=("Arial", 11, "bold"), foreground="#2ecc71")
        self.lbl_score_c.pack(anchor="w")
        self.lbl_score_d = ttk.Label(score_frame, text="D: 0.0 mol", font=("Arial", 11, "bold"), foreground="#e74c3c")
        self.lbl_score_d.pack(anchor="w")
        self.lbl_score_ratio = ttk.Label(score_frame, text="Razão: N/A", font=("Arial", 10, "italic"))
        self.lbl_score_ratio.pack(anchor="w")

        # ====== PAINEL DIREITO (Faceplates e Gráficos) ======
        # (O código continua normal daqui pra baixo)

        # ====== PAINEL DIREITO (Faceplates e Gráficos) ======
        # (Daqui para baixo, o seu código continua normal, criando o right_panel...)

        # ---> COLE ESTE BLOCO EXATAMENTE AQUI <---
        
        # ====== PAINEL DIREITO (Faceplates e Gráficos) ======
        right_panel = ttk.Frame(paned, padding=10)
        paned.add(right_panel, weight=3)

        fp_frame = ttk.Frame(right_panel)
        fp_frame.pack(fill="x")

        from components.faceplate import Faceplate
        self.fp_level = Faceplate(fp_frame, "LIC-101", self.lc, min_sp=0, max_sp=4.0, unit="m")
        self.fp_level.pack(side="left", padx=10)
        self.fp_temp = Faceplate(fp_frame, "TIC-101", self.tc, min_sp=30, max_sp=100, unit="°C")
        self.fp_temp.pack(side="left", padx=10)

        # Inicialização do Matplotlib
        plt.style.use('dark_background')
        plt.rcParams.update({"axes.facecolor": "#34495e", "figure.facecolor": "#2b3e50", "grid.color": "#bdc3c7", "grid.alpha": 0.2})
        self.fig, axs = plt.subplots(2, 3, figsize=(10, 5), dpi=100)
        self.fig.patch.set_facecolor('#2b3e50')
        
        self.ax_level = axs[0, 0]
        self.ax_temp = axs[0, 1]
        self.ax_CA = axs[0, 2]
        self.ax_level_op = axs[1, 0]
        self.ax_temp_op = axs[1, 1]
        self.ax_CC = axs[1, 2]
        
        # Criação das Linhas

        

        self.line_level_pv, = self.ax_level.plot(self.t_data, self.level_pv, 'g-', label='PV')
        self.line_level_sp, = self.ax_level.plot(self.t_data, self.level_sp, 'w--', label='SP')
        self.ax_level.set_title("Nível (m)"); self.ax_level.set_ylim(0, 5); self.ax_level.grid(True)
        
        self.line_level_op, = self.ax_level_op.plot(self.t_data, self.level_op, 'y-', label='OP')
        self.ax_level_op.set_title("Válvula Saída (%)"); self.ax_level_op.set_ylim(0, 105); self.ax_level_op.grid(True)
        
        self.line_temp_pv, = self.ax_temp.plot(self.t_data, self.temp_pv, 'r-', label='PV')
        self.line_temp_sp, = self.ax_temp.plot(self.t_data, self.temp_sp, 'w--', label='SP')
        self.ax_temp.set_title("Temperatura (°C)"); self.ax_temp.set_ylim(30, 110); self.ax_temp.grid(True)
        
        self.line_temp_op, = self.ax_temp_op.plot(self.t_data, self.temp_op, 'c-', label='Resfriamento OP%')
        self.ax_temp_op.set_title("OP Térmica (0=Frio, 100=Vapor)"); self.ax_temp_op.set_ylim(0, 105); self.ax_temp_op.grid(True)
        
        self.line_CA, = self.ax_CA.plot(self.t_data, self.CA_pv, 'b-', label='CA (Álcool)')
        self.ax_CA.set_title("Conc. Álcool (mol/m³)"); self.ax_CA.set_ylim(0, 1100); self.ax_CA.grid(True)
        
        self.line_CC, = self.ax_CC.plot(self.t_data, self.CC_pv, 'm-', label='CC (Surfactante)')
        self.ax_CC.set_title("Conc. Surfactante (mol/m³)"); self.ax_CC.set_ylim(0, 1100); self.ax_CC.grid(True)
        
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def setup_tuning_tab(self):
        container = ttk.Frame(self.tab_config, padding=20)
        container.pack(fill="both", expand=True)

        split_frame = ttk.Frame(container)
        split_frame.pack(fill="both", expand=True)

        left_frame = ttk.Frame(split_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=20)

        right_frame = ttk.Frame(split_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=20)

        # --- Sintonia PID (Painel Esquerdo) ---
        ttk.Label(left_frame, text="Sintonia dos Controladores (PID)", font=("Arial", 16, "bold"), bootstyle="warning").pack(pady=(0,10))
        
        frame_lc = ttk.LabelFrame(left_frame, text="LIC-101 (Nível)")
        frame_lc.pack(fill="x", pady=10, ipadx=10, ipady=10)
        self.lc_kp_var = tk.DoubleVar(value=self.lc.Kp)
        self.lc_ki_var = tk.DoubleVar(value=self.lc.Ki)
        self.lc_kd_var = tk.DoubleVar(value=self.lc.Kd)
        self.create_entry_row(frame_lc, "Ganho Proporcional (Kp):", self.lc_kp_var, 0)
        self.create_entry_row(frame_lc, "Tempo Integral (Ki):", self.lc_ki_var, 1)
        self.create_entry_row(frame_lc, "Tempo Derivativo (Kd):", self.lc_kd_var, 2)

        frame_tc = ttk.LabelFrame(left_frame, text="TIC-101 (Temperatura)")
        frame_tc.pack(fill="x", pady=10, ipadx=10, ipady=10)
        self.tc_kp_var = tk.DoubleVar(value=self.tc.Kp)
        self.tc_ki_var = tk.DoubleVar(value=self.tc.Ki)
        self.tc_kd_var = tk.DoubleVar(value=self.tc.Kd)
        self.create_entry_row(frame_tc, "Ganho Proporcional (Kp):", self.tc_kp_var, 0)
        self.create_entry_row(frame_tc, "Tempo Integral (Ki):", self.tc_ki_var, 1)
        self.create_entry_row(frame_tc, "Tempo Derivativo (Kd):", self.tc_kd_var, 2)

        # --- Parâmetros do Reator (Painel Direito) ---
        ttk.Label(right_frame, text="Física e Cinética do Reator", font=("Arial", 16, "bold"), bootstyle="info").pack(pady=(0,10))
        
        frame_proc = ttk.LabelFrame(right_frame, text="Constantes do Sistema")
        frame_proc.pack(fill="x", pady=10, ipadx=10, ipady=10)

        self.cv_var = tk.DoubleVar(value=self.model.Cv_out)
        self.area_var = tk.DoubleVar(value=self.model.Area)
        self.A1_var = tk.DoubleVar(value=self.model.A1)
        self.E1_var = tk.DoubleVar(value=self.model.E1)
        self.A2_var = tk.DoubleVar(value=self.model.A2)
        self.E2_var = tk.DoubleVar(value=self.model.E2)

        self.create_entry_row(frame_proc, "Área Base (m²):", self.area_var, 0)
        self.create_entry_row(frame_proc, "Cv da Válvula de Saída:", self.cv_var, 1)
        self.create_entry_row(frame_proc, "Fator Pré-Exp 1 (A1):", self.A1_var, 2)
        self.create_entry_row(frame_proc, "Energia Ativação 1 (E1):", self.E1_var, 3)
        self.create_entry_row(frame_proc, "Fator Pré-Exp 2 (A2):", self.A2_var, 4)
        self.create_entry_row(frame_proc, "Energia Ativação 2 (E2):", self.E2_var, 5)

        # Botão Aplicar
        btn_apply = ttk.Button(container, text="SALVAR ALTERAÇÕES", bootstyle="success", command=self.apply_tunings, width=30)
        btn_apply.pack(pady=20)

    def create_entry_row(self, parent, label_text, var, row):
        ttk.Label(parent, text=label_text, width=22, anchor="e").grid(row=row, column=0, padx=5, pady=8)
        ttk.Entry(parent, textvariable=var, width=15).grid(row=row, column=1, padx=5, pady=8)

    def apply_tunings(self):
        try:
            # Atualiza os PIDs diretamente
            self.lc.Kp = self.lc_kp_var.get()
            self.lc.Ki = self.lc_ki_var.get()
            self.lc.Kd = self.lc_kd_var.get()
            
            self.tc.Kp = self.tc_kp_var.get()
            self.tc.Ki = self.tc_ki_var.get()
            self.tc.Kd = self.tc_kd_var.get()

            # Atualiza a Física
            self.model.Area = self.area_var.get()
            self.model.Cv_out = self.cv_var.get()
            self.model.A1 = self.A1_var.get()
            self.model.E1 = self.E1_var.get()
            self.model.A2 = self.A2_var.get()
            self.model.E2 = self.E2_var.get()

            messagebox.showinfo("Sucesso", "Novos parâmetros aplicados com sucesso!")
        except Exception as e:
            messagebox.showerror("Erro", f"Valor inválido digitado:\n{e}")

    def update_params(self, val):
        self.F_in_nominal = float(val)
        # Atualiza a label em tempo real quando movemos o slider
        self.lbl_flow_val.config(text=f"Vazão de Carga: {self.F_in_nominal:.4f} m³/s")

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        
        # Alterna texto e cor (verde para rodando, amarelo para pausado)
        self.btn_pause.configure(
            text="RESUMIR" if self.is_paused else "PAUSAR",
            bootstyle="warning" if self.is_paused else "success"
        )
        
        if not self.is_paused:
            self.update()

    def reset_sim(self):
        self.model.reset_to_start()
        self.sim_time = 0.0

    def save_history_csv(self):
        try:
            # Pega o tamanho real dos dados guardados no momento
            current_len = len(self.level_pv)
            # Cria um array de tempo aproximado
            time_array = np.arange(current_len) * self.dt 
            
            data = {
                'Time_s': time_array,
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
                filetypes=[("CSV", "*.csv")], initialfile="historico_etoxilacao.csv"
            )
            if filename:
                df.to_csv(filename, index=False)
                messagebox.showinfo("Sucesso", f"Dados salvos em:\n{filename}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar:\n{e}")

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
                messagebox.showinfo("Sucesso", f"Salvo em:\n{filename}")
        except Exception as e:
            messagebox.showerror("Erro", f"Screenshot falhou:\n{e}")    

    def update(self):

        # --- ADICIONE ESTA TRAVA DE SEGURANÇA ---
        if not getattr(self, 'is_running', True):
            return

        
        if self.is_paused:
            self.root.after(100, self.update)
            return

        c_level = self.model.Volume / self.model.Area
        c_temp = self.model.Temperature - 273.15

        op_l = self.fp_level.update(c_level)
        op_t = self.fp_temp.update(c_temp)

        res = self.model.step(self.dt, self.F_in_nominal, self.T_in_nominal+273.15, 
                              self.CA_in_nominal, self.CB_in_nominal, op_l, op_t)
        
        level, temp_k, f_out, ca, cb, cc, cd = res
        temp_c = temp_k - 273.15
        
        self.lbl_ca.config(text=f"CA (Álcool): {ca:.1f}")
        self.lbl_cb.config(text=f"CB (Óxido Etileno): {cb:.1f}")
        self.lbl_cc.config(text=f"CC (Surfactante): {cc:.1f}")
        self.lbl_cd.config(text=f"CD (Subproduto): {cd:.1f}")
        
        # --- ATUALIZAÇÃO DO PLACAR ---

        # ---> ADICIONE A CONVERSÃO DO TEMPO AQUI <---
        # Transforma os segundos em Horas, Minutos e Segundos
        m, s = divmod(int(self.sim_time), 60)
        h, m = divmod(m, 60)
        self.lbl_timer.config(text=f"⏱️ Tempo: {h:02d}:{m:02d}:{s:02d}")

        acc_c = self.model.accumulated_C
        acc_d = self.model.accumulated_D
        
        self.lbl_score_c.config(text=f"Produto (C): {acc_c:.1f} mol")
        self.lbl_score_d.config(text=f"Subproduto (D): {acc_d:.1f} mol")
        
        # Calcula a métrica de qualidade do operador
        if acc_d > 1.0: # Evita divisão por zero
            ratio = acc_c / acc_d
            self.lbl_score_ratio.config(text=f"Razão (C/D): {ratio:.1f}x")
            
            # Muda a cor da razão dependendo do desempenho
            if ratio > 10:
                self.lbl_score_ratio.config(foreground="#2ecc71") # Excelente (Verde)
            elif ratio > 5:
                self.lbl_score_ratio.config(foreground="#f1c40f") # Atenção (Amarelo)
            else:
                self.lbl_score_ratio.config(foreground="#e74c3c") # Ruim (Vermelho)
        else:
            self.lbl_score_ratio.config(text="Razão (C/D): Excelente", foreground="#2ecc71")
        
        self.tank_display.update_level(level, temp_c)

        self.level_pv.append(level)
        if len(self.level_pv) > self.max_history:
            self.level_pv.pop(0)

        self.level_sp.append(self.fp_level.sp_var.get())
        if len(self.level_sp) > self.max_history:
            self.level_sp.pop(0)

        self.level_op.append(op_l)
        if len(self.level_op) > self.max_history:
            self.level_op.pop(0)

        self.temp_pv.append(temp_c)
        if len(self.temp_pv) > self.max_history:
            self.temp_pv.pop(0)

        self.temp_sp.append(self.fp_temp.sp_var.get())
        if len(self.temp_sp) > self.max_history:
            self.temp_sp.pop(0)    

        self.temp_op.append(op_t)
        if len(self.temp_op) > self.max_history:
            self.temp_op.pop(0)

        self.CA_pv.append(ca)
        if len(self.CA_pv) > self.max_history:
            self.CA_pv.pop(0)

        self.CC_pv.append(cc)
        if len(self.CC_pv) > self.max_history:
            self.CC_pv.pop(0)

        '''
        self.level_pv.append(level); self.level_pv.pop(0)
        self.level_sp.append(self.fp_level.sp_var.get()); self.level_sp.pop(0)
        self.level_op.append(op_l); self.level_op.pop(0)
        
        self.temp_pv.append(temp_c); self.temp_pv.pop(0)
        self.temp_sp.append(self.fp_temp.sp_var.get()); self.temp_sp.pop(0)
        self.temp_op.append(op_t); self.temp_op.pop(0)
        
        self.CA_pv.append(ca); self.CA_pv.pop(0)
        self.CC_pv.append(cc); self.CC_pv.pop(0)

        '''

        # Atualiza gráficos a cada 5 passos (para não sobrecarregar a tela)
        if int(self.sim_time * 10) % 5 == 0: 
            view = self.current_view_len
            
            # Cria um vetor X dinâmico do tamanho da janela atual
            x_axis = np.arange(0, view)
            
            # Atualiza X e Y de cada linha, pegando sempre apenas os ÚLTIMOS 'view' pontos
            self.line_level_pv.set_data(x_axis, self.level_pv[-view:])
            self.line_level_sp.set_data(x_axis, self.level_sp[-view:])
            self.line_level_op.set_data(x_axis, self.level_op[-view:])
            
            self.line_temp_pv.set_data(x_axis, self.temp_pv[-view:])
            self.line_temp_sp.set_data(x_axis, self.temp_sp[-view:])
            self.line_temp_op.set_data(x_axis, self.temp_op[-view:])
            
            self.line_CA.set_data(x_axis, self.CA_pv[-view:])
            self.line_CC.set_data(x_axis, self.CC_pv[-view:])
            
            # Pede para o Matplotlib desenhar a nova versão na tela
            self.canvas.draw_idle()
        '''
        if int(self.sim_time * 10) % 5 == 0: 
            self.line_level_pv.set_ydata(self.level_pv)
            self.line_level_sp.set_ydata(self.level_sp)
            self.line_level_op.set_ydata(self.level_op)
            self.line_temp_pv.set_ydata(self.temp_pv)
            self.line_temp_sp.set_ydata(self.temp_sp)
            self.line_temp_op.set_ydata(self.temp_op)
            self.line_CA.set_ydata(self.CA_pv)
            self.line_CC.set_ydata(self.CC_pv)
            self.canvas.draw_idle()
        '''
        self.sim_time += self.dt
        self.root.after(100, self.update)

    def start_loop(self):
        self.update()

    def on_closing(self):
        """Para o loop de simulação e fecha o aplicativo limpo"""
        self.is_running = False  # Avisa ao loop para parar
        self.root.quit()         # Encerra o mainloop do Tkinter
        self.root.destroy()      # Destrói a janela de forma segura

if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    root = ttk.Window(themename="superhero")
    app = CSTRApp(root)
    root.mainloop()
