import sys

if sys.argv[1:] == ["deps"]:
    # deps runs before the rest of the CLI is imported, so a missing package is reported, not raised.
    import json
    from . import config, deps
    print(json.dumps(deps.report(config.load())))
    sys.exit(0)

from .cli import main
sys.exit(main())
