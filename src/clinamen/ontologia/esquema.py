"""M1 — Ontología: esquema tipado de variables, parámetros, fuentes de azar, identidades,
observables y fichas de mecanismo.

Reglas que hace cumplir (si fallan, la ontología no compila):

* Toda variable tiene unidad y rango (M1, §14.1).
* Todo parámetro declara procedencia (dato / estimado / prior-LLM-ciego / supuesto), un prior con
  rango que contiene su valor, una referencia y si es invariante ante intervenciones (A13, §11.4).
* Toda fuente de azar declara familia, tiempo de identidad entre mundos y, si es de cola pesada,
  su índice de cola con intervalo (A4, A8, §3.4, §4.3).
* Toda variable de tipo stock tiene una identidad contable stock-flujo (A3).
* Toda ficha de mecanismo está completa y sus referencias existen (§14.2).
* No hay variables, parámetros ni fuentes huérfanos: cada uno lo usa algún mecanismo
  (antipatrón «estado sin límites», §20).
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Procedencia = Literal["dato", "estimado", "prior-LLM-ciego", "supuesto"]
FamiliaRuido = Literal["difusiva", "salto_ligero", "salto_pesado"]
Bloque = Literal["M", "G", "A", "E"]
Ambito = Literal["entidad", "global"]
TipoVariable = Literal["stock", "flujo", "estado", "derivada"]
Dominio = Literal["entidad", "arista", "global"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Variable(_Base):
    nombre: str
    bloque: Bloque
    ambito: Ambito = "entidad"
    tipo: TipoVariable
    unidad: str = Field(min_length=1)
    rango: tuple[float, float]
    descripcion: str = Field(min_length=1)

    @field_validator("rango")
    @classmethod
    def _rango(cls, v):
        if not (v[0] <= v[1]):
            raise ValueError(f"rango vacío {v}")
        return v


class Prior(_Base):
    familia: Literal["uniforme", "log-uniforme", "normal-truncada", "beta", "degenerado"]
    rango: tuple[float, float]

    @field_validator("rango")
    @classmethod
    def _rango(cls, v):
        if not (v[0] <= v[1]):
            raise ValueError(f"rango de prior vacío {v}")
        return v

    @model_validator(mode="after")
    def _logu(self):
        if self.familia == "log-uniforme" and self.rango[0] <= 0:
            raise ValueError("prior log-uniforme con rango no positivo")
        return self


class Parametro(_Base):
    nombre: str
    valor: float
    unidad: str = Field(min_length=1)
    prior: Prior
    procedencia: Procedencia
    referencia: str = Field(min_length=1)
    invariante: bool
    descripcion: str = ""

    @model_validator(mode="after")
    def _valor_en_prior(self):
        lo, hi = self.prior.rango
        if not (lo <= self.valor <= hi):
            raise ValueError(f"parámetro {self.nombre}: valor {self.valor} fuera de su prior {self.prior.rango}")
        return self


class IndiceCola(_Base):
    nominal: float = Field(gt=0)
    intervalo: tuple[float, float]

    @model_validator(mode="after")
    def _int(self):
        lo, hi = self.intervalo
        if not (0 < lo <= self.nominal <= hi):
            raise ValueError(f"índice de cola {self.nominal} fuera de su intervalo {self.intervalo}")
        return self


class Evento(_Base):
    nombre: str
    ranura: int = Field(ge=0)
    descripcion: str = Field(min_length=1)


class FuenteAzar(_Base):
    nombre: str
    familia: FamiliaRuido
    dominio: Dominio
    ranuras: int = Field(ge=1, le=128, description="uniformes por elemento del dominio y paso")
    tiempo_identidad_anios: Union[float, Literal["inf"]]
    justificacion_identidad: str = Field(min_length=1)
    indice_cola: Optional[IndiceCola] = None
    eventos: tuple[Evento, ...] = ()
    inclinable: bool = Field(False, description="admite POD de inclinación gaussiana (ranuras normales)")
    descripcion: str = Field(min_length=1)

    @model_validator(mode="after")
    def _cola(self):
        if self.familia == "salto_pesado" and self.indice_cola is None:
            raise ValueError(f"fuente {self.nombre}: cola pesada sin índice de cola (A4)")
        if self.familia != "salto_pesado" and self.indice_cola is not None:
            raise ValueError(f"fuente {self.nombre}: índice de cola en una fuente que no es de cola pesada")
        t = self.tiempo_identidad_anios
        if t != "inf" and (not isinstance(t, (int, float)) or t < 0):
            raise ValueError(f"fuente {self.nombre}: tiempo de identidad inválido {t}")
        nombres = [e.nombre for e in self.eventos]
        if len(set(nombres)) != len(nombres):
            raise ValueError(f"fuente {self.nombre}: eventos repetidos")
        for e in self.eventos:
            if e.ranura >= self.ranuras:
                raise ValueError(f"fuente {self.nombre}: evento {e.nombre} en ranura inexistente")
        return self

    @property
    def tau(self) -> float:
        return math.inf if self.tiempo_identidad_anios == "inf" else float(self.tiempo_identidad_anios)


class Identidad(_Base):
    """Identidad contable verificada en cada paso.

    * ``stock_flujo``: stock(t+1) = stock(t) + Σ entradas − Σ salidas, por entidad.
    * ``conservacion_global``: Σ_e Σ izquierda = Σ_e Σ derecha, por partícula.
    * ``stock_global_constante``: Σ_e stock(t+1) = Σ_e stock(t), por partícula.
    * ``desigualdad``: menor ≤ mayor, por entidad.
    """
    nombre: str
    tipo: Literal["stock_flujo", "conservacion_global", "stock_global_constante", "desigualdad"]
    stock: Optional[str] = None
    entradas: tuple[str, ...] = ()
    salidas: tuple[str, ...] = ()
    izquierda: tuple[str, ...] = ()
    derecha: tuple[str, ...] = ()
    menor: Optional[str] = None
    mayor: Optional[str] = None
    descripcion: str = Field(min_length=1)

    @model_validator(mode="after")
    def _campos(self):
        t = self.tipo
        if t == "stock_flujo" and (self.stock is None or not (self.entradas or self.salidas)):
            raise ValueError(f"identidad {self.nombre}: stock_flujo requiere stock y flujos")
        if t == "conservacion_global" and not (self.izquierda and self.derecha):
            raise ValueError(f"identidad {self.nombre}: conservacion_global requiere izquierda y derecha")
        if t == "stock_global_constante" and self.stock is None:
            raise ValueError(f"identidad {self.nombre}: requiere stock")
        if t == "desigualdad" and (self.menor is None or self.mayor is None):
            raise ValueError(f"identidad {self.nombre}: desigualdad requiere menor y mayor")
        return self

    def variables(self) -> set[str]:
        vs = set(self.entradas) | set(self.salidas) | set(self.izquierda) | set(self.derecha)
        for v in (self.stock, self.menor, self.mayor):
            if v:
                vs.add(v)
        return vs


class Observable(_Base):
    nombre: str
    variable: str
    reduccion: Literal["suma", "media", "max", "herfindahl", "valor"]
    unidad: str = Field(min_length=1)
    descripcion: str = Field(min_length=1)


class Circuitos(_Base):
    positivos: tuple[str, ...] = ()
    negativos: tuple[str, ...] = ()


class Evidencia(_Base):
    referencias: tuple[str, ...]
    tests_hechos_estilizados: tuple[str, ...] = ()
    test_hindcast: Optional[str] = None
    nota: str = ""


class FichaMecanismo(_Base):
    nombre: str
    ecuacion: str = Field(min_length=1)
    lee: tuple[str, ...]
    escribe: tuple[str, ...] = Field(min_length=1)
    parametros: tuple[str, ...] = ()
    fuentes: tuple[str, ...] = ()
    circuitos: Circuitos
    estructura_no_ergodica: tuple[Literal["metaestabilidad", "refuerzo", "barrera_absorbente"], ...] = ()
    evidencia: Evidencia


class Topologia(_Base):
    tipo: Literal["rejilla", "lista"]
    filas: Optional[int] = Field(None, ge=1)
    columnas: Optional[int] = Field(None, ge=1)
    entidades: Optional[int] = Field(None, ge=1)
    aristas: tuple[tuple[int, int], ...] = ()

    @model_validator(mode="after")
    def _forma(self):
        if self.tipo == "rejilla":
            if self.filas is None or self.columnas is None:
                raise ValueError("rejilla: hacen falta filas y columnas")
            object.__setattr__(self, "entidades", self.filas * self.columnas)
        else:
            if self.entidades is None:
                raise ValueError("lista: hace falta el número de entidades")
            for u, v in self.aristas:
                if not (0 <= u < self.entidades and 0 <= v < self.entidades) or u == v:
                    raise ValueError(f"arista inválida ({u}, {v})")
            if len(set(self.aristas)) != len(self.aristas):
                raise ValueError("aristas repetidas")
        return self


class Observacion(_Base):
    """Modelo de observación (§3.1): lo que registran las fuentes, con error de medida explícito y huecos.

    familia 'lognormal': log y = log x + N(0, sd²); 'normal': y = x + N(0, sd²). ``sd`` es el nombre de un
    parámetro declarado (con su procedencia). ``fraccion_huecos`` describe la degradación de un mundo sintético.
    """
    nombre: str
    variable: str
    entidades: tuple[int, ...]
    familia: Literal["normal", "lognormal"]
    sd: str
    fraccion_huecos: float = Field(0.0, ge=0.0, lt=1.0)
    descripcion: str = Field(min_length=1)


class Ontologia(_Base):
    nombre: str
    descripcion: str
    advertencia: str = ""
    topologia: Topologia
    variables: tuple[Variable, ...]
    parametros: tuple[Parametro, ...]
    fuentes: tuple[FuenteAzar, ...]
    identidades: tuple[Identidad, ...]
    observables: tuple[Observable, ...]
    mecanismos: tuple[FichaMecanismo, ...]
    estado_inicial: FichaMecanismo
    observaciones: tuple[Observacion, ...] = ()

    # ------------------------------------------------------------------ validación cruzada
    @model_validator(mode="after")
    def _coherencia(self):
        errores: list[str] = []
        V = {v.nombre: v for v in self.variables}
        P = {p.nombre: p for p in self.parametros}
        F = {f.nombre: f for f in self.fuentes}
        for coleccion, nombre in ((self.variables, "variable"), (self.parametros, "parámetro"),
                                  (self.fuentes, "fuente"), (self.identidades, "identidad"),
                                  (self.observables, "observable"), (self.mecanismos, "mecanismo")):
            nombres = [x.nombre for x in coleccion]
            dup = {n for n in nombres if nombres.count(n) > 1}
            if dup:
                errores.append(f"{nombre} duplicado: {sorted(dup)}")

        fichas = list(self.mecanismos) + [self.estado_inicial]
        for m in fichas:
            for v in set(m.lee) | set(m.escribe):
                if v not in V:
                    errores.append(f"mecanismo {m.nombre}: variable desconocida {v}")
            for p in m.parametros:
                if p not in P:
                    errores.append(f"mecanismo {m.nombre}: parámetro desconocido {p}")
            for f in m.fuentes:
                if f not in F:
                    errores.append(f"mecanismo {m.nombre}: fuente desconocida {f}")

        for i in self.identidades:
            for v in i.variables():
                if v not in V:
                    errores.append(f"identidad {i.nombre}: variable desconocida {v}")
            if i.tipo == "stock_flujo" and i.stock in V:
                if V[i.stock].tipo != "stock":
                    errores.append(f"identidad {i.nombre}: {i.stock} no es un stock")
                for f in set(i.entradas) | set(i.salidas):
                    if f in V and V[f].tipo != "flujo":
                        errores.append(f"identidad {i.nombre}: {f} no es un flujo")

        for ob in self.observaciones:
            if ob.variable not in V:
                errores.append(f"observación {ob.nombre}: variable desconocida {ob.variable}")
            if ob.sd not in P:
                errores.append(f"observación {ob.nombre}: parámetro de error desconocido {ob.sd}")
            if any(not (0 <= e < self.topologia.entidades) for e in ob.entidades):
                errores.append(f"observación {ob.nombre}: entidad fuera de rango")

        con_identidad = {i.stock for i in self.identidades if i.tipo == "stock_flujo"}
        for v in self.variables:
            if v.tipo == "stock" and v.nombre not in con_identidad:
                errores.append(f"stock {v.nombre} sin identidad stock-flujo (A3)")

        for o in self.observables:
            if o.variable not in V:
                errores.append(f"observable {o.nombre}: variable desconocida {o.variable}")
            elif o.reduccion == "valor" and V[o.variable].ambito != "global":
                errores.append(f"observable {o.nombre}: 'valor' solo para variables globales")

        escritas = set().union(*(m.escribe for m in fichas))
        leidas = set().union(*(m.lee for m in self.mecanismos))
        usadas = leidas | {o.variable for o in self.observables} | {ob.variable for ob in self.observaciones} | set().union(*(i.variables() for i in self.identidades))
        for v in V:
            if v not in escritas:
                errores.append(f"variable {v} no la escribe ningún mecanismo")
            if v not in usadas:
                errores.append(f"variable {v} huérfana: no la lee ningún mecanismo, observable ni identidad")
        # el estado inicial debe escribir todo lo que no es flujo
        for v in self.variables:
            if v.tipo != "flujo" and v.nombre not in self.estado_inicial.escribe:
                errores.append(f"estado inicial no inicializa {v.nombre}")

        usados_p = set().union(*(m.parametros for m in fichas)) | {ob.sd for ob in self.observaciones}
        for p in P:
            if p not in usados_p:
                errores.append(f"parámetro {p} huérfano")
        usadas_f = set().union(*(m.fuentes for m in fichas))
        for f in F:
            if f not in usadas_f:
                errores.append(f"fuente {f} huérfana")
        fuentes_por_mec: dict[str, list[str]] = {}
        for m in fichas:
            for f in m.fuentes:
                fuentes_por_mec.setdefault(f, []).append(m.nombre)
        for f, ms in fuentes_por_mec.items():
            if len(ms) > 1:
                errores.append(f"fuente {f} usada por varios mecanismos {ms}: cada sorteo tiene un solo dueño")
        if errores:
            raise ValueError("Ontología inválida:\n  - " + "\n  - ".join(errores))
        return self

    # ------------------------------------------------------------------ utilidades
    def variable(self, nombre: str) -> Variable:
        for v in self.variables:
            if v.nombre == nombre:
                return v
        raise KeyError(nombre)

    def fuente(self, nombre: str) -> FuenteAzar:
        for f in self.fuentes:
            if f.nombre == nombre:
                return f
        raise KeyError(nombre)

    def huella(self) -> str:
        """sha256 de la forma canónica: identifica la ontología en toda salida."""
        canon = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()
