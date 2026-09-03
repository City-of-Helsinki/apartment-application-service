"""Generate .sanitizerconfig from Django models with PII strategies applied."""

import yaml

from sanitizers.config import build_configuration, PII

conf = build_configuration()

out = yaml.dump(conf, default_flow_style=False, allow_unicode=True, sort_keys=True)
with open("/app/.sanitizerconfig", "w") as handle:
    handle.write(out)
print("Wrote .sanitizerconfig")
print("PII mappings:", sum(len(v) for v in PII.values()))
