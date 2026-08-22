from dataclasses import dataclass


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

    def catalog_entry(self) -> str:
        lines = [f"- `{self.key}` — {self.definition}"]
        if self.reading:
            lines.append(f'  Lectura: "{self.reading}".')
        lines.append(
            "  Dirección: "
            + (
                "dirigida — ORIGEN y DESTINO no son intercambiables."
                if self.directed
                else "simétrica — el orden de ORIGEN y DESTINO da igual."
            )
        )
        if self.examples:
            lines.append("  Ejemplos:")
            lines.extend(f'    · ["{s}", "{self.key}", "{t}"]' for s, t in self.examples)
        return "\n".join(lines)


@dataclass(frozen=True)
class RelationSchema:
    types: tuple[RelationType, ...]
    fallback: str | None = None
    prerequisite: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "types", tuple(self.types))
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
        return "\n".join(relation.catalog_entry() for relation in self.types)

    def key_list(self) -> str:
        return ", ".join(f'"{key}"' for key in self.keys)


# Nothing selects this schema: `config.KG_RELATION_SCHEMA` is `es` and must stay so. Since
# the KG prompts became Spanish, `catalog_entry` renders its scaffolding in Spanish, so an
# English `definition` would come out under a «Lectura:»/«Dirección:» heading and next to
# ORIGEN/DESTINO. Selecting `en` means translating the slot names here first.
RELATION_SCHEMA_EN = RelationSchema(
    fallback="related_to",
    prerequisite="prerequisite",
    types=(
        RelationType(
            key="prerequisite",
            verbose="has as a prerequisite",
            definition=(
                "the SOURCE presupposes or needs the TARGET; the TARGET must be mastered "
                "BEFORE the SOURCE."
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
            key="is_a",
            verbose="is a kind of",
            definition="the SOURCE is a TYPE, case or subclass of the TARGET.",
            reading="SOURCE is a kind of TARGET",
            examples=(
                ("Whale", "Mammal"),
                ("Sonnet", "Poem"),
                ("Equilateral triangle", "Triangle"),
            ),
            directed=True,
            acyclic=False,
            use_in_embedding=True,
        ),
        RelationType(
            key="part_of",
            verbose="is part of",
            definition=(
                "the SOURCE is a COMPONENT of the TARGET; the TARGET is the whole that contains it."
            ),
            reading="SOURCE is part of TARGET",
            examples=(
                ("Nucleus", "Cell"),
                ("Chorus", "Song"),
                ("Engine", "Car"),
            ),
            directed=True,
            acyclic=False,
            use_in_embedding=True,
        ),
        RelationType(
            key="related_to",
            verbose="is related to",
            definition=(
                "a genuine semantic association that does not cleanly fit any of the types above."
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
    fallback="relacionado",
    prerequisite="prerrequisito",
    types=(
        RelationType(
            key="prerrequisito",
            verbose="tiene como prerrequisito",
            definition=(
                "el ORIGEN presupone o necesita el DESTINO; el DESTINO debe dominarse "
                "ANTES que el ORIGEN."
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
            key="es_un",
            verbose="es un tipo de",
            definition="el ORIGEN es un TIPO, caso o subclase del DESTINO.",
            reading="ORIGEN es un tipo de DESTINO",
            examples=(
                ("Ballena", "Mamífero"),
                ("Soneto", "Poema"),
                ("Triángulo equilátero", "Triángulo"),
            ),
            directed=True,
            acyclic=False,
            use_in_embedding=True,
        ),
        RelationType(
            key="parte_de",
            verbose="es parte de",
            definition=(
                "el ORIGEN es un COMPONENTE del DESTINO; el DESTINO es el todo que lo contiene."
            ),
            reading="ORIGEN es parte de DESTINO",
            examples=(
                ("Núcleo", "Célula"),
                ("Estribillo", "Canción"),
                ("Motor", "Automóvil"),
            ),
            directed=True,
            acyclic=False,
            use_in_embedding=True,
        ),
        RelationType(
            key="relacionado",
            verbose="se relaciona con",
            definition=(
                "una asociación semántica genuina que no encaja limpiamente en ninguno de los "
                "tipos anteriores."
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
