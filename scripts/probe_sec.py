#!/usr/bin/env python3
"""One-off check: can GitHub's servers reach Wikidata, and how much company data does it hold? Prints counts only."""
import json, urllib.parse, urllib.request
UA = "FuturesRadar/1.0 (https://github.com/876lab/futures-radar; 876lab@users.noreply.github.com)"
def q(sparql):
    u = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(sparql)
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)["results"]["bindings"]
base = "?c p:P414 ?s . ?s ps:P414 ?ex ; pq:P249 ?t . VALUES ?ex { wd:Q13677 wd:Q82059 } "
for prop, label in [("P2295", "net profit"), ("P2139", "revenue"), ("P2137", "equity"), ("P2403", "total assets"), ("P3362", "operating income")]:
    for y in (2022, 2023, 2024, 2025):
        try:
            rows = q(f"SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE {{ {base} ?c p:{prop} ?v . ?v pq:P585 ?d . FILTER(YEAR(?d)={y}) }}")
            print(label, y, rows[0]["n"]["value"])
        except Exception as e:
            print("ERR", label, y, e)
rows = q(f"SELECT ?t ?d ?val WHERE {{ {base} FILTER(?t IN ('AAPL','KO','NVDA')) ?c p:P2295 ?v . ?v ps:P2295 ?val ; pq:P585 ?d . }} ORDER BY ?t ?d")
for r in rows[-15:]: print(r["t"]["value"], r["d"]["value"][:10], r["val"]["value"])
