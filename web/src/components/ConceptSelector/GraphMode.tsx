import { useMemo } from "react";

import { GraphCanvas } from "@/features/kg/GraphCanvas";
import { buildModel } from "@/features/kg/graph/model";
import type { GraphView } from "@/lib/types";
import { cn } from "@/lib/utils";

export function GraphMode({
  graph,
  offered,
  chosen,
  implied,
  onToggle,
  onAdd,
}: {
  graph: GraphView;
  offered: Set<string>;
  chosen: Set<string>;
  implied?: Set<string>;
  onToggle: (concept: string) => void;
  onAdd: (concepts: string[]) => void;
}) {
  const model = useMemo(() => buildModel(graph), [graph]);

  const bands = useMemo(() => {
    const rows = Array.from({ length: model.levelCount }, (_, level) => ({
      level,
      total: 0,
      chosen: 0,
      upTo: [] as string[],
    }));
    graph.nodes.forEach(([name, , nonTaggable], index) => {
      if (nonTaggable || !offered.has(name)) return;
      const level = model.levels[index] ?? 0;
      const row = rows[level];
      if (!row) return;
      row.total += 1;
      if (chosen.has(name)) row.chosen += 1;
      for (let above = level; above < rows.length; above += 1) rows[above].upTo.push(name);
    });
    return rows;
  }, [graph, model, offered, chosen]);

  const picked = useMemo(() => {
    const names = new Set(chosen);
    if (implied) for (const name of implied) names.add(name);
    return names;
  }, [chosen, implied]);

  const shallow = model.levelCount < 3;

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-border px-4 py-2 sm:px-6">
        <div className="mx-auto flex max-w-[110rem] flex-wrap items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Niveles de prerrequisito
          </span>
          {bands.map((band) => (
            <div
              key={band.level}
              className="flex items-center gap-1.5 rounded-md border border-border bg-card px-2 py-1 text-xs"
            >
              <span className="font-semibold">N{band.level}</span>
              <span
                className={cn(
                  "tabular-nums",
                  band.chosen > 0 ? "font-medium text-primary" : "text-muted-foreground",
                )}
              >
                {band.chosen}/{band.total}
              </span>
              <button
                type="button"
                disabled={band.upTo.length === 0}
                onClick={() => onAdd(band.upTo)}
                title={`Elegir todos los conceptos que se enseñan hasta el nivel ${band.level}`}
                className="rounded px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-40 disabled:hover:bg-transparent"
              >
                hasta aquí
              </button>
            </div>
          ))}
        </div>
        {shallow ? (
          <p className="mx-auto mt-2 max-w-[110rem] text-xs text-[var(--warning)]">
            El grafo declara {model.curriculumEdges} relación(es) de prerrequisito para{" "}
            {graph.nodes.length} conceptos, así que casi todo cae en el nivel 0 y las bandas
            distinguen poco.
          </p>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 p-4 sm:px-6">
        <GraphCanvas
          graph={graph}
          selected={null}
          onSelect={() => {}}
          picked={picked}
          onPick={onToggle}
          initialMode={model.curriculumEdges > 0 ? "curriculum" : "force"}
          highlight={offered}
        />
      </div>
    </div>
  );
}
