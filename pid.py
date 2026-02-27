import numpy as np

class PIDController:
    def __init__(self, Kp=1.0, Ki=0.0, Kd=0.0, dt=0.1, output_limits=(0, 100), direction="direct"):
        """
        Initialize the PID Controller.
        
        Args:
            Kp (float): Proportional Gain.
            Ki (float): Integral Gain.
            Kd (float): Derivative Gain.
            dt (float): Time step size (s).
            output_limits (tuple): (Min, Max) output values.
            direction (str): 'direct' (error=PV-SP) or 'reverse' (error=SP-PV).
                             Actually usually:
                             Reverse (Heating): PV < SP -> Output increases. Error = SP - PV.
                             Direct (Cooling/Level?): PV > SP -> Output increases?
                             Let's stick to standard error = SP - PV for Reverse Action (Heating).
                             Wait, if Kp is positive:
                             Error = SP - PV.
                             If SP > PV, Error > 0, Output increases. This is Heating (Reverse Acting).
                             
                             If Kp is negative:
                             Error = SP - PV.
                             If SP > PV, Error > 0, Output decreases. This is wrong for heating.
                             
                             Usually Kp sign handles it. 
                             Let's assume Error = SP - PV always.
                             Then Kp > 0 -> Heating (PV low -> Out high).
                             Kp < 0 -> Cooling (PV high -> Out high? No).
                             
                             Standard convention:
                             Error = Setpoint - PV.
        """
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.dt = dt
        self.min_out, self.max_out = output_limits
        
        self.integral = 0.0
        self.prev_error = 0.0
        
    def compute(self, setpoint, pv):
        """
        Compute the controller output.
        
        Args:
            setpoint (float): Desired value.
            pv (float): Process Variable (current value).
            
        Returns:
            float: Controller Output (clamped to limits).
        """
        # Standard Error: SP - PV
        error = setpoint - pv
        
        # Proportional Term
        P_term = self.Kp * error
        
        # Derivative Term
        derivative = (error - self.prev_error) / self.dt
        D_term = self.Kd * derivative
        
        # Tentative Output for Anti-Windup
        # Calculate what the integral term WOULD be
        # Trapezoidal or Rectangular? Rectangular forward: sum += error * dt
        temp_integral = self.integral + error * self.dt
        I_term = self.Ki * temp_integral
        
        tentative_output = P_term + I_term + D_term
        
        # Output Clamping & Anti-Windup Logic
        final_output = tentative_output
        
        if tentative_output > self.max_out:
            final_output = self.max_out
            # If saturated at Max, only integrate if unwinding (I_term decreasing)
            # Change in I = Ki * error * dt
            # If Ki*error > 0, we are trying to go further into saturation. Stop.
            delta_I_change = self.Ki * error # Direction of change
            if delta_I_change < 0: # Unwinding
                self.integral = temp_integral
            # else: keep old integral
        elif tentative_output < self.min_out:
            final_output = self.min_out
            # If saturated at Min, only integrate if unwinding (I_term increasing)
            delta_I_change = self.Ki * error
            if delta_I_change > 0: # Unwinding
                self.integral = temp_integral
        else:
            final_output = tentative_output
            self.integral = temp_integral
            
        # Update previous error
        self.prev_error = error
        
        return final_output

    def set_tunings(self, Kp, Ki, Kd):
        """Update PID parameters on the fly."""
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
    
    def reset(self):
        """Reset internal state."""
        self.integral = 0.0
        self.prev_error = 0.0
