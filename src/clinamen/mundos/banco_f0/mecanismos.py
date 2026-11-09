"""Mecanismos del mundo de banco F0.

ADVERTENCIA: mundo de prueba de ingeniería. Sus ecuaciones son deliberadamente sencillas y sus
parámetros son supuestos sin calibrar. Sirve para comprobar el motor (determinismo, gemelos,
identidades contables, rendimiento) con el tamaño del objetivo de §14.3: 30 entidades, unas 40
variables por entidad y 15 mecanismos. No es una afirmación sobre la historia.

Convenciones obligatorias del motor:

* Cada variable de entidad es un array (E, B); cada global, (1, B).
* Se escribe reasignando la entrada del diccionario (``x[v] = ...``), nunca modificando arrays en
  sitio por otra vía: así el rastreo de lecturas y escrituras de las pruebas es completo.
* Funciones trascendentes y reducciones solo a través de ``clinamen.numerica.mat``.
* Cada fuente de azar se sortea una vez por paso, en un único mecanismo, y los sucesos declarados
  se pasan como intervalos [lo, hi) de la uniforme; el desenlace se decide con ``u < hi``.
"""
from __future__ import annotations

import numpy as np

from ...azar.campo import pareto_truncada
from ...numerica import mat


# ---------------------------------------------------------------------------- estado inicial
def estado_inicial(c):
    x, p = c.x, c.p
    u = c.azar.uniformes("inicial")
    terr = p.ini_terr_min + (p.ini_terr_max - p.ini_terr_min) * u[0]
    tierra_max = terr * p.frac_cultivable * 100.0
    ocup = p.ini_ocup_min + (p.ini_ocup_max - p.ini_ocup_min) * u[1]
    tierra = tierra_max * ocup
    pob = tierra / p.ha_por_persona
    tasa = p.ini_tasa_min + (p.ini_tasa_max - p.ini_tasa_min) * u[4]
    cap = p.ini_cap_min + (p.ini_cap_max - p.ini_cap_min) * u[5]
    ingreso_tipico = tasa * cap * tierra * p.agr_y0
    x["territorio"] = terr
    x["tierra_cultivada"] = tierra
    x["poblacion"] = pob
    x["reservas"] = pob * p.cons_necesidad * (p.ini_res_min + (p.ini_res_max - p.ini_res_min) * u[2])
    x["tecnologia"] = p.ini_tec_min + (p.ini_tec_max - p.ini_tec_min) * u[3]
    x["tasa_fiscal"] = tasa
    x["capacidad_fiscal"] = cap
    x["tesoro"] = u[6] * p.ini_tesoro_anios * ingreso_tipico
    x["deuda"] = u[7] * p.ini_deuda_anios * ingreso_tipico
    x["ejercito"] = p.mil_frac * pob
    x["elites"] = pob * p.el_ratio_ref * (0.5 + u[8])
    x["legitimidad"] = p.ini_leg_min + (p.ini_leg_max - p.ini_leg_min) * u[9]
    x["inestabilidad"] = p.ini_inest_max * u[10]
    x["urbanizacion"] = p.ini_urb_min + (p.ini_urb_max - p.ini_urb_min) * u[11]
    x["gobernante_edad"] = p.ini_gob_edad_min + (p.ini_gob_edad_max - p.ini_gob_edad_min) * u[12]
    x["gobernante_fragilidad"] = mat.exp(p.gob_frag_sigma * mat.ndtri(u[13]))
    x["gobernante_capacidad"] = mat.ndtri(u[14])
    x["gobernante_mandato"] = p.ini_mandato_max * u[15]
    x["inmunidad"] = p.ini_inm_max * u[16]
    x["anomalia_clima"] = mat.ndtri(u[17]) * (p.clima_sigma / mat.sqrt(1.0 - p.clima_rho * p.clima_rho))
    x["epidemia_mortalidad"] = np.zeros_like(pob)
    x["rendimiento"] = np.full_like(pob, p.agr_y0)
    x["suficiencia_alimentaria"] = np.ones_like(pob)
    x["salario_real"] = np.full_like(pob, p.cons_necesidad)
    x["forzamiento_volcanico"] = np.zeros((1, c.B))


# ---------------------------------------------------------------------------- 1. volcán
def forzamiento_volcanico(c):
    x, p = c.x, c.p
    u_occ, u_mag = c.azar.uniformes("volcan", eventos={
        "erupcion": (0.0, p.vol_p), "sin_erupcion": (p.vol_p, 1.0)})
    hay = u_occ < p.vol_p
    erupcion = np.where(hay, pareto_truncada(u_mag, p.vol_xm, p.vol_alfa, p.vol_max), 0.0)
    x["erupcion"] = erupcion
    x["forzamiento_volcanico"] = x["forzamiento_volcanico"] * p.vol_persistencia + erupcion


# ---------------------------------------------------------------------------- 2. clima
def clima(c):
    x, p = c.x, c.p
    (z,) = c.azar.normales("clima_interno", eventos={
        "innovacion_adversa": (0.0, p.clima_p_adversa),
        "innovacion_no_adversa": (p.clima_p_adversa, 1.0)})
    x["anomalia_clima"] = (p.clima_rho * x["anomalia_clima"] + p.clima_sigma * z
                           - p.clima_gamma_volcan * x["forzamiento_volcanico"])


# ---------------------------------------------------------------------------- 3. tecnología
def tecnologia(c):
    x, p = c.x, c.p
    T = x["tecnologia"]
    q = p.tec_p_inv * (0.5 + x["urbanizacion"] / p.urb_max)
    (u,) = c.azar.uniformes("invencion", eventos={"invencion": (0.0, q), "sin_invencion": (q, 1.0)})
    dT = p.tec_r * T * (1.0 - T / p.tec_max) + p.tec_difusion * (c.topo.media_vecinos(T) - T)
    x["tecnologia"] = (T + dT) * np.where(u < q, 1.0 + p.tec_salto, 1.0)


# ---------------------------------------------------------------------------- 4. agricultura
def agricultura(c):
    x, p = c.x, c.p
    tierra_max = x["territorio"] * p.frac_cultivable * 100.0
    objetivo = np.minimum(tierra_max, x["poblacion"] * p.ha_por_persona)
    tierra = x["tierra_cultivada"]
    tierra = np.minimum(tierra + p.agr_ajuste * (objetivo - tierra), tierra_max)
    ocup = tierra / tierra_max
    m_clima = mat.acotar(1.0 + p.agr_beta_clima * x["anomalia_clima"], p.agr_clima_min, p.agr_clima_max)
    rend = (p.agr_y0 * mat.potencia(x["tecnologia"], p.agr_tec_elast) * m_clima
            * (1.0 - p.agr_rend_decreciente * ocup))
    prod = tierra * rend
    x["tierra_cultivada"] = tierra
    x["rendimiento"] = rend
    x["produccion"] = prod
    x["reservas"] = x["reservas"] + prod


# ---------------------------------------------------------------------------- 5. recaudación
def recaudacion(c):
    x = c.x
    ingresos = np.minimum(x["tasa_fiscal"] * x["capacidad_fiscal"] * x["produccion"], x["reservas"])
    x["ingresos_fiscales"] = ingresos
    x["reservas"] = x["reservas"] - ingresos
    x["tesoro"] = x["tesoro"] + ingresos


# ---------------------------------------------------------------------------- 6. comercio
def comercio(c):
    x, p, topo = c.x, c.p, c.topo
    R, P = x["reservas"], x["poblacion"]
    pc = mat.division_segura(R, P)
    pca, pcb = topo.extremos(pc)
    Ra, Rb = topo.extremos(R)
    Pa, Pb = topo.extremos(P)
    f = 0.5 * p.com_kappa * (pca - pcb) * np.minimum(Pa, Pb)
    f = np.minimum(f, p.com_cap * Ra / topo.G)
    f = np.maximum(f, -p.com_cap * Rb / topo.G)
    salidas, entradas = topo.flujo_a_entidades(f)
    x["exportaciones"] = salidas
    x["importaciones"] = entradas
    x["reservas"] = R - salidas + entradas


# ---------------------------------------------------------------------------- 7. consumo
def consumo(c):
    x, p = c.x, c.p
    P = x["poblacion"]
    necesidad = P * p.cons_necesidad
    cons = np.minimum(necesidad, p.cons_max_frac * x["reservas"])
    resto = x["reservas"] - cons
    mermas = p.merma * resto
    x["consumo"] = cons
    x["mermas"] = mermas
    x["reservas"] = resto - mermas
    x["suficiencia_alimentaria"] = mat.acotar(mat.division_segura(cons, necesidad, 1.0), 0.0, 1.0)
    x["salario_real"] = mat.division_segura(cons, P)


# ---------------------------------------------------------------------------- 8. demografía
def demografia(c):
    x, p = c.x, c.p
    P = x["poblacion"]
    suf = x["suficiencia_alimentaria"]
    z1, z2 = c.azar.normales("vital")
    nac = P * p.dem_natalidad * (1.0 - p.dem_natal_hambre * (1.0 - suf)) * mat.positiva(1.0 + p.dem_sigma * z1)
    m_ord = np.minimum(P * p.dem_mortalidad * mat.positiva(1.0 + p.dem_sigma * z2), 0.5 * P)
    hambre = 1.0 - suf
    m_ham = np.minimum(P * p.dem_hambre * hambre * hambre, 0.9 * P - m_ord)
    x["nacimientos"] = nac
    x["muertes_ordinarias"] = m_ord
    x["muertes_hambre"] = m_ham
    x["poblacion"] = P + nac - m_ord - m_ham


# ---------------------------------------------------------------------------- 9. epidemia
def epidemia(c):
    x, p = c.x, c.p
    epi = x["epidemia_mortalidad"]
    q = mat.acotar(p.epi_p_ext + p.epi_p_contagio * c.topo.suma_vecinos(epi), 0.0, p.epi_p_max)
    u1, u2 = c.azar.uniformes("epidemia", eventos={"brote": (0.0, q), "sin_brote": (q, 1.0)})
    brote = u1 < q
    virulencia = pareto_truncada(u2, p.epi_xm, p.epi_alfa, p.epi_max)
    nueva = np.where(brote, virulencia * (1.0 - x["inmunidad"]), epi * p.epi_decaimiento)
    muertes = nueva * x["poblacion"]
    x["epidemia_mortalidad"] = nueva
    x["inmunidad"] = mat.acotar(x["inmunidad"] * p.inm_decaimiento + p.inm_ganancia * nueva, 0.0, 1.0)
    x["muertes_epidemia"] = muertes
    x["poblacion"] = x["poblacion"] - muertes


# ---------------------------------------------------------------------------- 10. migración
def migracion(c):
    x, p, topo = c.x, c.p, c.topo
    P = x["poblacion"]
    wa, wb = topo.extremos(x["salario_real"])
    Pa, Pb = topo.extremos(P)
    f = p.mig_mu * mat.division_segura(wb - wa, wa + wb) * np.minimum(Pa, Pb)
    f = np.minimum(f, p.mig_cap * Pa / topo.G)
    f = np.maximum(f, -p.mig_cap * Pb / topo.G)
    emig, inmig = topo.flujo_a_entidades(f)
    x["emigrantes"] = emig
    x["inmigrantes"] = inmig
    x["poblacion"] = P - emig + inmig
    objetivo = p.urb_base + (p.urb_max - p.urb_base) * mat.sigmoide(
        p.urb_pendiente * (x["tecnologia"] - p.urb_T0)) * x["suficiencia_alimentaria"]
    x["urbanizacion"] = x["urbanizacion"] + p.urb_ajuste * (objetivo - x["urbanizacion"])


# ---------------------------------------------------------------------------- 11. gobernante
def gobernante(c):
    x, p = c.x, c.p
    edad = x["gobernante_edad"] + 1.0
    frag = x["gobernante_fragilidad"]
    h = p.gob_gompertz_a * frag * mat.exp(p.gob_gompertz_b * (edad - 20.0))
    q = mat.acotar(1.0 - mat.exp(-h), p.gob_q_min, p.gob_q_max)
    (u,) = c.azar.uniformes("muerte_gobernante", eventos={"muere": (0.0, q), "sobrevive": (q, 1.0)})
    muere = u < q
    s1, s2, s3 = c.azar.uniformes("sucesion")
    x["gobernante_edad"] = np.where(muere, p.gob_edad_min + p.gob_edad_rango * s1, edad)
    x["gobernante_fragilidad"] = np.where(muere, mat.exp(p.gob_frag_sigma * mat.ndtri(s2)), frag)
    x["gobernante_capacidad"] = np.where(muere, mat.ndtri(s3), x["gobernante_capacidad"])
    x["gobernante_mandato"] = np.where(muere, 0.0, x["gobernante_mandato"] + 1.0)
    leg = x["legitimidad"]
    x["legitimidad"] = np.where(muere, leg - p.gob_shock_sucesion * leg, leg)
    x["gobernante_murio"] = muere.astype(np.float64)


# ---------------------------------------------------------------------------- 12. militar
def militar(c):
    x, p = c.x, c.p
    ej, P = x["ejercito"], x["poblacion"]
    amenaza = mat.acotar(mat.division_segura(c.topo.max_vecinos(ej), ej, p.mil_amenaza_max + 1.0) - 1.0,
                         0.0, p.mil_amenaza_max)
    objetivo = p.mil_frac * P * (1.0 + p.mil_amenaza_peso * amenaza)
    recl = np.minimum(mat.positiva(p.mil_ajuste * (objetivo - ej)), p.mil_reclut_max * P)
    lic = mat.positiva(p.mil_ajuste * (ej - objetivo))
    lic = np.minimum(np.maximum(lic, ej + recl - p.mil_tope * P), ej + recl)
    x["reclutas"] = recl
    x["licenciados"] = lic
    x["ejercito"] = ej + recl - lic


# ---------------------------------------------------------------------------- 13. guerra
def guerra(c):
    x, p, topo = c.x, c.p, c.topo
    ej, P, terr, leg = x["ejercito"], x["poblacion"], x["territorio"], x["legitimidad"]
    psa, psb = topo.extremos(x["inestabilidad"])
    q = mat.acotar(p.gue_p0 * (1.0 + p.gue_inest * (psa + psb)), 0.0, p.gue_p_max)
    (u_w,) = c.azar.uniformes("guerra", eventos={"estalla": (0.0, q), "paz": (q, 1.0)})
    hay = u_w < q
    fuerza = ej * (1.0 + p.gue_peso_gob * mat.tanh(x["gobernante_capacidad"])) * (0.5 + 0.5 * leg)
    Sa, Sb = topo.extremos(fuerza)
    pa = mat.acotar(mat.division_segura(Sa * Sa, Sa * Sa + Sb * Sb, 0.5),
                    p.gue_sorpresa_min, 1.0 - p.gue_sorpresa_min)
    (u_r,) = c.azar.uniformes("batalla", eventos={
        "gana_a": (0.0, np.where(hay, pa, 1.0)), "gana_b": (np.where(hay, pa, 0.0), 1.0)})
    gana_a = u_r < pa
    (u_m,) = c.azar.uniformes("batalla_magnitud")
    L = np.where(hay, pareto_truncada(u_m, p.gue_xm, p.gue_alfa, p.gue_max), 0.0)
    Ea, Eb = topo.extremos(ej)
    Pa, Pb = topo.extremos(P)
    Ta, Tb = topo.extremos(terr)
    baj_a = L * Ea * np.where(gana_a, p.gue_bajas_ganador, 1.0)
    baj_b = L * Eb * np.where(gana_a, 1.0, p.gue_bajas_ganador)
    civ_a = np.where(gana_a, 0.0, p.gue_civiles * L * Pa)
    civ_b = np.where(gana_a, p.gue_civiles * L * Pb, 0.0)
    cedido = p.gue_territorio * L * np.where(gana_a, Tb, Ta)
    gan_a = np.where(gana_a, cedido, 0.0)
    gan_b = np.where(gana_a, 0.0, cedido)
    hayf = hay.astype(np.float64)
    dleg_a = np.where(hay, np.where(gana_a, p.gue_legit_victoria, -p.gue_legit_derrota), 0.0)
    dleg_b = np.where(hay, np.where(gana_a, -p.gue_legit_derrota, p.gue_legit_victoria), 0.0)
    bajas = topo.reunir(baj_a, baj_b)
    civiles = topo.reunir(civ_a, civ_b)
    ganado = topo.reunir(gan_a, gan_b)
    perdido = topo.reunir(gan_b, gan_a)
    x["bajas_militares"] = bajas
    x["muertes_guerra"] = bajas + civiles
    x["territorio_ganado"] = ganado
    x["territorio_perdido"] = perdido
    x["guerras_libradas"] = topo.reunir(hayf, hayf)
    x["ejercito"] = ej - bajas
    x["poblacion"] = P - (bajas + civiles)
    x["territorio"] = terr + ganado - perdido
    x["legitimidad"] = mat.acotar(leg + topo.reunir(dleg_a, dleg_b), 0.0, 1.0)


# ---------------------------------------------------------------------------- 14. fiscalidad y deuda
def fiscal(c):
    x, p = c.x, c.p
    ingresos, deuda, caja = x["ingresos_fiscales"], x["deuda"], x["tesoro"]
    int_plan = p.fis_interes * deuda
    gm_plan = p.mil_soldada * x["ejercito"]
    gc_plan = p.fis_gasto_civil * ingresos
    necesidad = int_plan + gm_plan + gc_plan
    capacidad_prestamo = mat.positiva(p.fis_lim_deuda * ingresos - deuda)
    prest = np.minimum(mat.positiva(necesidad - caja), capacidad_prestamo)
    disp = caja + prest
    pago_int = np.minimum(int_plan, disp)
    disp = disp - pago_int
    pago_gm = np.minimum(gm_plan, disp)
    disp = disp - pago_gm
    pago_gc = np.minimum(gc_plan, disp)
    disp = disp - pago_gc
    amort = np.minimum(deuda, p.fis_frac_amort * mat.positiva(disp - p.fis_reserva * ingresos))
    deuda = deuda + prest - amort
    impaga = (pago_int < int_plan) | (deuda > p.fis_lim_impago * ingresos)
    impago = np.where(impaga, p.fis_frac_impago * deuda, 0.0)
    estres = (prest > 0.0) | impaga
    tasa = x["tasa_fiscal"]
    x["tasa_fiscal"] = np.where(estres, np.minimum(tasa + p.fis_tasa_paso, p.fis_tasa_max),
                                tasa + p.fis_tasa_relaj * (p.fis_tasa_base - tasa))
    cap = x["capacidad_fiscal"]
    cap = (cap + p.fis_cap_aprendizaje * (1.0 - cap) * (1.0 + p.fis_cap_gob * mat.tanh(x["gobernante_capacidad"]))
           - np.where(impaga, p.fis_cap_shock, 0.0))
    x["capacidad_fiscal"] = mat.acotar(cap, 0.01, 1.0)
    x["legitimidad"] = mat.acotar(x["legitimidad"] - np.where(impaga, p.fis_shock_impago, 0.0), 0.0, 1.0)
    x["intereses"] = pago_int
    x["gasto_militar"] = pago_gm
    x["gasto_civil"] = pago_gc
    x["prestamos"] = prest
    x["amortizacion"] = amort
    x["impago"] = impago
    x["tesoro"] = disp - amort
    x["deuda"] = deuda - impago


# ---------------------------------------------------------------------------- 15. élites y crisis interna
def elites_crisis(c):
    x, p = c.x, c.p
    P, el, leg = x["poblacion"], x["elites"], x["legitimidad"]
    ratio = mat.division_segura(el, P)
    sobreprod = mat.positiva(ratio / p.el_ratio_ref - 1.0)
    estres = mat.acotar(mat.division_segura(x["deuda"], p.fis_lim_deuda * x["ingresos_fiscales"], 1.0), 0.0, 1.0)
    hambre = 1.0 - x["suficiencia_alimentaria"]
    psi_obj = mat.sigmoide(p.cri_pendiente * (p.cri_w_elite * sobreprod + p.cri_w_fiscal * estres
                                              + p.cri_w_hambre * hambre + p.cri_w_legit * (1.0 - leg)
                                              - p.cri_umbral))
    psi = x["inestabilidad"]
    psi = psi + p.cri_ajuste * (psi_obj - psi)
    q = mat.acotar(p.cri_r0 * psi * psi, p.cri_q_min, p.cri_q_max)
    u1, u2 = c.azar.uniformes("revuelta", eventos={"revuelta": (0.0, q), "calma": (q, 1.0)})
    R = np.where(u1 < q, pareto_truncada(u2, p.cri_xm, p.cri_alfa, 1.0), 0.0)
    gob = mat.tanh(x["gobernante_capacidad"])
    x["revuelta_magnitud"] = R
    x["inestabilidad"] = mat.acotar(psi * (1.0 - p.cri_alivio * R), 0.0, 1.0)
    x["legitimidad"] = mat.acotar(leg - p.cri_legit_rev * R + p.leg_ajuste * (p.leg_base + p.leg_gob * gob - leg),
                                  0.0, 1.0)
    x["capacidad_fiscal"] = mat.acotar(x["capacidad_fiscal"] - p.cri_cap_rev * R, 0.01, 1.0)
    entrada = el * p.el_crecimiento * mat.positiva(1.0 - ratio / p.el_ratio_max)
    salida = el * (p.el_mortalidad + p.el_purga * R)
    salida = np.minimum(np.maximum(salida, el + entrada - p.el_tope * P), el + entrada)
    x["entrada_elites"] = entrada
    x["salida_elites"] = salida
    x["elites"] = el + entrada - salida


MECANISMOS = [
    forzamiento_volcanico, clima, tecnologia, agricultura, recaudacion, comercio, consumo,
    demografia, epidemia, migracion, gobernante, militar, guerra, fiscal, elites_crisis,
]
