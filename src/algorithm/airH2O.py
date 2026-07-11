from CoolProp.CoolProp import PropsSI, HAPropsSI


def Cp_dryAir(t):
    return PropsSI('C', 'T', t+273.15, 'P', 101325.0, 'Air') / 1000.0

def get_SHR_min(ha_N, da_N,RH_set):
    ha_S_min = -20.0
    da_S_min = hR_d(ha_S_min, RH_set)
    return (ha_N - ha_S_min) / (da_N - da_S_min)

def isoHumidCount(da, RH, ha_max):
    delta_ha = 5.0
    ha = 0.0
    while delta_ha > 0.000001:
        ha = ha_max - delta_ha
        d = HAPropsSI('W', 'H', ha*1000.0, 'R', RH, 'P', 101325.0)
        if d > da:
            ha_max = ha
        else:
            delta_ha /= 2.0
    return ha

def tb_dew(t_dry, t_wet):
    t_dry_K = t_dry + 273.15
    t_wet_K = t_wet + 273.15
    d = HAPropsSI('W', 'T', t_dry_K, 'B', t_wet_K, 'P', 101325.0)
    ha_max = HAPropsSI('H', 'T', t_dry_K, 'B', t_wet_K, 'P', 101325.0) / 1000.0
    ha = isoHumidCount(d, 1.0, ha_max)
    return HAPropsSI('T', 'H', ha*1000.0, 'W', d, 'P', 101325.0) - 273.15

def get_SF_hd(ha_N, da_N, SHR, RH_set=0.95):
    ha_max = isoHumidCount(da_N, RH_set, ha_N)
    delta_ha = 5.0
    ha, da = 0.0, 0.0
    while delta_ha > 0.000001:
        ha = ha_max - delta_ha
        if ha < -20.0:
            ha = -20.0
            print(f"SHR值太小，导致计算超范围.ha={ha}, da={da}")
            break
        da = hR_d(ha, RH_set)
        SHR_calculated = (ha_N - ha) / (da_N - da)
        
        if SHR_calculated > SHR:
            ha_max = ha
        else:
            delta_ha /= 2.0
    
    return ha, da

def tR_h(t_dry, RH):
    t_dry_K = t_dry + 273.15
    return HAPropsSI('H', 'T', t_dry_K, 'R', RH, 'P', 101325.0) / 1000.0

def tR_d(t_dry, RH):
    t_dry_K = t_dry + 273.15
    return HAPropsSI('W', 'T', t_dry_K, 'R', RH, 'P', 101325.0)

def tR_Rho(t_dry, RH):
    t_dry_K = t_dry + 273.15
    return 1.0 / HAPropsSI('V', 'T', t_dry_K, 'R', RH, 'P', 101325.0)

def tR_b(t_dry, RH):
    t_dry_K = t_dry + 273.15
    return HAPropsSI('B', 'T', t_dry_K, 'R', RH, 'P', 101325.0) - 273.15

def hR_d(ha, RH):
    return HAPropsSI('W', 'H', ha*1000.0, 'R', RH, 'P', 101325.0)

def hd_b(ha, d):
    return HAPropsSI('B', 'H', ha*1000.0, 'W', d, 'P', 101325.0) - 273.15

def hd_t(ha, d):
    return HAPropsSI('T', 'H', ha*1000.0, 'W', d, 'P', 101325.0) - 273.15

def tb_h(t_dry, t_wet):
    t_dry_K = t_dry + 273.15
    t_wet_K = t_wet + 273.15
    return HAPropsSI('H', 'T', t_dry_K, 'B', t_wet_K, 'P', 101325.0) / 1000.0

def tb_d(t_dry, t_wet):
    t_dry_K = t_dry + 273.15
    t_wet_K = t_wet + 273.15
    return HAPropsSI('W', 'T', t_dry_K, 'B', t_wet_K, 'P', 101325.0)

def tb_K(t_dry, t_wet):
    t_dry_K = t_dry + 273.15
    t_wet_K = t_wet + 273.15
    return HAPropsSI('K', 'T', t_dry_K, 'B', t_wet_K, 'P', 101325.0) / 1000.0

def tb_M(t_dry, t_wet):
    t_dry_K = t_dry + 273.15
    t_wet_K = t_wet + 273.15
    return HAPropsSI('M', 'T', t_dry_K, 'B', t_wet_K, 'P', 101325.0)

def tb_C(t_dry, t_wet):
    t_dry_K = t_dry + 273.15
    t_wet_K = t_wet + 273.15
    return HAPropsSI('C', 'T', t_dry_K, 'B', t_wet_K, 'P', 101325.0) / 1000.0

def td_h(t_dry, d):
    t_dry_K = t_dry + 273.15
    return HAPropsSI('H', 'T', t_dry_K, 'W', d, 'P', 101325.0) / 1000.0

def td_b(t_dry, d):
    t_dry_K = t_dry + 273.15
    return HAPropsSI('B', 'T', t_dry_K, 'W', d, 'P', 101325.0) - 273.15

def td_C(t_dry, d):
    t_dry_K = t_dry + 273.15
    return HAPropsSI('C', 'T', t_dry_K, 'W', d, 'P', 101325.0) / 1000.0

def td_Rho(t_dry, d):
    t_dry_K = t_dry + 273.15
    return 1.0 / HAPropsSI('V', 'T', t_dry_K, 'W', d, 'P', 101325.0)

def tb_Rho(t_dry, t_wet):
    t_dry_K = t_dry + 273.15
    t_wet_K = t_wet + 273.15
    return 1.0 / HAPropsSI('V', 'T', t_dry_K, 'B', t_wet_K, 'P', 101325.0)

def get_Q_D(ha_N, da_N, ha_S, da_S, Ga):
    Q = (ha_N - ha_S) * Ga
    D = (da_N - da_S) * Ga
    return Q, D

def Cp_w(tw):
    t = tw + 273.15
    return PropsSI('C', 'T', t, 'Q', 0, 'water') / 1000.0

def Rho_w(tw):
    t = tw + 273.15
    return PropsSI('D', 'T', t, 'Q', 0, 'water')

def conductivity_w(tw):
    t = tw + 273.15
    return PropsSI('L', 'T', t, 'Q', 0, 'water') / 1000.0

def viscosity_w(tw):
    t = tw + 273.15
    return PropsSI('V', 'T', t, 'Q', 0, 'water')

def LH_vaporization(tw):
    t = tw + 273.15
    ha_v = PropsSI('H', 'T', t, 'Q', 1, 'water') / 1000.0
    ha_l = PropsSI('H', 'T', t, 'Q', 0, 'water') / 1000.0
    return ha_v - ha_l
