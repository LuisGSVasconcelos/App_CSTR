import numpy as np

import numpy as np

class CSTR:
    def __init__(self, Area=2.0, H_max=5.0, Cv_out=0.05,
                 rho=1000.0, Cp=4184.0,
                 A1=1e6, E1=50000.0,
                 A2=1e8, E2=60000.0,
                 deltaH1=-50000.0, deltaH2=-70000.0,
                 R=8.314):
        """
        Modelo de CSTR não isotérmico com duas reações:
          A + B -> C   (taxa r1 = k1 * CA * CB)
          A + C -> D   (taxa r2 = k2 * CA * CC)
        """
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
        self.Volume = 1.0          # m³
        self.Temperature = 300.0   # K
        self.CA = 0.0
        self.CB = 0.0
        self.CC = 0.0
        self.CD = 0.0
        
    def step(self, dt, F_in, T_in, CA_in, CB_in, Valve_Open_Pct, Q_heating):
        # Válvula de saída
        valve_frac = np.clip(Valve_Open_Pct, 0, 100) / 100.0
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