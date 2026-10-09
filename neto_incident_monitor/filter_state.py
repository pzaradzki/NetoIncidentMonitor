"""Persist confirmed membership separately from lifetime detection history."""
import copy
import json
from pathlib import Path


class FilterState:
    def __init__(self, path, normalize=lambda url: url):
        self.path = Path(path)
        raw = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.filters = raw.get("filters", {}) if raw.get("version") == 2 else {
            url: {"present": numbers, "ever": numbers, "legacy": True}
            for url, numbers in raw.items()}
        normalized = {}
        for url, state in self.filters.items():
            key = normalize(url)
            current = normalized.setdefault(key, {"present": [], "ever": []})
            for field in ("present", "ever"):
                current[field] = sorted(set(current[field]) | set(state.get(field, [])))
        self.filters = normalized

    def arrivals(self, url, numbers, first_only=False):
        state = self.filters.get(url, {})
        # Legacy data tracked lifetime sightings, not confirmed membership.
        previous = set(state.get("present", []))
        return set(numbers) - set(state.get("ever", [])) if first_only else set(numbers) - previous

    def commit(self, url, numbers):
        updated = copy.deepcopy(self.filters)
        previous = updated.get(url, {})
        updated[url] = {"present": sorted(numbers),
                        "ever": sorted(set(previous.get("ever", [])) | set(numbers))}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"version": 2, "filters": updated}, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        self.filters = updated
