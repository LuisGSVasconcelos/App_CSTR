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
from model import CSTR
from pid import PIDController
from components.tank_widget import TankWidget
from components.faceplate import Faceplate

# ============================================================
# INTERFACE GRAFICA - SALA DE CONTROLE DO REATOR R-101
# ============================================================
# Esta classe implementa a interface do operador para o simulador
# de CSTR. O operador pode:
#   - Visualizar o nivel e temperatura do reator em tempo real
#   - Ajustar setpoints dos controladores PID (LIC-101, TIC-101)
#   - Alterar a vaz~ao de alimentacao
#   - Alternar entre modo AUTO e MANUAL para cada malha
#   - Salvar dados historico e capturar tela
# ============================================================

class CSTRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador Etoxilacao R-101 - Advanced Process Control")
        self.root.geometry("1400x850")

        self.is_running = True
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Parametros de simulacao
        self.dt = 0.1           # passo de tempo (s)
        self.sim_time = 0.0     # tempo acumulado de simulacao (s)

        # Modelo do reator
        self.model = CSTR()

        # Controladores PID
        #   LIC-101 (Nivel): Kp negativo = acao reversa
        #     (nivel alto -> +erro -> -saida -> fecha valvula)
        #   TIC-101 (Temperatura): Kp positivo = acao direta
        #     (temp alta -> +erro -> +saida -> resfria)
        self.lc = PIDController(Kp=-60.0, Ki=-8.0, Kd=-1.0,
                                dt=self.dt, output_limits=(0, 100))
        self.tc = PIDController(Kp=8.0, Ki=1.2, Kd=0.2,
                                dt=self.dt, output_limits=(0, 100))

        # Variaveis nominais de operacao
        self.F_in_nominal = 0.0012   # m3/s (~4.3 m3/h)
        self.T_in_nominal = 35.0     # C
        self.CA_in_nominal = 1000.0  # mol/m3
        self.CB_in_nominal = 2000.0  # mol/m3

        # Historico para os graficos (buffer circular)
        self.max_history = 5000
        self.current_view_len = 300

        initial_level = self.model.Volume / self.model.Area
        initial_temp = self.model.Temperature - 273.15

        self.level_pv = [initial_level] * self.max_history
        self.level_sp = [initial_level] * self.max_history
        self.level_op = [50.0] * self.max_history

        self.temp_pv = [initial_temp] * self.max_history
        self.temp_sp = [initial_temp] * self.max_history
        self.temp_op = [50.0] * self.max_history

        self.CA_pv = [self.model.CA] * self.max_history
        self.CC_pv = [self.model.CC] * self.max_history

        self.is_paused = False
        self.setup_ui()
        self.start_loop()

    # ----------------------------------------------------------
    # Atualizacao da janela de visualizacao dos graficos
    # ----------------------------------------------------------
    def update_history_window(self, val):
        self.current_view_len = int(float(val))
        self.lbl_history_val.config(text=f"{self.current_view_len} s")

        if not hasattr(self, 'ax_level'):
            return

        for ax in [self.ax_level, self.ax_temp, self.ax_CA,
                   self.ax_level_op, self.ax_temp_op, self.ax_CC]:
            ax.set_xlim(0, self.current_view_len)
        self.canvas.draw_idle()

    # ----------------------------------------------------------
    # Construcao da interface
    # ----------------------------------------------------------
    def setup_ui(self):
        header = ttk.Frame(self.root, bootstyle="danger", padding=10)
        header.pack(fill="x", side="top")

        title_frame = ttk.Frame(header, bootstyle="danger")
        title_frame.pack(side="left", padx=20)

        try:
            pil_img = Image.open("UFCG_logo_png.png")
            h_size = 60
            w_size = int((h_size / float(pil_img.size[1])) * float(pil_img.size[0]))
            pil_img = pil_img.resize((w_size, h_size), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(pil_img)
            ttk.Label(title_frame, image=self.logo_img,
                      bootstyle="inverse-danger").pack(side="left", padx=(0, 10))
            ttk.Label(title_frame, text="LARCA",
                      font=("Arial", 16, "bold"),
                      bootstyle="inverse-danger").pack(side="left", padx=(0, 20))
        except Exception as e:
            print(f"Aviso: Logo nao encontrada. {e}")

        ttk.Label(title_frame, text="UNIDADE DE ETOXILACAO R-101",
                  font=("Arial", 22, "bold"),
                  bootstyle="inverse-danger").pack(side="left")

        btn_frame = ttk.Frame(header, bootstyle="danger")
        btn_frame.pack(side="right", padx=20)

        self.btn_pause = ttk.Button(btn_frame, text="PAUSAR",
                                    bootstyle="success", width=10,
                                    command=self.toggle_pause)
        self.btn_pause.pack(side="left", padx=5)

        ttk.Button(btn_frame, text="RESETAR",
                   bootstyle="secondary", width=10,
                   command=self.reset_sim).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="SALVAR DADOS",
                   bootstyle="dark", width=15,
                   command=self.save_history_csv).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="CAPTURA",
                   bootstyle="info", width=10,
                   command=self.take_screenshot).pack(side="left", padx=5)

        footer = ttk.Frame(self.root, bootstyle="secondary", padding=5)
        footer.pack(fill="x", side="bottom")
        ttk.Label(footer,
                  text="Autor: Luis Vasconcelos | Laboratorio LARCA - UFCG | Process Control",
                  font=("Arial", 10),
                  bootstyle="inverse-secondary").pack(side="right", padx=20)

        self.notebook = ttk.Notebook(self.root, bootstyle="danger")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_op = ttk.Frame(self.notebook)
        self.tab_config = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_op, text=" Painel de Operacao ")
        self.notebook.add(self.tab_config, text=" Parametros e Sintonia ")

        self.setup_operation_tab()
        self.setup_tuning_tab()

    # ----------------------------------------------------------
    # Aba 1 - Painel de Operacao
    # ----------------------------------------------------------
    def setup_operation_tab(self):
        paned = ttk.Panedwindow(self.tab_op, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # --- Painel Esquerdo (tanque, sliders, concentracoes, placar) ---
        left_panel = ttk.Frame(paned, padding=10)
        paned.add(left_panel, weight=1)

        self.tank_display = TankWidget(left_panel, width=220,
                                       height=300, max_level=4.0)
        self.tank_display.pack(pady=(0, 10))

        self.lbl_flow_val = ttk.Label(
            left_panel,
            text=f"Vazao de Carga: {self.F_in_nominal:.4f} m3/s",
            font=("Arial", 10))
        self.lbl_flow_val.pack(anchor="w")
        self.sc_flow = ttk.Scale(left_panel, from_=0.0002, to=0.02,
                                 command=self.update_params,
                                 bootstyle="info")
        self.sc_flow.set(self.F_in_nominal)
        self.sc_flow.pack(fill="x", pady=(2, 10))

        ttk.Label(left_panel, text="Janela Historico (s):",
                  font=("Arial", 10, "bold")).pack(anchor="w")
        self.lbl_history_val = ttk.Label(left_panel, text="300 s")
        self.lbl_history_val.pack(anchor="w")
        self.sc_history = ttk.Scale(left_panel, from_=50,
                                    to=self.max_history,
                                    command=self.update_history_window,
                                    bootstyle="warning")
        self.sc_history.set(300)
        self.sc_history.pack(fill="x", pady=(2, 10))

        ttk.Label(left_panel, text="Concentracao no Reator:",
                  font=("Arial", 9, "bold")).pack(anchor="w")
        self.lbl_ca = ttk.Label(left_panel, text="CA (Alcool): 0.0",
                                font=("Arial", 9))
        self.lbl_ca.pack(anchor="w")
        self.lbl_cb = ttk.Label(left_panel, text="CB (Oxido Etileno): 0.0",
                                font=("Arial", 9))
        self.lbl_cb.pack(anchor="w")
        self.lbl_cc = ttk.Label(left_panel, text="CC (Surfactante): 0.0",
                                font=("Arial", 9))
        self.lbl_cc.pack(anchor="w")
        self.lbl_cd = ttk.Label(left_panel, text="CD (Subproduto): 0.0",
                                font=("Arial", 9))
        self.lbl_cd.pack(anchor="w")

        score_frame = ttk.LabelFrame(left_panel,
                                     text="Placar de Producao")
        score_frame.pack(fill="x", pady=(10, 0), ipadx=5, ipady=5)

        self.lbl_timer = ttk.Label(score_frame,
                                   text="Tempo: 00:00:00",
                                   font=("Arial", 12, "bold"),
                                   foreground="#f39c12")
        self.lbl_timer.pack(anchor="w", pady=(0, 5))

        self.lbl_score_c = ttk.Label(score_frame,
                                     text="C: 0.0 mol",
                                     font=("Arial", 11, "bold"),
                                     foreground="#2ecc71")
        self.lbl_score_c.pack(anchor="w")
        self.lbl_score_d = ttk.Label(score_frame,
                                     text="D: 0.0 mol",
                                     font=("Arial", 11, "bold"),
                                     foreground="#e74c3c")
        self.lbl_score_d.pack(anchor="w")
        self.lbl_score_ratio = ttk.Label(score_frame,
                                         text="Razao: N/A",
                                         font=("Arial", 10, "italic"))
        self.lbl_score_ratio.pack(anchor="w")

        # --- Painel Direito (faceplates + graficos) ---
        right_panel = ttk.Frame(paned, padding=10)
        paned.add(right_panel, weight=3)

        fp_frame = ttk.Frame(right_panel)
        fp_frame.pack(fill="x")

        self.fp_level = Faceplate(fp_frame, "LIC-101", self.lc,
                                  min_sp=0, max_sp=4.0, unit="m")
        self.fp_level.pack(side="left", padx=10)
        self.fp_temp = Faceplate(fp_frame, "TIC-101", self.tc,
                                 min_sp=30, max_sp=100, unit="C")
        self.fp_temp.pack(side="left", padx=10)

        plt.style.use('dark_background')
        plt.rcParams.update({
            "axes.facecolor": "#34495e",
            "figure.facecolor": "#2b3e50",
            "grid.color": "#bdc3c7",
            "grid.alpha": 0.2,
        })
        self.fig, axs = plt.subplots(2, 3, figsize=(10, 5), dpi=100)
        self.fig.patch.set_facecolor('#2b3e50')

        self.ax_level = axs[0, 0]
        self.ax_temp = axs[0, 1]
        self.ax_CA = axs[0, 2]
        self.ax_level_op = axs[1, 0]
        self.ax_temp_op = axs[1, 1]
        self.ax_CC = axs[1, 2]

        x_init = np.arange(self.max_history)

        self.line_level_pv, = self.ax_level.plot(
            x_init, self.level_pv, 'g-', label='PV')
        self.line_level_sp, = self.ax_level.plot(
            x_init, self.level_sp, 'w--', label='SP')
        self.ax_level.set_title("Nivel (m)")
        self.ax_level.set_ylim(0, 5)
        self.ax_level.grid(True)

        self.line_level_op, = self.ax_level_op.plot(
            x_init, self.level_op, 'y-', label='OP')
        self.ax_level_op.set_title("Valvula Saida (%)")
        self.ax_level_op.set_ylim(0, 105)
        self.ax_level_op.grid(True)

        self.line_temp_pv, = self.ax_temp.plot(
            x_init, self.temp_pv, 'r-', label='PV')
        self.line_temp_sp, = self.ax_temp.plot(
            x_init, self.temp_sp, 'w--', label='SP')
        self.ax_temp.set_title("Temperatura (C)")
        self.ax_temp.set_ylim(30, 110)
        self.ax_temp.grid(True)

        self.line_temp_op, = self.ax_temp_op.plot(
            x_init, self.temp_op, 'c-', label='OP Termica')
        self.ax_temp_op.set_title("Split-Range (0=Frio, 100=Vapor)")
        self.ax_temp_op.set_ylim(0, 105)
        self.ax_temp_op.grid(True)

        self.line_CA, = self.ax_CA.plot(
            x_init, self.CA_pv, 'b-', label='CA (Alcool)')
        self.ax_CA.set_title("Conc. Alcool (mol/m3)")
        self.ax_CA.set_ylim(0, 1100)
        self.ax_CA.grid(True)

        self.line_CC, = self.ax_CC.plot(
            x_init, self.CC_pv, 'm-', label='CC (Surfactante)')
        self.ax_CC.set_title("Conc. Surfactante (mol/m3)")
        self.ax_CC.set_ylim(0, 1100)
        self.ax_CC.grid(True)

        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # ----------------------------------------------------------
    # Aba 2 - Parametros e Sintonia
    # ----------------------------------------------------------
    def setup_tuning_tab(self):
        container = ttk.Frame(self.tab_config, padding=20)
        container.pack(fill="both", expand=True)

        split_frame = ttk.Frame(container)
        split_frame.pack(fill="both", expand=True)

        left_frame = ttk.Frame(split_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=20)

        right_frame = ttk.Frame(split_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=20)

        ttk.Label(left_frame, text="Sintonia dos Controladores (PID)",
                  font=("Arial", 16, "bold"),
                  bootstyle="warning").pack(pady=(0, 10))

        ttk.Label(left_frame,
                  text="u(t) = Kp.e(t) + Ki.INT e(t) dt + Kd.de/dt",
                  font=("Arial", 9, "italic")).pack()

        frame_lc = ttk.LabelFrame(left_frame, text="LIC-101 (Nivel)")
        frame_lc.pack(fill="x", pady=10, ipadx=10, ipady=10)
        self.lc_kp_var = tk.DoubleVar(value=self.lc.Kp)
        self.lc_ki_var = tk.DoubleVar(value=self.lc.Ki)
        self.lc_kd_var = tk.DoubleVar(value=self.lc.Kd)
        self.create_entry_row(frame_lc, "Ganho Proporcional (Kp):",
                              self.lc_kp_var, 0)
        self.create_entry_row(frame_lc, "Ganho Integral (Ki):",
                              self.lc_ki_var, 1)
        self.create_entry_row(frame_lc, "Ganho Derivativo (Kd):",
                              self.lc_kd_var, 2)

        frame_tc = ttk.LabelFrame(left_frame, text="TIC-101 (Temperatura)")
        frame_tc.pack(fill="x", pady=10, ipadx=10, ipady=10)
        self.tc_kp_var = tk.DoubleVar(value=self.tc.Kp)
        self.tc_ki_var = tk.DoubleVar(value=self.tc.Ki)
        self.tc_kd_var = tk.DoubleVar(value=self.tc.Kd)
        self.create_entry_row(frame_tc, "Ganho Proporcional (Kp):",
                              self.tc_kp_var, 0)
        self.create_entry_row(frame_tc, "Ganho Integral (Ki):",
                              self.tc_ki_var, 1)
        self.create_entry_row(frame_tc, "Ganho Derivativo (Kd):",
                              self.tc_kd_var, 2)

        ttk.Label(right_frame, text="Fisica e Cinetica do Reator",
                  font=("Arial", 16, "bold"),
                  bootstyle="info").pack(pady=(0, 10))

        frame_proc = ttk.LabelFrame(right_frame, text="Constantes do Sistema")
        frame_proc.pack(fill="x", pady=10, ipadx=10, ipady=10)

        self.cv_var = tk.DoubleVar(value=self.model.Cv_out)
        self.area_var = tk.DoubleVar(value=self.model.Area)
        self.A1_var = tk.DoubleVar(value=self.model.A1)
        self.E1_var = tk.DoubleVar(value=self.model.E1)
        self.A2_var = tk.DoubleVar(value=self.model.A2)
        self.E2_var = tk.DoubleVar(value=self.model.E2)

        self.create_entry_row(frame_proc, "Area Base (m2):",
                              self.area_var, 0)
        self.create_entry_row(frame_proc, "Cv da Valvula de Saida:",
                              self.cv_var, 1)
        self.create_entry_row(frame_proc, "Fator Pre-Exp 1 (A1):",
                              self.A1_var, 2)
        self.create_entry_row(frame_proc, "Energia Ativacao 1 (E1):",
                              self.E1_var, 3)
        self.create_entry_row(frame_proc, "Fator Pre-Exp 2 (A2):",
                              self.A2_var, 4)
        self.create_entry_row(frame_proc, "Energia Ativacao 2 (E2):",
                              self.E2_var, 5)

        btn_apply = ttk.Button(container, text="SALVAR ALTERACOES",
                               bootstyle="success",
                               command=self.apply_tunings, width=30)
        btn_apply.pack(pady=20)

    def create_entry_row(self, parent, label_text, var, row):
        ttk.Label(parent, text=label_text, width=22,
                  anchor="e").grid(row=row, column=0, padx=5, pady=8)
        ttk.Entry(parent, textvariable=var,
                  width=15).grid(row=row, column=1, padx=5, pady=8)

    def apply_tunings(self):
        try:
            self.lc.Kp = self.lc_kp_var.get()
            self.lc.Ki = self.lc_ki_var.get()
            self.lc.Kd = self.lc_kd_var.get()

            self.tc.Kp = self.tc_kp_var.get()
            self.tc.Ki = self.tc_ki_var.get()
            self.tc.Kd = self.tc_kd_var.get()

            self.model.Area = self.area_var.get()
            self.model.Cv_out = self.cv_var.get()
            self.model.A1 = self.A1_var.get()
            self.model.E1 = self.E1_var.get()
            self.model.A2 = self.A2_var.get()
            self.model.E2 = self.E2_var.get()

            messagebox.showinfo("Sucesso",
                                "Novos parametros aplicados com sucesso!")
        except Exception as e:
            messagebox.showerror("Erro",
                                 f"Valor invalido digitado:\n{e}")

    def update_params(self, val):
        self.F_in_nominal = float(val)
        self.lbl_flow_val.config(
            text=f"Vazao de Carga: {self.F_in_nominal:.4f} m3/s")

    # ----------------------------------------------------------
    # Controle de execucao
    # ----------------------------------------------------------
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.btn_pause.configure(
            text="RESUMIR" if self.is_paused else "PAUSAR",
            bootstyle="warning" if self.is_paused else "success"
        )
        if not self.is_paused:
            self.update()

    def reset_sim(self):
        """Reinicia a simulacao: modelo, PIDs e historico."""
        self.model.reset_to_start()
        self.sim_time = 0.0

        self.lc.reset()
        self.tc.reset()

        initial_level = self.model.Volume / self.model.Area
        initial_temp = self.model.Temperature - 273.15

        self.level_pv = [initial_level] * self.max_history
        self.level_sp = [initial_level] * self.max_history
        self.level_op = [50.0] * self.max_history

        self.temp_pv = [initial_temp] * self.max_history
        self.temp_sp = [initial_temp] * self.max_history
        self.temp_op = [50.0] * self.max_history

        self.CA_pv = [self.model.CA] * self.max_history
        self.CC_pv = [self.model.CC] * self.max_history

        self.lbl_score_c.config(text="C: 0.0 mol")
        self.lbl_score_d.config(text="D: 0.0 mol")
        self.lbl_score_ratio.config(text="Razao: N/A",
                                    foreground="#2ecc71")

    # ----------------------------------------------------------
    # Exportacao de dados e captura de tela
    # ----------------------------------------------------------
    def save_history_csv(self):
        try:
            current_len = len(self.level_pv)
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
                'CC_PV_mol/m3': self.CC_pv,
            }
            df = pd.DataFrame(data)
            filename = filedialog.asksaveasfilename(
                title="Salvar Historico",
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                initialfile="historico_etoxilacao.csv")
            if filename:
                df.to_csv(filename, index=False)
                messagebox.showinfo("Sucesso",
                                    f"Dados salvos em:\n{filename}")
        except Exception as e:
            messagebox.showerror("Erro",
                                 f"Falha ao salvar:\n{e}")

    def take_screenshot(self):
        try:
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()

            filename = filedialog.asksaveasfilename(
                title="Salvar Captura",
                defaultextension=".png",
                filetypes=[("PNG", "*.png")],
                initialfile="captura_reator.png")

            if filename:
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                img.save(filename)
                messagebox.showinfo("Sucesso",
                                    f"Salvo em:\n{filename}")
        except Exception as e:
            messagebox.showerror("Erro",
                                 f"Screenshot falhou:\n{e}")

    # ----------------------------------------------------------
    # Loop principal de simulacao
    # ----------------------------------------------------------
    def update(self):
        if not getattr(self, 'is_running', True):
            return

        if self.is_paused:
            self.root.after(100, self.update)
            return

        c_level = self.model.Volume / self.model.Area
        c_temp = self.model.Temperature - 273.15

        op_l = self.fp_level.update(c_level)
        op_t = self.fp_temp.update(c_temp)

        res = self.model.step(
            self.dt,
            self.F_in_nominal,
            self.T_in_nominal + 273.15,
            self.CA_in_nominal,
            self.CB_in_nominal,
            op_l, op_t)

        level, temp_k, f_out, ca, cb, cc, cd = res
        temp_c = temp_k - 273.15

        self.lbl_ca.config(text=f"CA (Alcool): {ca:.1f}")
        self.lbl_cb.config(text=f"CB (Oxido Etileno): {cb:.1f}")
        self.lbl_cc.config(text=f"CC (Surfactante): {cc:.1f}")
        self.lbl_cd.config(text=f"CD (Subproduto): {cd:.1f}")

        m, s = divmod(int(self.sim_time), 60)
        h, m = divmod(m, 60)
        self.lbl_timer.config(
            text=f"Tempo: {h:02d}:{m:02d}:{s:02d}")

        acc_c = self.model.accumulated_C
        acc_d = self.model.accumulated_D
        self.lbl_score_c.config(text=f"Produto (C): {acc_c:.1f} mol")
        self.lbl_score_d.config(
            text=f"Subproduto (D): {acc_d:.1f} mol")

        if acc_d > 1.0:
            ratio = acc_c / acc_d
            self.lbl_score_ratio.config(
                text=f"Razao (C/D): {ratio:.1f}x")
            if ratio > 10:
                self.lbl_score_ratio.config(foreground="#2ecc71")
            elif ratio > 5:
                self.lbl_score_ratio.config(foreground="#f1c40f")
            else:
                self.lbl_score_ratio.config(foreground="#e74c3c")
        else:
            self.lbl_score_ratio.config(text="Razao (C/D): Excelente",
                                        foreground="#2ecc71")

        self.tank_display.update_level(level, temp_c)

        self.level_pv.append(level)
        self.level_pv.pop(0)
        self.level_sp.append(self.fp_level.sp_var.get())
        self.level_sp.pop(0)
        self.level_op.append(op_l)
        self.level_op.pop(0)

        self.temp_pv.append(temp_c)
        self.temp_pv.pop(0)
        self.temp_sp.append(self.fp_temp.sp_var.get())
        self.temp_sp.pop(0)
        self.temp_op.append(op_t)
        self.temp_op.pop(0)

        self.CA_pv.append(ca)
        self.CA_pv.pop(0)
        self.CC_pv.append(cc)
        self.CC_pv.pop(0)

        if int(self.sim_time * 10) % 5 == 0:
            view = self.current_view_len
            x_axis = np.arange(0, view)

            self.line_level_pv.set_data(x_axis,
                                         self.level_pv[-view:])
            self.line_level_sp.set_data(x_axis,
                                         self.level_sp[-view:])
            self.line_level_op.set_data(x_axis,
                                         self.level_op[-view:])

            self.line_temp_pv.set_data(x_axis,
                                        self.temp_pv[-view:])
            self.line_temp_sp.set_data(x_axis,
                                        self.temp_sp[-view:])
            self.line_temp_op.set_data(x_axis,
                                        self.temp_op[-view:])

            self.line_CA.set_data(x_axis, self.CA_pv[-view:])
            self.line_CC.set_data(x_axis, self.CC_pv[-view:])

            self.canvas.draw_idle()

        self.sim_time += self.dt
        self.root.after(100, self.update)

    def start_loop(self):
        self.update()

    def on_closing(self):
        self.is_running = False
        self.root.quit()
        self.root.destroy()


# ============================================================
# PONTO DE ENTRADA
# ============================================================
if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = ttk.Window(themename="superhero")
    app = CSTRApp(root)
    root.mainloop()
