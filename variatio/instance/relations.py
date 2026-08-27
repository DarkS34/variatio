from dataclasses import dataclass

# The two slot names of a triple, and the words that frame a catalogue entry. They exist
# here rather than in the prompts because a relation's `definition` and `reading` are
# written using them, so the schema and its rendering cannot be in different languages.
# The prose of the KG prompts uses the same two words: `es/knowledge_graph.py` says
# ORIGEN → DESTINO and `en/knowledge_graph.py` says SOURCE → TARGET.
CATALOG_WORDS: dict[str, dict[str, str]] = {
    "es": {
        "source": "ORIGEN",
        "target": "DESTINO",
        "reading": "Lectura",
        "direction": "Dirección",
        "directed": "dirigida — ORIGEN y DESTINO no son intercambiables.",
        "symmetric": "simétrica — el orden de ORIGEN y DESTINO da igual.",
        "examples": "Ejemplos",
    },
    "en": {
        "source": "SOURCE",
        "target": "TARGET",
        "reading": "Reading",
        "direction": "Direction",
        "directed": "directed — SOURCE and TARGET are not interchangeable.",
        "symmetric": "symmetric — the order of SOURCE and TARGET does not matter.",
        "examples": "Examples",
    },
}


@dataclass(frozen=True)
class RelationType:
    key: str
    verbose: str
    definition: str
    reading: str = ""
    examples: tuple[tuple[str, str], ...] = ()
    directed: bool = True
    acyclic: bool = False
    use_in_embedding: bool = True

    def __post_init__(self):
        if not self.key or self.key.split() != [self.key]:
            raise ValueError(f"Relation key must be a single whitespace-free token: {self.key!r}")
        if not self.verbose:
            raise ValueError(f"Relation '{self.key}' needs a verbose label")
        if not self.definition:
            raise ValueError(f"Relation '{self.key}' needs a definition (it is shown to the model)")
        object.__setattr__(self, "examples", tuple(tuple(pair) for pair in self.examples))

    def details(self) -> dict:
        return {
            "verbose": self.verbose,
            "directed": self.directed,
            "acyclic": self.acyclic,
            "use_in_embedding": self.use_in_embedding,
        }

    # The scaffolding of the catalogue entry, per language. It lives here and not in the
    # prompts because the DEFINITIONS interpolated below are written in the schema's own
    # language and name its own slots: an English definition under a «Lectura:» heading,
    # next to ORIGEN and DESTINO, is the exact mismatch that kept `RELATION_SCHEMA_EN`
    # unselectable until now.
    def catalog_entry(self, language: str = "es") -> str:
        words = CATALOG_WORDS[language]
        lines = [f"- `{self.key}` — {self.definition}"]
        if self.reading:
            lines.append(f'  {words["reading"]}: "{self.reading}".')
        lines.append(
            f"  {words['direction']}: "
            + (words["directed"] if self.directed else words["symmetric"])
        )
        if self.examples:
            lines.append(f"  {words['examples']}:")
            lines.extend(f'    · ["{s}", "{self.key}", "{t}"]' for s, t in self.examples)
        return "\n".join(lines)


@dataclass(frozen=True)
class RelationSchema:
    types: tuple[RelationType, ...]
    fallback: str | None = None
    prerequisite: str | None = None
    # Which language its definitions, readings and slot names are written in. It decides how
    # `catalog_block` renders, so a schema and the prompt set that interpolates it always
    # agree — `derived` resolves both from the workspace's own `prompt_language`.
    language: str = "es"

    def __post_init__(self):
        object.__setattr__(self, "types", tuple(self.types))
        if self.language not in CATALOG_WORDS:
            raise ValueError(f"Unknown relation-schema language: {self.language!r}")
        if not self.types:
            raise ValueError("A relation schema needs at least one relation type")
        keys = [relation.key for relation in self.types]
        duplicated = {key for key in keys if keys.count(key) > 1}
        if duplicated:
            raise ValueError(f"Duplicated relation key(s): {', '.join(sorted(duplicated))}")
        for label, pointer in (("fallback", self.fallback), ("prerequisite", self.prerequisite)):
            if pointer is not None and pointer not in keys:
                raise ValueError(
                    f"{label} '{pointer}' is not one of the declared keys: {', '.join(keys)}"
                )

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(relation.key for relation in self.types)

    def __iter__(self):
        return iter(self.types)

    def __len__(self) -> int:
        return len(self.types)

    def __contains__(self, key: object) -> bool:
        return key in self.keys

    def __getitem__(self, key: str) -> RelationType:
        for relation in self.types:
            if relation.key == key:
                return relation
        raise KeyError(key)

    def get(self, key: str) -> RelationType | None:
        return next((relation for relation in self.types if relation.key == key), None)

    def by_verbose(self, verbose: str) -> RelationType | None:
        return next((relation for relation in self.types if relation.verbose == verbose), None)

    @property
    def prerequisite_verbose(self) -> str | None:
        return None if self.prerequisite is None else self[self.prerequisite].verbose

    def specific_keys(self) -> tuple[str, ...]:
        return tuple(key for key in self.keys if key != self.fallback)

    def catalog_block(self) -> str:
        return "\n".join(relation.catalog_entry(self.language) for relation in self.types)

    @property
    def source_slot(self) -> str:
        return CATALOG_WORDS[self.language]["source"]

    @property
    def target_slot(self) -> str:
        return CATALOG_WORDS[self.language]["target"]

    def key_list(self) -> str:
        return ", ".join(f'"{key}"' for key in self.keys)


# Selected by a workspace whose `prompt_language` is `en`. Its scaffolding is rendered from
# `CATALOG_WORDS["en"]`, so the definitions below — which name SOURCE and TARGET — come out
# under English headings and beside the English prompt set that interpolates them.
#
# Note what this does NOT change: the `verbose` labels are what the loader indexes a graph
# by, so they are baked into `knowledge_graph.json` at build time. A workspace's language is
# therefore chosen when it is created and not afterwards.
RELATION_SCHEMA_EN = RelationSchema(
    language="en",
    fallback="related_to",
    prerequisite="prerequisite",
    types=(
        RelationType(
            key="prerequisite",
            verbose="has as a prerequisite",
            definition=(
                "the SOURCE presupposes or needs the TARGET: the TARGET must be mastered "
                "BEFORE the SOURCE. It states teaching order, never containment — if the "
                "SOURCE is a case or a component of the TARGET, this is not the relation."
            ),
            reading="to learn SOURCE you must first know TARGET",
            examples=(
                ("Binary search", "Sorted list"),
                ("Multiplication", "Addition"),
                ("Integral calculus", "Derivatives"),
            ),
            directed=True,
            acyclic=True,
            use_in_embedding=False,
        ),
        RelationType(
            key="falls_under",
            verbose="falls under",
            definition=(
                "the SOURCE falls under the TARGET: it is a type, a case or a component of "
                "it, and the TARGET is the category or the whole that subsumes it. Do not "
                "agonise over type versus part — what matters is the direction, from the "
                "specific to the general, between two DISTINCT concepts."
            ),
            reading="SOURCE is a kind or a part of TARGET",
            examples=(
                ("Equilateral triangle", "Triangle"),
                ("Nucleus", "Cell"),
                ("Sonnet", "Poem"),
                ("Chorus", "Song"),
            ),
            directed=True,
            acyclic=False,
            use_in_embedding=True,
        ),
        RelationType(
            key="related_to",
            verbose="is related to",
            definition=(
                "a genuine semantic association that does not cleanly fit any of the types "
                "above. It is the last resort: never use it to restate a fact another "
                "relation already expresses between the same two concepts."
            ),
            reading="SOURCE and TARGET are semantically associated",
            examples=(
                ("Supply", "Demand"),
                ("Photosynthesis", "Cellular respiration"),
            ),
            directed=False,
            acyclic=False,
            use_in_embedding=True,
        ),
    ),
)


# Spanish counterpart, and the one `config.KG_RELATION_SCHEMA` selects. Every field is
# Spanish now: `key`, `verbose` and `examples` because they surface in the output, and
# `definition` and `reading` because the KG prompts that interpolate them are Spanish too.
# ORIGEN/DESTINO are the slot names `catalog_entry` and those prompts use; they must agree.
RELATION_SCHEMA_ES = RelationSchema(
    language="es",
    fallback="relacionado",
    prerequisite="prerrequisito",
    types=(
        RelationType(
            key="prerrequisito",
            verbose="tiene como prerrequisito",
            definition=(
                "el ORIGEN presupone o necesita el DESTINO: el DESTINO debe dominarse "
                "ANTES que el ORIGEN. Expresa orden de aprendizaje, nunca pertenencia — "
                "si el ORIGEN es un caso o un componente del DESTINO, la relación no es esta."
            ),
            reading="para aprender ORIGEN hay que saber antes DESTINO",
            examples=(
                ("Búsqueda binaria", "Lista ordenada"),
                ("Multiplicación", "Suma"),
                ("Cálculo integral", "Derivadas"),
            ),
            directed=True,
            acyclic=True,
            use_in_embedding=False,
        ),
        RelationType(
            key="se_engloba_en",
            verbose="se engloba en",
            definition=(
                "el ORIGEN se engloba en el DESTINO: es un tipo, un caso o un componente "
                "suyo, y el DESTINO es la categoría o el todo que lo abarca. No te "
                "detengas en si es tipo o parte — lo que importa es la dirección, de lo "
                "concreto a lo general, entre dos conceptos DISTINTOS."
            ),
            reading="ORIGEN es un tipo o una parte de DESTINO",
            examples=(
                ("Triángulo equilátero", "Triángulo"),
                ("Núcleo", "Célula"),
                ("Soneto", "Poema"),
                ("Estribillo", "Canción"),
            ),
            directed=True,
            acyclic=False,
            use_in_embedding=True,
        ),
        RelationType(
            key="relacionado",
            verbose="se relaciona con",
            definition=(
                "una asociación semántica genuina que no encaja limpiamente en ninguno de "
                "los tipos anteriores. Es el último recurso: nunca la uses para repetir un "
                "hecho que otra relación ya expresa entre los mismos dos conceptos."
            ),
            reading="ORIGEN y DESTINO están asociados semánticamente",
            examples=(
                ("Oferta", "Demanda"),
                ("Fotosíntesis", "Respiración celular"),
            ),
            directed=False,
            acyclic=False,
            use_in_embedding=True,
        ),
    ),
)


BUILTIN_SCHEMAS = {
    "en": RELATION_SCHEMA_EN,
    "es": RELATION_SCHEMA_ES,
}

# Keyed by the same codes `core.languages` declares, because a workspace's prompt language
# is what selects the schema: the definitions it interpolates are prose, and prose in one
# language under a prompt written in another is the mismatch this pairing removes.
RELATION_SCHEMAS = BUILTIN_SCHEMAS


def schema_for(language: str | None) -> RelationSchema:
    return BUILTIN_SCHEMAS.get(str(language or ""), RELATION_SCHEMA_ES)
