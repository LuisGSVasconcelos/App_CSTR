"""
tank_widget.py — Visualizac~ao grafica do tanque do reator
============================================================

Implementa um widget Canvas que desenha um tanque com n'ivel
de liquido animado e gradiente de cor azul-vermelho de acordo
com a temperatura do conteudo.
"""

import tkinter as tk


class TankWidget(tk.Canvas):
    """
    Desenha um tanque com preenchimento proporcional ao n'ivel.

    A cor do l'iquido varia continuamente entre:
        - Azul (20 C)  -> frio
        - Vermelho (120 C) -> quente

    Parametros:
        parent    : widget pai
        width     : largura do canvas (pixels)
        height    : altura do canvas (pixels)
        max_level : n'ivel m'aximo do tanque em metros
    """

    def __init__(self, parent, width=150, height=300, max_level=5.0):
        super().__init__(parent, width=width, height=height,
                         bg="#2b3e50", highlightthickness=0)
        self.width = width
        self.height = height
        self.max_level = max_level

        tank_margin = 40
        self.tank_x = tank_margin // 2
        self.tank_y = tank_margin // 2
        self.tank_w = width - tank_margin
        self.tank_h = height - tank_margin

        # Moldura do tanque
        self.create_rectangle(
            self.tank_x, self.tank_y,
            self.tank_x + self.tank_w, self.tank_y + self.tank_h,
            outline="white", width=3)

        # Retangulo interno do nivel (inicialmente vazio)
        self.level_rect = self.create_rectangle(
            self.tank_x + 2, self.tank_y + self.tank_h,
            self.tank_x + self.tank_w - 2, self.tank_y + self.tank_h,
            fill="#3498db", outline="")

        # R'otulos de escala
        self.create_text(10, self.tank_y,
                         text=f"{max_level}m",
                         anchor="e", font=("Arial", 8), fill="white")
        self.create_text(10, self.tank_y + self.tank_h,
                         text="0m", anchor="e",
                         font=("Arial", 8), fill="white")

    # ----------------------------------------------------------
    # Mapa de cores temperatura -> cor
    # ----------------------------------------------------------
    def _get_color_from_temp(self, temp):
        """
        Mapeia temperatura (C) para cor RGB.
        Faixa: 20 C = azul, 120 C = vermelho.

        Args:
            temp (float): temperatura em graus Celsius.

        Returns:
            str: string de cor no formato '#rrggbb'.
        """
        t = max(20, min(temp, 120))
        ratio = (t - 20) / 100.0

        r = int(ratio * 255)
        g = 0
        b = int((1 - ratio) * 255)

        return f"#{r:02x}{g:02x}{b:02x}"

    # ----------------------------------------------------------
    # Atualizacao do nivel e cor
    # ----------------------------------------------------------
    def update_level(self, current_level, current_temp):
        """
        Atualiza a altura e a cor do l'iquido no tanque.

        Args:
            current_level (float): nivel atual em metros.
            current_temp (float): temperatura atual em graus Celsius.
        """
        level = max(0, min(current_level, self.max_level))

        px_per_m = self.tank_h / self.max_level
        fill_height = level * px_per_m

        # Coordenadas: y cresce para baixo na tela
        top_y = (self.tank_y + self.tank_h) - fill_height

        self.coords(
            self.level_rect,
            self.tank_x + 2, top_y,
            self.tank_x + self.tank_w - 2, self.tank_y + self.tank_h)

        color = self._get_color_from_temp(current_temp)
        self.itemconfig(self.level_rect, fill=color)
