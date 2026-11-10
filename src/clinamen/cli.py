"""Interfaz de línea de órdenes.

    clinamen ontologia [--mundo banco_f0]
    clinamen ensemble --particulas 1000 --anios 200 --semilla 1 --salida corridas/x [--pod pod.yaml] ...
    clinamen puerta-f0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def _ontologia(args):
    from .gemelos.intervencion import catalogo
    from .mundos import obtener_modelo
    m = obtener_modelo(args.mundo)
    o = m.ontologia
    ent = [v for v in o.variables if v.ambito == "entidad"]
    print(f"Ontología {o.nombre}: huella {o.huella()}")
    print(f"  {m.E} entidades, {m.topo.A} aristas, {len(ent)} variables por entidad, {len(o.variables) - len(ent)} globales")
    print(f"  {len(o.parametros)} parámetros, {len(o.fuentes)} fuentes de azar, {len(o.identidades)} identidades, "
          f"{len(o.mecanismos)} mecanismos, {len(o.observables)} observables")
    if o.advertencia:
        print(f"  ADVERTENCIA: {o.advertencia}")
    print("Fuentes de azar:")
    for f in o.fuentes:
        cola = f" α={f.indice_cola.nominal} {list(f.indice_cola.intervalo)}" if f.indice_cola else ""
        print(f"  {f.nombre:18s} {f.familia:13s} dominio={f.dominio:8s} τ={f.tiempo_identidad_anios}{cola}")
    print("Catálogo de intervenciones:")
    for c in catalogo(o):
        print("  " + json.dumps(c, ensure_ascii=False))


def _ensemble(args):
    from .motor.salida import ConfigEnsemble, ejecutar_ensemble
    pod = None
    if args.pod:
        ruta = Path(args.pod)
        pod = yaml.safe_load(ruta.read_text(encoding="utf-8")) if ruta.exists() else json.loads(args.pod)
    anclas = tuple(int(a) for a in args.anclas.split(",")) if args.anclas else ()
    cfg = ConfigEnsemble(mundo=args.mundo, particulas=args.particulas, anios=args.anios, semilla=args.semilla,
                         pod=pod, acoplamiento=args.acoplamiento, bloque=args.bloque, anios_ancla=anclas,
                         verificar=not args.sin_verificar, motor_philox=args.philox)
    man = ejecutar_ensemble(cfg, args.salida, procesos=args.procesos, max_horas=args.max_horas,
                            solo_estimar=args.estimar)
    if args.estimar:
        e = man["estimacion"]
        print(json.dumps(e, indent=2, ensure_ascii=False))


def _puerta_f0(args):
    from .puerta.f0 import evaluar_puerta_f0
    res = evaluar_puerta_f0(args.salida) if args.salida else evaluar_puerta_f0()
    sys.exit(0 if res["supera_puerta"] else 1)


def _puerta_f1(args):
    from .puerta.f1 import evaluar_puerta_f1
    kw = {"procesos": args.procesos, "max_horas": args.max_horas}
    res = evaluar_puerta_f1(args.salida, **kw) if args.salida else evaluar_puerta_f1(**kw)
    sys.exit(0 if res["supera_puerta"] else 1)


def _puerta_f2a(args):
    from .puerta.f2a import evaluar_puerta_f2a
    res = evaluar_puerta_f2a(args.salida) if args.salida else evaluar_puerta_f2a()
    sys.exit(0 if res["supera_puerta"] else 1)


def _puerta_f2a_cliopatria(args):
    from .ingesta.cliopatria import cargar_panel_cliopatria
    from .puerta.f2a import evaluar_puerta_f2a
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    res = evaluar_puerta_f2a(args.salida or raiz / "informes" / "F2a_cliopatria", prerregistro="F2a_cliopatria",
                             panel=cargar_panel_cliopatria(), var="Terr", observables=("Terr",), correcciones=True)
    if args.posthoc_seshat:
        evaluar_puerta_f2a(raiz / "informes" / "F2a_iter2_seshat_POSTHOC", correcciones=True)
    sys.exit(0 if res["supera_puerta"] else 1)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="clinamen", description="Motor de historia contrafactual (fase F0)")
    sub = ap.add_subparsers(dest="orden", required=True)

    o = sub.add_parser("ontologia", help="valida y resume la ontología de un mundo")
    o.add_argument("--mundo", default="banco_f0")
    o.set_defaults(f=_ontologia)

    e = sub.add_parser("ensemble", help="ejecuta un ensemble (con gemelos si se da un POD)")
    e.add_argument("--mundo", default="banco_f0")
    e.add_argument("--particulas", type=int, required=True)
    e.add_argument("--anios", type=int, required=True)
    e.add_argument("--semilla", type=int, required=True)
    e.add_argument("--salida", required=True)
    e.add_argument("--pod", help="fichero YAML o JSON en línea con el POD")
    e.add_argument("--acoplamiento", default="fisico", choices=["fisico", "maximo", "independiente"])
    e.add_argument("--bloque", type=int, default=256)
    e.add_argument("--procesos", type=int, default=1)
    e.add_argument("--anclas", help="pasos ancla con estado completo, separados por comas")
    e.add_argument("--max-horas", type=float, default=2.0, help="aborta si la estimación supera este tope")
    e.add_argument("--estimar", action="store_true", help="solo estima la duración")
    e.add_argument("--sin-verificar", action="store_true", help="no verifica identidades (más rápido)")
    e.add_argument("--philox", default="auto", choices=["auto", "numpy", "numba"])
    e.set_defaults(f=_ensemble)

    p = sub.add_parser("puerta-f0", help="evalúa la puerta F0 contra el prerregistro")
    p.add_argument("--salida", default=None)
    p.set_defaults(f=_puerta_f0)

    p1 = sub.add_parser("puerta-f1", help="evalúa la puerta F1 contra el prerregistro (reanudable)")
    p1.add_argument("--salida", default=None)
    p1.add_argument("--procesos", type=int, default=4)
    p1.add_argument("--max-horas", type=float, default=2.0)
    p1.set_defaults(f=_puerta_f1)

    p2 = sub.add_parser("puerta-f2a", help="evalúa la puerta F2a: hindcast de escala social con Seshat")
    p2.add_argument("--salida", default=None)
    p2.set_defaults(f=_puerta_f2a)

    p3 = sub.add_parser("puerta-f2a-cliopatria", help="iteración 2 de F2a validada con Cliopatria")
    p3.add_argument("--salida", default=None)
    p3.add_argument("--posthoc-seshat", action="store_true", help="además, iteración 2 sobre Seshat (post hoc)")
    p3.set_defaults(f=_puerta_f2a_cliopatria)

    args = ap.parse_args(argv)
    args.f(args)


if __name__ == "__main__":
    main()
