import argparse
import json

from loguru import logger

from . import bootstrap, config, stages
from .core import paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="variant-generator",
        description="Knowledge graph-guided generation of educational items: exercises grounded in a curriculum graph.",
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--workspace",
        metavar="SLUG",
        help="operate on WORKSPACES_DIR/SLUG instead of WORKSPACES_DIR/default",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "build", parents=[common], help="build the missing instance artifacts from the workspace's raw/"
    )
    subparsers.add_parser(
        "init", parents=[common], help="load the instance, tag the exemplars bank and warm the indices"
    )

    restamp = subparsers.add_parser(
        "restamp-descriptions",
        parents=[common],
        help="re-stamp the description fingerprints against the current graph, keeping every text",
    )
    restamp.add_argument(
        "--dry-run",
        action="store_true",
        help="only count how many descriptions the current graph would rewrite",
    )

    generate = subparsers.add_parser(
        "generate", parents=[common], help="initialize, then generate new items"
    )
    _add_generation_args(generate)

    run_all = subparsers.add_parser(
        "all", parents=[common], help="build what is missing, then initialize and generate"
    )
    _add_generation_args(run_all)

    return parser


def _add_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-n", type=int, default=2, help="number of items to generate")
    parser.add_argument(
        "--concepts",
        nargs="+",
        metavar="CONCEPT",
        help="target concepts (default: most frequent tags in the bank)",
    )
    parser.add_argument(
        "--item-type",
        metavar="TYPE",
        help="modality to generate, as declared in the exemplars profile (default: the first one)",
    )
    parser.add_argument(
        "--fixed",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="fix a schema field to a value; repeatable",
    )
    parser.add_argument(
        "--curriculum",
        nargs="+",
        metavar="CONCEPT",
        help="restrict generation to this concept set",
    )
    parser.add_argument(
        "--instructions",
        metavar="TEXT",
        help="free-text request for this batch (screened by the guardrail model before use)",
    )


def _parse_fixed(pairs: list[str]) -> dict[str, object]:
    fixed: dict[str, object] = {}
    for pair in pairs:
        field, sep, value = pair.partition("=")
        if not sep or not field:
            raise ValueError(f"--fixed expects FIELD=VALUE, got: {pair!r}")
        try:
            fixed[field] = json.loads(value)
        except json.JSONDecodeError:
            fixed[field] = value
    return fixed


def _report(results: list) -> None:
    for i, result in enumerate(results, 1):
        print(f"\n============== ITEM {i} · {result.item_type} ==============")
        print(result.item.model_dump_json(indent=2))
        if result.thinking:
            print(f"\n--- thinking ---\n{result.thinking}")


def _generate_and_report(args: argparse.Namespace, ws) -> None:
    context = stages.initialize(tag=True, ws=ws)
    results = stages.generate(
        context,
        concepts=args.concepts,
        item_type=args.item_type,
        n=args.n,
        fixed=_parse_fixed(args.fixed),
        curriculum=args.curriculum,
        instructions=args.instructions,
    )
    _report(results)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    ws = paths.workspace(args.workspace)

    try:
        if args.command != "restamp-descriptions":
            bootstrap()
        if args.command == "build":
            built = stages.build_missing(ws)
            if built:
                logger.success(f"Artefactos construidos: {', '.join(built)}")
            else:
                logger.info("Todos los artefactos de la instancia ya existen")
        elif args.command == "init":
            stages.initialize(tag=True, ws=ws)
        elif args.command == "restamp-descriptions":
            changed, total = stages.restamp_descriptions(ws=ws, dry_run=args.dry_run)
            print(f"{changed} de {total} descripción(es) {'se reescribirían' if args.dry_run else 'reselladas'}")
        elif args.command == "generate":
            _generate_and_report(args, ws)
        elif args.command == "all":
            stages.build_missing(ws)
            _generate_and_report(args, ws)
    except stages.MissingArtifactError as e:
        logger.error(f"{e}; ejecuta antes `variant-generator build`")
        return 1
    except (RuntimeError, ImportError, OSError, ValueError) as e:
        logger.error(str(e))
        return 1
    return 0