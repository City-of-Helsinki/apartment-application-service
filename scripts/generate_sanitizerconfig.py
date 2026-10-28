"""
Generate .sanitizerconfig from Django models with PII strategies applied.

Run with: ./manage.py shell < scripts/generate_sanitizerconfig.py
"""

from pathlib import Path

import yaml
from django.conf import settings

from sanitizers.config import build_configuration, PII

config_path = Path(settings.BASE_DIR) / ".sanitizerconfig"
conf = build_configuration()

out = yaml.dump(conf, default_flow_style=False, allow_unicode=True, sort_keys=True)
config_path.write_text(out)
print(f"Wrote {config_path}")
print("PII mappings:", sum(len(v) for v in PII.values()))
