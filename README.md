# sokuhou-collector

Collects publicly available official information and normalizes it to JSON.
Each source is one module under `sokuhou/sources/` that exposes `parse()` (pure, tested against saved snapshots) and `collect()` (one polite HTTP request).

| Source | Module | Notes |
|---|---|---|
| Otsu City fire dispatch | `sokuhou.sources.otsu_fire` | The page lists only the latest ~10 incidents, so history must be accumulated by the caller. |
| Otsu City black-bear sightings | `sokuhou.sources.otsu_bear` | Google My Maps KML published by the city. Cross-checked against the city's own per-year counts. Terms of programmatic access to the KML endpoint are not yet confirmed. |
| jGrants subsidies open for application | `sokuhou.sources.jgrants` | Official public API, no authentication. |

```
python -m sokuhou.sources.otsu_fire
python -m sokuhou.sources.jgrants
python -m unittest discover -s tests -t .
```

Data is taken from the public pages of the respective organizations. This project is not affiliated with them.
Information may be delayed or incomplete; always check the official source.
