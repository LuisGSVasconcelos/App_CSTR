"""
model.py — Modelo Matemático do CSTR para Etoxilação
====================================================

Este módulo implementa o modelo fenomenológico de um Reator Contínuo
de Tanque Agitado (CSTR) não-isotérmico para a reação de etoxilação.
O código foi estruturado para fins didáticos em disciplinas de Graduação e 
Pós-Graduação em Engenharia Química, destacando cada etapa da modelagem.

---------------------------------------------------------------------------
ESQUEMA REACIONAL
---------------------------------------------------------------------------
Duas reações exotérmicas consecutivas ocorrem no reator:

    (1)  A + B  --k1-->  C       (reação principal)
    (2)  A + C  --k2-->  D       (reação consecutiva indesejada)

    A = Álcool graxo (reagente)
    B = Óxido de Etileno (reagente gasoso)
    C = Surfactante etoxilado (PRODUTO DESEJADO)
    D = Subproduto

---------------------------------------------------------------------------
CINÉTICA QUÍMICA (Lei de Arrhenius)
---------------------------------------------------------------------------
Cada reação segue cinética elementar de 2ª ordem. A constante de
velocidade é dada pela Lei de Arrhenius:

    k_i(T) = A_i * exp( -E_i / (R * T) )

    r_1 = k_1 * C_A * C_B
    r_2 = k_2 * C_C * C_A

onde:
    A_i = fator pré-exponencial (m³/mol·s)
    E_i = energia de ativação (J/mol)
    R   = constante universal dos gases (8,314 J/mol·K)
    T   = temperatura absoluta (K)

---------------------------------------------------------------------------
BALANÇOS DE MASSA (espécie i em um CSTR com volume variável)
---------------------------------------------------------------------------
Partindo do balanço molar geral para um CSTR:

    d(N_i) / dt = F_in * C_i^in - F_out * C_i + V * Σ(ν_ij * r_j)

onde N_i = V * C_i. Expandindo:

    V * dC_i/dt + C_i * dV/dt = F_in * C_i^in - F_out * C_i + V * Σ(ν_ij * r_j)

Substituindo dV/dt = F_in - F_out e simplificando:

    dC_i/dt = (F_in / V) * (C_i^in - C_i) + Σ(ν_ij * r_j)

Aplicando para cada espécie:

    dC_A/dt = (F_in / V) * (C_A^in - C_A) - r_1 - r_2
    dC_B/dt = (F_in / V) * (C_B^in - C_B) - 2*r_1
    dC_C/dt = (F_in / V) * (0 - C_C) + r_1 - r_2
    dC_D/dt = (F_in / V) * (0 - C_D) + r_2

Os coeficientes estequiométricos (-1 para reagentes, +1 para produtos)
refletem o consumo/formação de cada espécie.

---------------------------------------------------------------------------
BALANÇO DE ENERGIA
---------------------------------------------------------------------------
Para um CSTR não-isotérmico com camisa de aquecimento/resfriamento:

    dT/dt = [ Q_sensivel + Q_reacao + Q_jack ] / (rho * Cp * V)

onde:
    Q_sensivel = F_in * rho * Cp * (T_in - T)     [calor sensível da alimentação]
    Q_reacao   = -ΔH_1 * r_1 * V - ΔH_2 * r_2 * V  [calor gerado pelas reações]
    Q_jack     = sinal térmico da camisa            [aquece ou resfria]

NOTA: ΔH é negativo para reações exotérmicas. O termo Q_reacao se torna
positivo (gera calor) pois (-ΔH) > 0.

---------------------------------------------------------------------------
BALANÇO DE VOLUME (NÍVEL)
---------------------------------------------------------------------------
    dV/dt = F_in - F_out

A vazão de saída é modelada por uma válvula com comportamento
de fluxo turbulento (raiz quadrada do nível):

    F_out = Cv * f * sqrt(h)

    h = V / Area      (nível no tanque)
    f = OP / 100      (fração de abertura da válvula)

---------------------------------------------------------------------------
CONTROLE TÉRMICO SPLIT-RANGE (COM TEMPERATURA DOS FLUIDOS)
---------------------------------------------------------------------------
O sistema utiliza uma estratégia split-range com dois fluidos térmicos:

    [0% - 50%] : Resfriamento — água de resfriamento a 25°C
    [50% - 100%] : Aquecimento — vapor de baixa pressão (135°C)
    50%        : Neutro (válvulas fechadas)

A carga térmica é calculada com base na diferença de temperatura entre
o fluido e o reator, garantindo comportamento fisicamente realista:

    Q_cooling = UA_cooling * (T_coolant - T) * frac_cooling
    Q_heating = UA_heating * (T_steam - T) * frac_heating

Dessa forma, quando T → T_coolant, o resfriamento diminui naturalmente,
impedindo que a temperatura do reator caia abaixo da água de resfriamento.

---------------------------------------------------------------------------
INTEGRAÇÃO NUMÉRICA
---------------------------------------------------------------------------
Método de Euler explícito com 5 sub-passos por iteração para melhorar
a estabilidade numérica na presença de dinâmicas rápidas (rigidez
moderada do sistema de EDOs).

    y_{n+1} = y_n + (dy/dt) * dt_sub
"""

import numpy as np


class CSTR:
    """
    Modelo de CSTR não-isotérmico para etoxilação.

    Integra numericamente (Euler com sub-passos) as equações de
    balanço de massa (4 espécies), balanço de energia e balanço
    de volume, considerando duas reações exotérmicas consecutivas.

    Parâmetros de construção:
        Area    : área da seção transversal do tanque (m²)
        H_max   : altura máxima operacional do tanque (m)
        Cv_out  : coeficiente de vazão da válvula de saída
        rho     : densidade da mistura reacional (kg/m³)
        Cp      : capacidade calorífica da mistura (J/kg·K)
        A1, A2  : fatores pré-exponenciais de Arrhenius (m³/mol·s)
        E1, E2  : energias de ativação (J/mol)
        deltaH1 : entalpia da reação 1 (J/mol) — negativa (exotérmica)
        deltaH2 : entalpia da reação 2 (J/mol) — negativa (exotérmica)
        R       : constante universal dos gases (J/mol·K)
        T_coolant : temperatura da água de resfriamento (K) — padrão 298,15 (25°C)
        T_steam : temperatura do vapor de aquecimento (K) — padrão 408,15 (135°C)
        UA_cooling : coeficiente global U·A da camisa de resfriamento (W/K)
        UA_heating : coeficiente global U·A do vapor de aquecimento (W/K)
    """

    def __init__(self, Area=3.75, H_max=4.0, Cv_out=0.03,
                 rho=900.0, Cp=2500.0,
                 A1=5.0e6, E1=75000.0,
                 A2=1.0e8, E2=90000.0,
                 deltaH1=-184000.0, deltaH2=-220000.0,
                 R=8.314,
                 T_coolant=298.15, T_steam=408.15,
                 UA_cooling=333333.0, UA_heating=30120.0):
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

        # Parâmetros do sistema térmico split-range
        self.T_coolant = T_coolant               # K (25°C — água de resfriamento)
        self.T_steam = T_steam                   # K (135°C — vapor de baixa pressão)
        self.UA_cooling = UA_cooling             # W/K (produto U·A da camisa de resfriamento)
        self.UA_heating = UA_heating             # W/K (produto U·A do vapor)

        self.reset_to_start()

    # ------------------------------------------------------------------
    # Estado inicial
    # ------------------------------------------------------------------
    def reset_to_start(self):
        """
        Reinicia o reator para as condições iniciais de operação.

        Volume baixo (0.5 m³) e temperatura ambiente (~37°C) garantem
        partida segura. A concentração inicial de EO (B) é mantida baixa
        para evitar taxa reacional explosiva no instante inicial.
        """
        self.Volume = 0.5                 # m³
        self.Temperature = 310.15          # K (~37°C)

        self.CA = 1000.0                   # mol/m³  (álcool)
        self.CB = 50.0                     # mol/m³  (EO baixo)
        self.CC = 0.0                      # mol/m³  (surfactante)
        self.CD = 0.0                      # mol/m³  (subproduto)

        # Acumuladores para a "gamificação" (mols exportados)
        self.accumulated_C = 0.0           # mol de produto C recuperados
        self.accumulated_D = 0.0           # mol de subproduto D recuperados

    # ------------------------------------------------------------------
    # Passo de integração
    # ------------------------------------------------------------------
    def step(self, dt, F_in, T_in, CA_in, CB_in,
             Valve_Open_Pct, Q_thermal_signal):
        """
        Avança a simulação em um passo de tempo *dt*.

        A integração usa Euler explícito com 5 sub-passos para
        contornar a rigidez numérica moderada do sistema.

        Parâmetros
        ----------
        dt                : passo de tempo (s)
        F_in              : vazão volumétrica de alimentação (m³/s)
        T_in              : temperatura da alimentação (K)
        CA_in             : concentração de A na alimentação (mol/m³)
        CB_in             : concentração de B na alimentação (mol/m³)
        Valve_Open_Pct    : abertura da válvula de saída (0 a 100%)
        Q_thermal_signal  : sinal split-range (0 a 100%)
                            0 = máximo resfriamento (água 25°C)
                            50 = neutro
                            100 = máximo aquecimento (vapor 135°C)
                            A carga térmica real depende da diferença
                            entre a temperatura do fluido e a do reator.

        Retorna
        -------
        tuple   (level, T, F_out, CA, CB, CC, CD)
            level : nível do tanque (m)
            T     : temperatura (K)
            F_out : vazão de saída (m³/s)
            CA-D  : concentrações (mol/m³)
        """
        sub_dt = dt / 5.0

        for _ in range(5):
            # ----------------------------------------------------------
            # Vazão de saída (válvula com característica quadrática)
            # ----------------------------------------------------------
            valve_frac = Valve_Open_Pct / 100.0
            level = self.Volume / self.Area
            h = max(level, 0.001)
            F_out = self.Cv_out * valve_frac * np.sqrt(h)

            T = self.Temperature

            # ----------------------------------------------------------
            # Leis de Arrhenius para ambas as reações
            # ----------------------------------------------------------
            k1 = self.A1 * np.exp(-self.E1 / (self.R * T))
            k2 = self.A2 * np.exp(-self.E2 / (self.R * T))

            # ----------------------------------------------------------
            # Taxas reacionais (cinética elementar)
            # ----------------------------------------------------------
            r1 = k1 * self.CA * self.CB    # A + B  ->  C
            r2 = k2 * self.CC * self.CA    # A + C  ->  D

            V = max(self.Volume, 0.1)

            # ----------------------------------------------------------
            # Balanços de Massa (forma simplificada para volume variável)
            # ----------------------------------------------------------
            dCA_dt = (F_in * (CA_in - self.CA)) / V - r1 - r2
            dCB_dt = (F_in * (CB_in - self.CB)) / V - 2.0 * r1
            dCC_dt = (F_in * (0.0 - self.CC)) / V + r1 - r2
            dCD_dt = (F_in * (0.0 - self.CD)) / V + r2

            # ----------------------------------------------------------
            # Controle Térmico Split-Range (calor trocado por diferença de temperatura)
            # Q_cooling = UA_c * (T_coolant - T) * frac
            # Q_heating = UA_h * (T_steam - T) * frac
            # A força motriz (ΔT) diminui conforme T se aproxima do fluido,
            # impedindo temperaturas abaixo da água de resfriamento (25°C).
            # ----------------------------------------------------------
            if Q_thermal_signal < 50.0:
                frac_cooling = (50.0 - Q_thermal_signal) / 50.0
                Q_thermal = self.UA_cooling * (self.T_coolant - T) * frac_cooling
            else:
                frac_heating = (Q_thermal_signal - 50.0) / 50.0
                Q_thermal = self.UA_heating * (self.T_steam - T) * frac_heating

            # ----------------------------------------------------------
            # Balanço de Energia
            # ----------------------------------------------------------
            Q_rxn = (self.deltaH1 * r1 + self.deltaH2 * r2) * V
            Q_inflow = F_in * self.rho * self.Cp * (T_in - T)

            dT_dt = (Q_inflow - Q_rxn + Q_thermal) / (self.rho * self.Cp * V)

            # ----------------------------------------------------------
            # Integração Explícita de Euler (sub-passo)
            # ----------------------------------------------------------
            self.Volume = np.clip(
                self.Volume + (F_in - F_out) * sub_dt,
                0.1,
                self.Area * self.H_max
            )
            self.Temperature += dT_dt * sub_dt
            self.CA = max(self.CA + dCA_dt * sub_dt, 0)
            self.CB = max(self.CB + dCB_dt * sub_dt, 0)
            self.CC = max(self.CC + dCC_dt * sub_dt, 0)
            self.CD = max(self.CD + dCD_dt * sub_dt, 0)

            # ----------------------------------------------------------
            # Acumuladores de produção (gamificação)
            # ----------------------------------------------------------
            self.accumulated_C += F_out * self.CC * sub_dt
            self.accumulated_D += F_out * self.CD * sub_dt

        return (self.Volume / self.Area, self.Temperature, F_out,
                self.CA, self.CB, self.CC, self.CD)
