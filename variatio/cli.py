"""The command line: argument parsing, the build-if-missing policy, and the reporting.

Every `print()` and every exit code of the library lives here. The stages return data and
raise; deciding to build what is missing is this layer's call and never theirs.
"""

import argparse
import json

from loguru import logger

from . import stages
from .core import inference, paths


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for every subcommand."""
    parser = argparse.ArgumentParser(
        prog="variatio",
        description="Knowledge graph-guided generation of educational items: exercises grounded in a curriculum graph.",
    )

    common = argparse.ArgumentParser(add_help=False)

    common.add_argument(
        "--workspace",
        metavar="SLUG",
        required=True, # Required: there is no default workspace
        help="operate on WORKSPACES_DIR/SLUG",
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
    """Add the arguments the generating subcommands share."""
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
    """Parse the `FIELD=VALUE` pins, reading each value as JSON and else as a string.

    Raises ValueError on a pair with no `=`.
    """
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


def _generate_and_report(args: argparse.Namespace, ws) -> None:
    """Initialize the instance, generate what was asked for, and print the result."""
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
    
    # Print each generated item, and its reasoning when the model produced any
    for i, result in enumerate(results, 1):
        print(f"\n============== ITEM {i} · {result.item_type} ==============")
        if result.thinking:
            print("\n-----------------")
            print(f"--- THINKING ---\n{result.thinking}")
            print("-----------------\n")
        print(result.item.model_dump_json(indent=2))



def main(argv: list[str] | None = None) -> int:
    """Run one subcommand and return its exit code."""
    args = build_parser().parse_args(argv)

    ws = paths.workspace(args.workspace)

    try:
        # `restamp-descriptions` calls no model, so it must not demand a live engine.
        if args.command != "restamp-descriptions":
            inference.require_engine()
        
        match args.command:
            case "build":
                built = stages.build_missing(ws)
                if built:
                    logger.success(f"Artifacts built: {', '.join(built)}")
                else:
                    logger.info("Every artifact of the instance already exists")
            case "init":
                stages.initialize(tag=True, ws=ws)
            case "restamp-descriptions":
                changed, total = stages.restamp_descriptions(ws=ws, dry_run=args.dry_run)
                logger.info(f"{changed} of {total} description(s) {'would be rewritten' if args.dry_run else 're-stamped'}")
            case "generate":
                _generate_and_report(args, ws)
            case "all":
                stages.build_missing(ws)
                _generate_and_report(args, ws)
    except stages.MissingArtifactError as e:
        logger.error(f"{e}; run `variatio build` first")
        return 1
    except (RuntimeError, ImportError, OSError, ValueError) as e:
        logger.error(str(e))
        return 1
    return 0