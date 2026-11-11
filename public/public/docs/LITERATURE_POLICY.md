# Literature governance — evidence before claims

This is an evolving, **curated** library, not an AI self-rewriting rulebook.

## Lifecycle

- `approved.json`: manually checked studies with bibliographic URLs, short original summaries, evidence type, and tags. It is read by MCP tool `search_training_literature`.
- `candidates.json`: new metadata candidates from manually invoked Crossref lookup, **never used for recommendations**.
- Review each candidate's publication status, DOI, article method, population, outcomes, certainty, limitations, applicability to recreational runners, and whether the summary truly matches the full abstract/article.
- Commit changes via reviewed pull request. Record source, reviewer and date in future versions. Don't claim a live or automatically refreshed evidence base.
- Prefer position statements, consensus, systematic reviews and meta-analyses, but verify whether findings are actually applicable; avoid exclusive reliance on one study.
- Future CI can check dead links/new publications and open an issue/PR; never merge or silently rewrite evidence automatically.

## Initial evidence (verified public links, 2026-11-11)

- TID individual-participant meta-analysis (PMID 39888556): outcomes differ by athlete level; no universal winning model.
- 2024 polarized vs. other TID review: VO2peak benefits do not universally translate into time-trial performance superiority.
- 2024 running economy strength review (PMID 38165636): resistance training may help economy, depending on method and speed.
- Running injury and training parameters review (PMC9528699): heterogeneous evidence; no automatic 10% rule.
- 2025 umbrella review (PMID 40153564): strength tends to help running economy, without guaranteed VO2max improvements.

Copyright: store references and *original short summaries*, not full copyrighted papers.
