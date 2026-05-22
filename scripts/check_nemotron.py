"""Probe the Foundry Local catalog (SDK 1.1.0) for the Nemotron Speech Streaming model."""
from foundry_local_sdk import Configuration, FoundryLocalManager

TARGET_ID = "nemotron-speech-streaming-en-0.6b-generic-cpu:3"
TARGET_ALIAS = "nemotron-speech-streaming-en-0.6b"

cfg = Configuration(app_name="fl-nemotron-probe")
FoundryLocalManager.initialize(cfg)
mgr = FoundryLocalManager.instance

models = mgr.catalog.list_models()
print(f"TOTAL MODELS IN CATALOG: {len(models)}")

hits = []
for x in models:
    alias = (getattr(x, "alias", "") or "").lower()
    mid = (getattr(x, "id", "") or getattr(x, "model_id", "") or "").lower()
    name = (getattr(x, "name", "") or "").lower()
    if any(k in alias or k in mid or k in name for k in ("nemotron", "speech", "0.6b")):
        hits.append(x)

print(f"NEMOTRON/SPEECH/0.6B MATCHES: {len(hits)}")
for x in hits:
    attrs = {k: getattr(x, k, None) for k in ("alias", "id", "model_id", "name", "task", "publisher", "license", "size_in_bytes", "device_type", "runtime", "variants")}
    print(f"  -> {attrs}")

print("---")
print(f"get_model({TARGET_ALIAS!r}):", mgr.catalog.get_model(TARGET_ALIAS))
print(f"get_model({TARGET_ID!r}):  ", mgr.catalog.get_model(TARGET_ID))

print("---")
print("Sample of first 5 model aliases:")
for x in models[:5]:
    print(f"  alias={getattr(x,'alias',None)!r}  id={getattr(x,'id',None)!r}  name={getattr(x,'name',None)!r}")
