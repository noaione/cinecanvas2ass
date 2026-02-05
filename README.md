# cinecanvas2ass

A converter from [CineCanvas] subtitle XML files to Advanced SubStation Alpha 4+ subtitle files.

Parser is based on the CineCanvas Rev C (or 1.1) specification, which can be found [here][CineCanvas].<br />
Some part might not be fully compliant with the specification, so please report any issues you find.

## Features
- [x] Converts text, font, size, color, position, alignment, and basic styles (bold, italic, underline).
- [x] Supports multiple dialogues with different styles.
- [x] Handles vertical and horizontal text directions.
- [x] Supports custom fonts and sizes.
- [x] Calculates proper positioning based on CineCanvas specifications.
- [ ] Handles ruby text (experimental).

## Usage

### Command Line

After installation, you can use the `cinecanvas2ass` command:

```bash
# Basic usage
cinecanvas2ass input.xml output.ass

# Specify custom resolution
cinecanvas2ass input.xml output.ass --width 1920 --height 1080

# Enable experimental ruby text processing (for Japanese furigana)
cinecanvas2ass input.xml output.ass --ruby-experimental

# Verbose output
cinecanvas2ass input.xml output.ass --verbose
```

Using `uv`:
```bash
uv run cinecanvas2ass input.xml output.ass
```

### Python API

```python
from cinecanvas.conversion import ASSConverter

# Create converter
converter = ASSConverter("input.xml", width=1920, height=1080)

# Enable ruby processing (experimental)
converter.process_ruby = True

# Convert and save
converter.save("output.ass")
```

### Options

- `input`: Input CineCanvas XML file path
- `output`: Output ASS file path
- `-w, --width`: Video width resolution (default: 1920)
- `--height`: Video height resolution (default: 1080)
- `--ruby-experimental`: Enable experimental ruby text processing
- `-v, --verbose`: Enable verbose output

## License

Apache-2.0

[CineCanvas]: https://interop-docs.cinepedia.com/Reference_Documents/CineCanvas(tm)_RevC.pdf
