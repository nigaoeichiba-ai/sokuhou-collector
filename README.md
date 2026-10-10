# sokuhou-collector

Collects publicly available official information and normalizes it to JSON.
Each source is one module under `sokuhou/sources/` that exposes `parse()` (pure, tested against saved snapshots) and `collect()` (one polite HTTP request).

| Source | Module | Notes |
|---|---|---|
| Otsu City fire dispatch | `sokuhou.sources.otsu_fire` | The page lists only the latest ~10 incidents, so history must be accumulated by the caller. |
| Otsu City black-bear sightings (counts only) | `sokuhou.sources.otsu_kuma` | The city's own page (dated headings only; robots.txt checked). The city states no licence, so only municipality, month, count and latest date are stored, like every source without an explicit licence. |
| MHLW regional minimum wages | `sokuhou.sources.mhlw_minwage` | Reads the history workbook linked from the MHLW page. Raises unless all 47 prefectures and the weighted average are present. Source terms: Public Data License v1.0 (attribution required; state that the data was processed). |
| jGrants subsidies open for application | `sokuhou.sources.jgrants` | Official public API, no authentication. |

```
python -m sokuhou.sources.otsu_fire
python -m sokuhou.sources.jgrants
python -m unittest discover -s tests -t .
```

Data is taken from the public pages of the respective organizations. This project is not affiliated with them.
Information may be delayed or incomplete; always check the official source.
