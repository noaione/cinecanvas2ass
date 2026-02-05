"""
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cinecanvas.conversion import ASSConverter


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="cinecanvas2ass",
        description="Convert CineCanvas XML subtitle files to ASS format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.xml output.ass
  %(prog)s input.xml output.ass --width 1920 --height 1080
  %(prog)s input.xml output.ass --ruby-experimental
        """,
    )

    parser.add_argument(
        "input",
        type=str,
        help="Input CineCanvas XML file path",
    )

    parser.add_argument(
        "output",
        type=str,
        help="Output ASS file path",
    )

    parser.add_argument(
        "-w",
        "--width",
        type=int,
        default=1920,
        help="Video width resolution (default: 1920)",
    )

    parser.add_argument(
        "--height",
        type=int,
        default=1080,
        help="Video height resolution (default: 1080)",
    )

    parser.add_argument(
        "--ruby-experimental",
        action="store_true",
        help="Enable experimental ruby text processing (for Japanese furigana)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file '{args.input}' does not exist", file=sys.stderr)
        sys.exit(1)

    if not input_path.is_file():
        print(f"Error: Input path '{args.input}' is not a file", file=sys.stderr)
        sys.exit(1)

    # Validate output path
    output_path = Path(args.output)
    if output_path.exists() and not output_path.is_file():
        print(f"Error: Output path '{args.output}' exists but is not a file", file=sys.stderr)
        sys.exit(1)

    # Create parent directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        print(f"Input file: {input_path}")
        print(f"Output file: {output_path}")
        print(f"Resolution: {args.width}x{args.height}")
        print(f"Ruby processing: {'enabled' if args.ruby_experimental else 'disabled'}")
        print()

    try:
        # Create converter
        if args.verbose:
            print("Loading CineCanvas XML file...")

        converter = ASSConverter(input_path, width=args.width, height=args.height)

        # Enable ruby processing if requested
        if args.ruby_experimental:
            converter.process_ruby = True
            if args.verbose:
                print("Ruby text processing enabled (experimental)")

        # Convert and save
        if args.verbose:
            print("Converting to ASS format...")

        converter.save(output_path)

        if args.verbose:
            print("✓ Conversion complete!")
        else:
            print(f"Successfully converted '{input_path.name}' to '{output_path.name}'")

    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
