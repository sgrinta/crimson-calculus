#!/bin/zsh
# Finder launcher for an already-configured local project.
cd -- "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]]; then
    print "The Python environment is missing. Follow the Run locally steps in README.md first."
    read -r "?Press Return to close this window."
    exit 1
fi
.venv/bin/python scripts/launch_app.py
launcher_exit=$?
if (( launcher_exit != 0 )); then
    read -r "?Press Return to close this window."
fi
exit "$launcher_exit"
