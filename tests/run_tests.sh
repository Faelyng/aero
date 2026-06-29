#!/bin/bash
# Run from the project root so package imports resolve.
cd "$(dirname "$0")/.." || exit 1
python3 -m unittest discover -s tests -v
