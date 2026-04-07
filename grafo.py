import networkx as nx

# ── Dominios ─────────────────────────────────────────────────────────────────

DOMINIOS: list[str] = [
    "Introducción",
    "Subprogramación",
    "Estructuras de control",
    "Estructuras de datos",
    "Recursividad y algoritmos",
]

# ── Conceptos por dominio ─────────────────────────────────────────────────────

CONCEPTOS: dict[str, list[str]] = {
    "Introducción": [
        "Programa",
        "Algoritmo",
        "Intérprete",
        "Compilador",
        "Script",
        "Variable",
        "Literal",
        "Tipo de dato",
        "Tipo de dato básico",
        "Identificador",
        "Operador",
        "Expresión",
        "Asignación",
        "Entrada / Salida",
        "Error sintáctico",
        "Error lógico",
        "Comentario",
        "Prueba del software",
        "Caso de prueba",
        "Bug",
        "Excepción",
        "Depurar",
        "Flujo de ejecución",
        "Indentación",
    ],
    "Subprogramación": [
        "Función",
        "Cabecera de función",
        "Cuerpo de función",
        "Llamada a función",
        "Parámetro",
        "Argumento",
        "Valor de retorno",
        "Ámbito",
        "Variable local",
        "Variable global",
        "Documentación",
        "Importación de funciones",
        "Biblioteca",
    ],
    "Estructuras de control": [
        "Sentencia condicional",
        "Bucle for",
        "Bucle while",
        "break",
        "continue",
        "pass",
        "Iterable",
        "Iterador",
        "Bucle anidado",
        "Expresión de comparación",
        "Expresión booleana",
    ],
    "Estructuras de datos": [
        "Lista",
        "Tupla",
        "Cadena",
        "Conjunto",
        "Array",
        "Registro",
        "Diccionario",
        "Indexación",
        "Slicing",
        "Mutabilidad",
        "Iterabilidad",
        "Conversión de tipos",
        "Copia superficial",
        "Copia profunda",
    ],
    "Recursividad y algoritmos": [
        "Recursividad",
        "Caso base",
        "Caso recursivo",
        "Pila de llamadas",
        "Desbordamiento de recursión",
        "Complejidad algorítmica",
        "Búsqueda lineal",
        "Búsqueda binaria",
        "Método de ordenación",
        "Ordenación burbuja",
        "Ordenación por inserción",
        "Ordenación por selección",
    ],
}

# ── Relaciones entre conceptos ────────────────────────────────────────────────
# Formato: (origen, destino, tipo_relacion)
# Semántica de REQUIERE_PREVIO: para aprender 'origen' hay que dominar 'destino' antes.

TipoRelacion = ["REQUIERE_PREVIO", "ES_CASO_ESPECIAL_DE", "SE_COMBINA_CON"]

RELACIONES: list[tuple[str, str, list]] = [

    # ── TEMA 1: Introducción ──────────────────────────────────────────────────

    # Programa / Algoritmo
    ("Programa",            "Algoritmo",            "REQUIERE_PREVIO"),
    ("Intérprete",          "Programa",              "REQUIERE_PREVIO"),
    ("Compilador",          "Programa",              "REQUIERE_PREVIO"),
    ("Script",              "Programa",              "REQUIERE_PREVIO"),
    ("Flujo de ejecución",  "Programa",              "REQUIERE_PREVIO"),
    ("Indentación",         "Flujo de ejecución",    "REQUIERE_PREVIO"),
    ("Indentación",         "Flujo de ejecución",    "SE_COMBINA_CON"),

    # Tipos y variables
    ("Tipo de dato básico", "Tipo de dato",          "ES_CASO_ESPECIAL_DE"),
    ("Variable",            "Tipo de dato",          "REQUIERE_PREVIO"),
    ("Variable",            "Identificador",         "REQUIERE_PREVIO"),
    ("Literal",             "Tipo de dato",          "REQUIERE_PREVIO"),

    # Expresiones y operadores
    ("Expresión",           "Operador",              "REQUIERE_PREVIO"),
    ("Expresión",           "Variable",              "REQUIERE_PREVIO"),
    ("Expresión",           "Literal",               "REQUIERE_PREVIO"),
    ("Asignación",          "Variable",              "REQUIERE_PREVIO"),
    ("Asignación",          "Expresión",             "REQUIERE_PREVIO"),
    ("Entrada / Salida",    "Variable",              "REQUIERE_PREVIO"),

    # Errores y depuración
    ("Bug",                 "Error lógico",          "REQUIERE_PREVIO"),
    ("Bug",                 "Error sintáctico",      "REQUIERE_PREVIO"),
    ("Excepción",           "Error sintáctico",      "REQUIERE_PREVIO"),
    ("Excepción",           "Error lógico",          "REQUIERE_PREVIO"),
    ("Depurar",             "Bug",                   "REQUIERE_PREVIO"),
    ("Depurar",             "Excepción",             "REQUIERE_PREVIO"),
    ("Excepción",           "Depurar",               "SE_COMBINA_CON"),
    ("Error lógico",        "Depurar",               "SE_COMBINA_CON"),

    # Pruebas
    ("Caso de prueba",      "Algoritmo",             "REQUIERE_PREVIO"),
    ("Prueba del software", "Caso de prueba",        "REQUIERE_PREVIO"),
    ("Prueba del software", "Bug",                   "SE_COMBINA_CON"),

    # ── TEMA 2: Subprogramación ───────────────────────────────────────────────

    ("Función",                 "Algoritmo",          "REQUIERE_PREVIO"),
    ("Función",                 "Variable",           "REQUIERE_PREVIO"),
    ("Función",                 "Indentación",        "REQUIERE_PREVIO"),
    ("Cabecera de función",     "Función",            "ES_CASO_ESPECIAL_DE"),
    ("Cuerpo de función",       "Función",            "ES_CASO_ESPECIAL_DE"),
    ("Llamada a función",       "Función",            "REQUIERE_PREVIO"),
    ("Parámetro",               "Función",            "REQUIERE_PREVIO"),
    ("Parámetro",               "Variable",           "REQUIERE_PREVIO"),
    ("Argumento",               "Llamada a función",  "REQUIERE_PREVIO"),
    ("Argumento",               "Parámetro",          "REQUIERE_PREVIO"),
    ("Valor de retorno",        "Función",            "REQUIERE_PREVIO"),
    ("Ámbito",                  "Función",            "REQUIERE_PREVIO"),
    ("Ámbito",                  "Variable",           "REQUIERE_PREVIO"),
    ("Variable local",          "Ámbito",             "REQUIERE_PREVIO"),
    ("Variable local",          "Variable",           "ES_CASO_ESPECIAL_DE"),
    ("Variable global",         "Ámbito",             "REQUIERE_PREVIO"),
    ("Variable global",         "Variable",           "ES_CASO_ESPECIAL_DE"),
    ("Variable local",          "Variable global",    "SE_COMBINA_CON"),
    ("Documentación",           "Función",            "REQUIERE_PREVIO"),
    ("Biblioteca",              "Función",            "REQUIERE_PREVIO"),
    ("Importación de funciones","Función",            "REQUIERE_PREVIO"),
    ("Importación de funciones","Biblioteca",         "REQUIERE_PREVIO"),

    # ── TEMA 3: Estructuras de control ───────────────────────────────────────

    ("Expresión de comparación","Expresión",               "REQUIERE_PREVIO"),
    ("Expresión de comparación","Operador",                "REQUIERE_PREVIO"),
    ("Expresión booleana",      "Expresión de comparación","REQUIERE_PREVIO"),
    ("Expresión booleana",      "Tipo de dato básico",     "REQUIERE_PREVIO"),
    ("Sentencia condicional",   "Expresión booleana",      "REQUIERE_PREVIO"),
    ("Sentencia condicional",   "Indentación",             "REQUIERE_PREVIO"),
    ("Bucle for",               "Iterable",                "REQUIERE_PREVIO"),
    ("Bucle for",               "Indentación",             "REQUIERE_PREVIO"),
    ("Bucle while",             "Expresión booleana",      "REQUIERE_PREVIO"),
    ("Bucle while",             "Indentación",             "REQUIERE_PREVIO"),
    ("break",                   "Bucle for",               "REQUIERE_PREVIO"),
    ("break",                   "Bucle while",             "REQUIERE_PREVIO"),
    ("continue",                "Bucle for",               "REQUIERE_PREVIO"),
    ("continue",                "Bucle while",             "REQUIERE_PREVIO"),
    ("pass",                    "Sentencia condicional",   "REQUIERE_PREVIO"),
    ("pass",                    "Bucle for",               "REQUIERE_PREVIO"),
    ("pass",                    "Bucle while",             "REQUIERE_PREVIO"),
    ("Iterable",                "Tipo de dato",            "REQUIERE_PREVIO"),
    ("Iterador",                "Iterable",                "REQUIERE_PREVIO"),
    ("Bucle anidado",           "Bucle for",               "REQUIERE_PREVIO"),
    ("Bucle anidado",           "Bucle while",             "REQUIERE_PREVIO"),
    ("Sentencia condicional",   "Bucle for",               "SE_COMBINA_CON"),
    ("Sentencia condicional",   "Bucle while",             "SE_COMBINA_CON"),
    ("Bucle for",               "Bucle while",             "SE_COMBINA_CON"),

    # ── TEMA 4: Estructuras de datos ─────────────────────────────────────────
    # AJUSTE: eliminada ("Lista", "Indexación", "REQUIERE_PREVIO") — ciclo resuelto.
    # Indexación requiere Lista (ya estaba), no al revés.

    ("Lista",               "Variable",              "REQUIERE_PREVIO"),
    ("Lista",               "Tipo de dato",          "REQUIERE_PREVIO"),
    ("Tupla",               "Lista",                 "REQUIERE_PREVIO"),
    ("Tupla",               "Mutabilidad",           "REQUIERE_PREVIO"),
    ("Cadena",              "Tipo de dato básico",   "REQUIERE_PREVIO"),
    ("Cadena",              "Indexación",            "REQUIERE_PREVIO"),
    ("Conjunto",            "Lista",                 "REQUIERE_PREVIO"),
    ("Array",               "Lista",                 "REQUIERE_PREVIO"),
    ("Registro",            "Variable",              "REQUIERE_PREVIO"),
    ("Registro",            "Tipo de dato",          "REQUIERE_PREVIO"),
    ("Diccionario",         "Lista",                 "REQUIERE_PREVIO"),
    ("Diccionario",         "Indexación",            "REQUIERE_PREVIO"),
    ("Indexación",          "Lista",                 "REQUIERE_PREVIO"),   # ← dirección correcta
    ("Indexación",          "Cadena",                "SE_COMBINA_CON"),
    ("Slicing",             "Indexación",            "REQUIERE_PREVIO"),
    ("Mutabilidad",         "Tipo de dato",          "REQUIERE_PREVIO"),
    ("Iterabilidad",        "Iterable",              "REQUIERE_PREVIO"),
    ("Iterabilidad",        "Lista",                 "SE_COMBINA_CON"),
    ("Conversión de tipos", "Tipo de dato básico",   "REQUIERE_PREVIO"),
    ("Copia superficial",   "Lista",                 "REQUIERE_PREVIO"),
    ("Copia superficial",   "Mutabilidad",           "REQUIERE_PREVIO"),
    ("Copia profunda",      "Copia superficial",     "REQUIERE_PREVIO"),
    ("Lista",               "Diccionario",           "SE_COMBINA_CON"),
    ("Lista",               "Conjunto",              "SE_COMBINA_CON"),
    ("Tupla",               "Lista",                 "SE_COMBINA_CON"),

    # ── TEMA 5: Recursividad y algoritmos ────────────────────────────────────

    ("Pila de llamadas",            "Función",             "REQUIERE_PREVIO"),
    ("Pila de llamadas",            "Llamada a función",   "REQUIERE_PREVIO"),
    ("Recursividad",                "Función",             "REQUIERE_PREVIO"),
    ("Recursividad",                "Pila de llamadas",    "REQUIERE_PREVIO"),
    ("Caso base",                   "Recursividad",        "REQUIERE_PREVIO"),
    ("Caso recursivo",              "Recursividad",        "REQUIERE_PREVIO"),
    ("Caso base",                   "Caso recursivo",      "SE_COMBINA_CON"),
    ("Desbordamiento de recursión", "Recursividad",        "REQUIERE_PREVIO"),
    ("Desbordamiento de recursión", "Pila de llamadas",    "REQUIERE_PREVIO"),
    ("Complejidad algorítmica",     "Algoritmo",           "REQUIERE_PREVIO"),
    ("Complejidad algorítmica",     "Método de ordenación","SE_COMBINA_CON"),
    ("Búsqueda lineal",             "Lista",               "REQUIERE_PREVIO"),
    ("Búsqueda lineal",             "Bucle for",           "REQUIERE_PREVIO"),
    ("Búsqueda binaria",            "Búsqueda lineal",     "REQUIERE_PREVIO"),
    ("Búsqueda binaria",            "Método de ordenación","REQUIERE_PREVIO"),
    ("Búsqueda binaria",            "Recursividad",        "SE_COMBINA_CON"),
    ("Método de ordenación",        "Lista",               "REQUIERE_PREVIO"),
    ("Método de ordenación",        "Algoritmo",           "REQUIERE_PREVIO"),
    ("Ordenación burbuja",          "Método de ordenación","ES_CASO_ESPECIAL_DE"),
    ("Ordenación burbuja",          "Bucle anidado",       "REQUIERE_PREVIO"),
    ("Ordenación por inserción",    "Método de ordenación","ES_CASO_ESPECIAL_DE"),
    ("Ordenación por inserción",    "Bucle anidado",       "REQUIERE_PREVIO"),
    ("Ordenación por selección",    "Método de ordenación","ES_CASO_ESPECIAL_DE"),
    ("Ordenación por selección",    "Bucle anidado",       "REQUIERE_PREVIO"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def concepto_dominio() -> dict[str, str]:
    """Devuelve un mapa concepto → dominio."""
    return {c: d for d, cs in CONCEPTOS.items() for c in cs}


def construir_grafo(
    tipos: list[list] | None = None,
) -> nx.DiGraph:
    """
    Construye y devuelve un DiGraph de NetworkX.

    Parámetros
    ----------
    tipos : lista de tipos de relación a incluir.
            Por defecto incluye los tres tipos.
            Ejemplo: construir_grafo(["REQUIERE_PREVIO"]) devuelve solo
            las aristas de prerequisito, útil para calcular el frente
            de aprendizaje.

    Cada arista lleva el atributo 'tipo' con el valor correspondiente.
    Cada nodo lleva el atributo 'dominio'.
    """
    if tipos is None:
        tipos = ["REQUIERE_PREVIO", "ES_CASO_ESPECIAL_DE", "SE_COMBINA_CON"]

    G = nx.DiGraph()

    # Añadir todos los nodos con su dominio
    for dominio, cs in CONCEPTOS.items():
        for c in cs:
            G.add_node(c, dominio=dominio)

    # Añadir aristas filtradas por tipo
    for origen, destino, tipo in RELACIONES:
        if tipo in tipos:
            G.add_edge(origen, destino, tipo=tipo)

    return G


def frente_aprendizaje(
    conceptos_dominados: set[str],
) -> list[str]:
    """
    Devuelve los conceptos desbloqueados pero aún no dominados.

    Un concepto está desbloqueado cuando todos sus prerequisitos directos
    (aristas REQUIERE_PREVIO salientes) están en conceptos_dominados.

    Parámetros
    ----------
    conceptos_dominados : conjunto de conceptos que el estudiante domina.
    """
    G_req = construir_grafo(["REQUIERE_PREVIO"])
    frente = []
    for nodo in G_req.nodes:
        if nodo in conceptos_dominados:
            continue
        prereqs = list(G_req.successors(nodo))
        if not prereqs:
            # Nodo raíz: siempre desbloqueado
            frente.append(nodo)
        elif all(p in conceptos_dominados for p in prereqs):
            frente.append(nodo)
    return sorted(frente)


def casos_especiales(concepto: str) -> list[str]:
    """
    Devuelve los conceptos que son casos especiales de 'concepto'.
    Útil para enriquecer el contexto del prompt de generación.
    """
    G = construir_grafo(["ES_CASO_ESPECIAL_DE"])
    return [n for n, d in G.in_edges(concepto) if
            G[n][concepto]["tipo"] == "ES_CASO_ESPECIAL_DE"]


def combinaciones_naturales(concepto: str) -> list[str]:
    """
    Devuelve los conceptos que se combinan naturalmente con 'concepto'.
    Útil como sugerencia para el LLM que sintetiza el enunciado.
    """
    G = construir_grafo(["SE_COMBINA_CON"])
    vecinos = set(G.successors(concepto)) | set(G.predecessors(concepto))
    return sorted(vecinos)


# ── Validación al importar ────────────────────────────────────────────────────

def _validar():
    G_req = construir_grafo(["REQUIERE_PREVIO"])
    try:
        ciclo = nx.find_cycle(G_req)
        raise ValueError(f"Ciclo detectado en REQUIERE_PREVIO: {ciclo}")
    except nx.NetworkXNoCycle:
        pass  # correcto, el grafo es acíclico


_validar()


# ── Demo / smoke test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    G = construir_grafo()
    print(f"Nodos: {G.number_of_nodes()} | Aristas: {G.number_of_edges()}")

    G_req = construir_grafo(["REQUIERE_PREVIO"])
    print(f"Aristas REQUIERE_PREVIO: {G_req.number_of_edges()}")
    print(f"Aristas ES_CASO_ESPECIAL_DE: {construir_grafo(['ES_CASO_ESPECIAL_DE']).number_of_edges()}")
    print(f"Aristas SE_COMBINA_CON: {construir_grafo(['SE_COMBINA_CON']).number_of_edges()}")
    print()

    dominados = set(CONCEPTOS["Introducción"]) | set(CONCEPTOS["Subprogramación"])
    frente = frente_aprendizaje(dominados)
    print(f"Frente de aprendizaje tras Intro + Subprogramación ({len(frente)} conceptos):")
    for c in frente:
        print(f"  {c}")
    print()

    print("Casos especiales de 'Variable':", casos_especiales("Variable"))
    print("Casos especiales de 'Método de ordenación':", casos_especiales("Método de ordenación"))
    print()
    print("Combinaciones naturales de 'Bucle for':", combinaciones_naturales("Bucle for"))
    print("Combinaciones naturales de 'Lista':", combinaciones_naturales("Lista"))
