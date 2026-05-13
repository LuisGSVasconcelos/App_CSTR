"""
pid.py — Controlador PID Digital com Anti-Windup
=================================================

Implementa um controlador PID na forma paralela:

    u(t) = Kp * e(t)  +  Ki * INT e(tau) dtau  +  Kd * de(t)/dt

    onde:
        e(t) = SP - PV   (erro = setpoint - variavel de processo)
        Kp   = ganho proporcional
        Ki   = ganho integral
        Kd   = ganho derivativo

Sinal de controle discreto (Euler progressivo):

    u_n = Kp * e_n  +  Ki * I_n  +  Kd * (e_n - e_{n-1}) / dt

    I_n = I_{n-1} + e_n * dt   (integracao retangular)

O controlador inclui:
    - Limitacao da sa'ida (satura,ao do atuador entre min_out e max_out)
    - Anti-windup condicional: a integral s'o acumula quando o
      sinal de sa'ida n~ao esta saturado, evitando o "integral windup"

Sinal de erro: sempre SP - PV.
"""

import numpy as np


class PIDController:
    """
    Controlador PID digital com anti-windup condicional.

    A equac~ao implementada (dom'inio discreto, Euler progressivo):

        u_n = Kp * e_n  +  Ki * I_n  +  Kd * (e_n - e_{n-1}) / dt

        I_n = I_{n-1} + e_n * dt   [apenas se n~ao saturado]

    A,cao de controle:
        Kp > 0  (direta):  PV > SP -> u aumenta (resfria / abre valvula)
        Kp < 0  (reversa): PV > SP -> u diminui (fecha valvula)

    Parametros de construcao:
        Kp  : ganho proporcional
        Ki  : ganho integral
        Kd  : ganho derivativo
        dt  : per'iodo de amostragem (s)
        output_limits : tupla (min, max) para satura,ao do atuador
    """

    def __init__(self, Kp=1.0, Ki=0.0, Kd=0.0, dt=0.1,
                 output_limits=(0, 100)):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.dt = dt
        self.min_out, self.max_out = output_limits

        self.integral = 0.0
        self.prev_error = 0.0

    def compute(self, setpoint, pv):
        """
        Calcula a sa'ida do controlador dado o setpoint e o PV.

        Parametros
        ----------
        setpoint : float
            Valor desejado (SP) para a vari'avel controlada.
        pv : float
            Valor medido (PV) da vari'avel de processo.

        Retorna
        -------
        float
            Sa'ida do controlador, limitada entre min_out e max_out.
        """
        error = setpoint - pv

        P_term = self.Kp * error

        derivative = (error - self.prev_error) / self.dt
        D_term = self.Kd * derivative

        temp_integral = self.integral + error * self.dt
        I_term = self.Ki * temp_integral

        tentative_output = P_term + I_term + D_term

        # Anti-windup condicional: s'o atualiza a integral se
        # o sinal n~ao estiver saturado (ou se estiver "desaturando")
        if tentative_output > self.max_out:
            final_output = self.max_out
            if self.Ki * error < 0:
                self.integral = temp_integral
        elif tentative_output < self.min_out:
            final_output = self.min_out
            if self.Ki * error > 0:
                self.integral = temp_integral
        else:
            final_output = tentative_output
            self.integral = temp_integral

        self.prev_error = error

        return final_output

    def set_tunings(self, Kp, Ki, Kd):
        """Atualiza os ganhos do PID em tempo real."""
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd

    def reset(self):
        """Zera o termo integral e o erro anterior (reinicia o PID)."""
        self.integral = 0.0
        self.prev_error = 0.0
