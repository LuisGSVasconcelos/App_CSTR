import numpy as np
import matplotlib.pyplot as plt
from model import HeatingTank

def test_heating_tank():
    # Initialize Tank with NEW parameters
    tank = HeatingTank(Area=2.0, H_max=5.0, A_coil=15.0, U=2000.0)
    
    # Simulation Parameters
    dt = 1.0 
    sim_time = 600 
    steps = int(sim_time / dt)
    
    # Inputs 
    F_in = 0.02 # Safe flow limit
    T_in = 20.0
    Valve_Pct = 8.5 # Low valve to maintain Level ~2.5m (High Residence Time)
    P_steam = 2.0 # Initial Pressure
    
    print(f"Starting Simulation: F_in={F_in}, T_in={T_in}, A_coil={tank.A_coil}")
    
    times = []
    temps = []
    
    for i in range(steps):
        # Step change in Steam Pressure to 6 bar at t=100
        if i * dt > 100:
            P_steam = 10.0 
            
        inputs = (dt, F_in, T_in, Valve_Pct, P_steam)
        L, T, F_out = tank.step(*inputs)
        
        times.append(i * dt)
        temps.append(T)
        
    print(f"Final Temp: {temps[-1]:.2f} C with P_steam={P_steam} bar")
    
    # Check if we can reach > 60C
    assert temps[-1] > 60.0, "Should reach setpoint with these parameters"
    print("Verification Passed! System has sufficient capacity.")

if __name__ == "__main__":
    test_heating_tank()
