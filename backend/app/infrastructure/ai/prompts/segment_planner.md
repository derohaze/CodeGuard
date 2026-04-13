Prompt module: segment_planner

Use this module when turning repository artifacts into file, block, and path work units.

- Preserve coverage intent from the selected scan mode.
- Prefer block segmentation that keeps security-relevant context intact.
- Keep exposed routes, auth boundaries, service layers, and sink-adjacent blocks near the front of the queue.
- In deep scans, avoid dropping lower-level blocks that could complete the trust-boundary path.
- In fast scans, sample aggressively but explain the tradeoff.
