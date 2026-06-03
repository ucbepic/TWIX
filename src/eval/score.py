"""eval.md §2 — combine NodeMatchF1, ContentScore, StructureScore.

Two-level alignment: records first (§3.0), then nodes within each matched
record pair (§3.1–3.2). Stage 2 (code-gen loop) calls `score()` directly.
"""

from __future__ import annotations

import json
from pathlib import Path

from .align import align, align_records
from .content import content_similarity
from .convert import to_eval_format


W_NODE = 0.40
W_CONTENT = 0.40
W_STRUCT = 0.20


def _pr_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    if tp == 0:
        p = 0.0 if (tp + fp) else 1.0
        r = 0.0 if (tp + fn) else 1.0
        return p, r, (0.0 if (p + r) == 0 else 2 * p * r / (p + r))
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return p, r, (0.0 if (p + r) == 0 else 2 * p * r / (p + r))


def validate_tree(tree: dict) -> list[str]:
    """Return list of validation errors for the ground-truth pages/blocks format. Empty = ok."""
    errors = []
    if not isinstance(tree, dict):
        return ["root is not an object"]
    pages = tree.get("pages")
    if not isinstance(pages, list):
        errors.append("`pages` is not a list")
        return errors
    if len(pages) == 0:
        errors.append("`pages` is empty")
    seen_block_ids: set = set()
    for pi, page in enumerate(pages):
        if not isinstance(page, dict):
            errors.append(f"pages[{pi}] is not an object")
            continue
        if "page" not in page:
            errors.append(f"pages[{pi}] missing `page`")
        blocks = page.get("blocks")
        if not isinstance(blocks, list):
            errors.append(f"pages[{pi}] `blocks` is not a list")
            continue
        for bi, block in enumerate(blocks):
            if not isinstance(block, dict):
                errors.append(f"pages[{pi}].blocks[{bi}] is not an object")
                continue
            for k in ("type", "block_id", "data"):
                if k not in block:
                    errors.append(f"pages[{pi}].blocks[{bi}] missing field `{k}`")
            block_type = block.get("type")
            if block_type not in ("table", "kv"):
                errors.append(
                    f"pages[{pi}].blocks[{bi}] type={block_type!r} not in {{table, kv}}"
                )
            bid = block.get("block_id")
            if bid in seen_block_ids:
                errors.append(f"pages[{pi}].blocks[{bi}] duplicate block_id {bid!r}")
            seen_block_ids.add(bid)
            data = block.get("data")
            if block_type == "table":
                if not isinstance(data, list):
                    errors.append(f"pages[{pi}].blocks[{bi}] table `data` is not a list")
                else:
                    for ri, row in enumerate(data):
                        if not isinstance(row, dict):
                            errors.append(
                                f"pages[{pi}].blocks[{bi}].data[{ri}] is not a dict"
                            )
            elif block_type == "kv":
                if not isinstance(data, (dict, list)):
                    errors.append(
                        f"pages[{pi}].blocks[{bi}] kv `data` is not a dict or list"
                    )
    return errors


# --------------------------------------------------------------------------- #
# Path utilities for content_diffs
# --------------------------------------------------------------------------- #

def _table_diffs_to_entries(g_node: dict, c_node: dict, table_diag: dict) -> list[dict]:
    out = []
    g_rows = (g_node.get("content") or {}).get("rows") or []
    c_rows = (c_node.get("content") or {}).get("rows") or []
    for hd in table_diag.get("header_diffs", []):
        reason = "R-HEADER-ORDER" if hd.get("reason") == "R-HEADER-ORDER" else "R-HEADER-DIFFERS"
        out.append({
            "gold_id": g_node.get("id"),
            "candidate_id": c_node.get("id"),
            "type": "table",
            "field": "headers",
            "gold": hd.get("gold"),
            "candidate": hd.get("candidate"),
            "reason": reason,
        })
    for cd in table_diag.get("cell_diffs", []):
        gri = cd.get("g_row")
        hdr = cd.get("header")
        path = f"rows[{gri}].{hdr}" if hdr else f"rows[{gri}]"
        out.append({
            "gold_id": g_node.get("id"),
            "candidate_id": c_node.get("id"),
            "type": "table",
            "field": path,
            "gold": cd.get("gold"),
            "candidate": cd.get("candidate"),
            "reason": cd.get("reason", "R-CELL-DIFFERS"),
        })
    for ri in table_diag.get("missing_rows", []):
        out.append({
            "gold_id": g_node.get("id"),
            "candidate_id": c_node.get("id"),
            "type": "table",
            "field": f"rows[{ri}]",
            "gold": g_rows[ri] if ri < len(g_rows) else None,
            "candidate": None,
            "reason": "R-ROW-MISSING",
        })
    for rj in table_diag.get("extra_rows", []):
        out.append({
            "gold_id": g_node.get("id"),
            "candidate_id": c_node.get("id"),
            "type": "table",
            "field": f"rows[{rj}](candidate)",
            "gold": None,
            "candidate": c_rows[rj] if rj < len(c_rows) else None,
            "reason": "R-ROW-EXTRA",
        })
    return out


def _kv_diffs_to_entries(g_node: dict, c_node: dict, diag: dict) -> list[dict]:
    return [
        {
            "gold_id": g_node.get("id"),
            "candidate_id": c_node.get("id"),
            "type": "key_value",
            "field": d.get("field"),
            "gold": d.get("gold"),
            "candidate": d.get("candidate"),
            "reason": d.get("reason"),
        }
        for d in diag.get("diffs", [])
    ]


def _metadata_diffs_to_entries(g_node: dict, c_node: dict, diag: dict) -> list[dict]:
    return [
        {
            "gold_id": g_node.get("id"),
            "candidate_id": c_node.get("id"),
            "type": "metadata",
            "field": d.get("field"),
            "gold": d.get("gold"),
            "candidate": d.get("candidate"),
            "reason": d.get("reason"),
        }
        for d in diag.get("diffs", [])
    ]


# --------------------------------------------------------------------------- #
# Top-level scoring
# --------------------------------------------------------------------------- #

def score(
    gold: dict,
    candidate: dict,
    reference: str = "agent",
    threshold: float = 0.9,
) -> dict:
    """Return the eval.json shape per eval.md §7.1."""
    if reference not in ("agent", "human"):
        reference = "agent"

    gold = to_eval_format(gold)
    candidate = to_eval_format(candidate)

    gold_records = list(gold.get("records") or [])
    cand_records = list(candidate.get("records") or [])

    # --- Record-level alignment (§3.0) ---
    rec_alignment = align_records(gold_records, cand_records)
    rec_pairs = rec_alignment["pairs"]          # (g_idx, c_idx, record_sim)
    missing_gold_rec_idxs = rec_alignment["missing_gold"]
    extra_cand_rec_idxs = rec_alignment["extra_candidate"]

    # RecordMatchF1 (diagnostic — does not enter headline accuracy).
    rec_tp = len(rec_pairs)
    rec_fn = len(missing_gold_rec_idxs)
    rec_fp = len(extra_cand_rec_idxs)
    if gold_records == [] and cand_records == []:
        rec_p, rec_r, rec_f1 = 1.0, 1.0, 1.0
    else:
        rec_p, rec_r, rec_f1 = _pr_f1(rec_tp, rec_fp, rec_fn)

    record_alignment_info = []
    missing_gold_records_info = []
    extra_cand_records_info = []

    for gi in missing_gold_rec_idxs:
        g_rec = gold_records[gi]
        missing_gold_records_info.append({
            "gold_record_id": g_rec.get("record_id", f"r{gi+1}"),
            "reason": "R-RECORD-MISSING",
        })
    for ci in extra_cand_rec_idxs:
        c_rec = cand_records[ci]
        extra_cand_records_info.append({
            "candidate_record_id": c_rec.get("record_id", f"r{ci+1}"),
            "reason": "R-RECORD-EXTRA",
        })

    # --- Node-level scoring aggregated across matched record pairs ---
    total_g_nodes = 0
    total_c_nodes = 0
    total_typed_tp = 0
    total_untyped_tp = 0

    type_matched_sims: list[float] = []
    by_type_sums: dict = {"table": [], "key_value": [], "metadata": []}

    content_diffs: list[dict] = []
    type_mismatch_entries: list[dict] = []
    alignment_records_out: list[dict] = []
    missing_entries: list[dict] = []
    extra_entries: list[dict] = []

    total_edge_correct = 0
    total_edge_total = 0
    total_pairs_correct = 0
    total_pairs_total = 0
    total_note_match = 0
    total_note_total = 0
    all_structure_diffs: list[dict] = []

    from .structure import structure_score

    for gi, ci, rec_sim_val in rec_pairs:
        g_rec = gold_records[gi]
        c_rec = cand_records[ci]
        g_rid = g_rec.get("record_id", f"r{gi+1}")
        c_rid = c_rec.get("record_id", f"r{ci+1}")

        g_nodes = list(g_rec.get("nodes") or [])
        c_nodes = list(c_rec.get("nodes") or [])

        total_g_nodes += len(g_nodes)
        total_c_nodes += len(c_nodes)

        node_alignment = align(g_nodes, c_nodes)
        pairs = node_alignment["pairs"]
        missing_gold_nodes = node_alignment["missing_gold"]
        extra_cand_nodes = node_alignment["extra_candidate"]

        total_typed_tp += sum(1 for p in pairs if p[3] == 1.0)
        total_untyped_tp += len(pairs)

        for g_idx, c_idx, sim, type_match, content_sim, content_diag in pairs:
            g_node = g_nodes[g_idx]
            c_node = c_nodes[c_idx]
            alignment_records_out.append({
                "gold_record_id": g_rid,
                "candidate_record_id": c_rid,
                "gold_id": g_node.get("id"),
                "candidate_id": c_node.get("id"),
                "type_match": bool(type_match == 1.0),
                "content_sim": round(float(content_sim), 6),
            })
            if type_match == 1.0:
                type_matched_sims.append(content_sim)
                t = g_node.get("type")
                if t in by_type_sums:
                    by_type_sums[t].append(content_sim)
                def _tag(entries, gr=g_rid, cr=c_rid):
                    for e in entries:
                        e["gold_record_id"] = gr
                        e["candidate_record_id"] = cr
                    return entries
                if t == "table":
                    content_diffs.extend(_tag(_table_diffs_to_entries(g_node, c_node, content_diag)))
                elif t == "key_value":
                    content_diffs.extend(_tag(_kv_diffs_to_entries(g_node, c_node, content_diag)))
                elif t == "metadata":
                    content_diffs.extend(_tag(_metadata_diffs_to_entries(g_node, c_node, content_diag)))
            else:
                type_matched_sims.append(0.0)
                type_mismatch_entries.append({
                    "gold_record_id": g_rid,
                    "candidate_record_id": c_rid,
                    "gold_id": g_node.get("id"),
                    "candidate_id": c_node.get("id"),
                    "type": "type_mismatch",
                    "field": "type",
                    "gold": g_node.get("type"),
                    "candidate": c_node.get("type"),
                    "reason": "R-TYPE-MISMATCH",
                })

        closest_for_missing = node_alignment.get("closest_for_missing", {})
        for gi_n in missing_gold_nodes:
            gn = g_nodes[gi_n]
            best_j, best_s = closest_for_missing.get(gi_n, (-1, 0.0))
            missing_entries.append({
                "gold_record_id": g_rid,
                "gold_id": gn.get("id"),
                "type": gn.get("type"),
                "closest_candidate_id": c_nodes[best_j].get("id") if best_j >= 0 else None,
                "closest_similarity": round(float(best_s), 4),
                "reason": "R-NODE-UNALIGNED",
            })
        for cj_n in extra_cand_nodes:
            cn = c_nodes[cj_n]
            extra_entries.append({
                "candidate_record_id": c_rid,
                "candidate_id": cn.get("id"),
                "type": cn.get("type"),
                "reason": "R-NODE-EXTRA",
            })

        struct = structure_score(g_nodes, c_nodes, node_alignment)
        for sd in struct["structure_diffs"]:
            sd["gold_record_id"] = g_rid
            sd["candidate_record_id"] = c_rid
        all_structure_diffs.extend(struct["structure_diffs"])
        total_edge_correct += struct["_edge_correct"]
        total_edge_total += struct["_edge_total"]
        total_pairs_correct += struct["_pairs_correct"]
        total_pairs_total += struct["_pairs_total"]
        total_note_match += struct["_note_match"]
        total_note_total += struct["_note_total"]

        record_alignment_info.append({
            "gold_record_id": g_rid,
            "candidate_record_id": c_rid,
            "record_sim": round(float(rec_sim_val), 6),
        })

    # Nodes from missing gold records → FN (with reason R-RECORD-MISSING)
    for gi in missing_gold_rec_idxs:
        g_rec = gold_records[gi]
        g_rid = g_rec.get("record_id", f"r{gi+1}")
        for gn in list(g_rec.get("nodes") or []):
            total_g_nodes += 1
            missing_entries.append({
                "gold_record_id": g_rid,
                "gold_id": gn.get("id"),
                "type": gn.get("type"),
                "closest_candidate_id": None,
                "closest_similarity": 0.0,
                "reason": "R-RECORD-MISSING",
            })

    # Nodes from extra candidate records → FP (with reason R-RECORD-EXTRA)
    for ci in extra_cand_rec_idxs:
        c_rec = cand_records[ci]
        c_rid = c_rec.get("record_id", f"r{ci+1}")
        for cn in list(c_rec.get("nodes") or []):
            total_c_nodes += 1
            extra_entries.append({
                "candidate_record_id": c_rid,
                "candidate_id": cn.get("id"),
                "type": cn.get("type"),
                "reason": "R-RECORD-EXTRA",
            })

    # NodeMatchF1.
    typed_tp = total_typed_tp
    typed_fp = total_c_nodes - typed_tp
    typed_fn = total_g_nodes - typed_tp
    untyped_tp = total_untyped_tp
    untyped_fp = total_c_nodes - untyped_tp
    untyped_fn = total_g_nodes - untyped_tp

    if total_g_nodes == 0 and total_c_nodes == 0:
        typed_p = typed_r = typed_f = 1.0
        untyped_p = untyped_r = untyped_f = 1.0
    else:
        typed_p, typed_r, typed_f = _pr_f1(typed_tp, typed_fp, typed_fn)
        untyped_p, untyped_r, untyped_f = _pr_f1(untyped_tp, untyped_fp, untyped_fn)

    # ContentScore.
    if type_matched_sims:
        content_overall = sum(type_matched_sims) / len(type_matched_sims)
    elif total_g_nodes == 0 and total_c_nodes == 0:
        content_overall = 1.0
    else:
        content_overall = 0.0
    by_type_means = {
        k: (sum(vs) / len(vs) if vs else None) for k, vs in by_type_sums.items()
    }

    # StructureScore (micro-aggregated across all matched record pairs).
    edge_accuracy = (total_edge_correct / total_edge_total) if total_edge_total else (
        1.0 if total_g_nodes == 0 else 0.0
    )
    path_accuracy = (total_pairs_correct / total_pairs_total) if total_pairs_total else 1.0
    note_agreement_rate = (total_note_match / total_note_total) if total_note_total else 1.0

    accuracy = max(0.0, min(1.0,
        W_NODE * typed_f + W_CONTENT * content_overall + W_STRUCT * edge_accuracy
    ))

    exact_match = (
        abs(accuracy - 1.0) < 1e-9
        and not missing_entries
        and not extra_entries
        and not content_diffs
        and not all_structure_diffs
        and not type_mismatch_entries
        and not missing_gold_records_info
        and not extra_cand_records_info
    )

    candidate_id = "code" if (candidate.get("model") or "").lower().startswith("code") else "agent"
    if reference == "agent" and candidate_id == "agent":
        candidate_id = "code"

    return {
        "doc_name": gold.get("doc_name") or candidate.get("doc_name", ""),
        "reference": reference,
        "candidate": candidate_id,
        "reference_model": gold.get("model"),
        "candidate_model": candidate.get("model"),
        "exact_match": bool(exact_match),
        "accuracy": round(float(accuracy), 6),
        "components": {
            "RecordMatchF1": {
                "typed_f1": round(rec_f1, 6),
                "precision": round(rec_p, 6),
                "recall": round(rec_r, 6),
            },
            "NodeMatchF1": {
                "typed_f1": round(typed_f, 6),
                "untyped_f1": round(untyped_f, 6),
                "precision": round(typed_p, 6),
                "recall": round(typed_r, 6),
                "untyped_precision": round(untyped_p, 6),
                "untyped_recall": round(untyped_r, 6),
            },
            "ContentScore": {
                "overall": round(float(content_overall), 6),
                "by_type": {
                    k: (round(float(v), 6) if v is not None else None)
                    for k, v in by_type_means.items()
                },
            },
            "StructureScore": {
                "edge_accuracy": round(float(edge_accuracy), 6),
                "path_accuracy": round(float(path_accuracy), 6),
                "note_agreement_rate": round(float(note_agreement_rate), 6),
            },
        },
        "weights": {"NodeMatchF1": W_NODE, "ContentScore": W_CONTENT, "StructureScore": W_STRUCT},
        "threshold": threshold,
        "record_alignment": record_alignment_info,
        "missing_gold_records": missing_gold_records_info,
        "extra_candidate_records": extra_cand_records_info,
        "alignment": alignment_records_out,
        "missing_gold_nodes": missing_entries,
        "extra_candidate_nodes": extra_entries,
        "type_mismatches": type_mismatch_entries,
        "content_diffs": content_diffs,
        "structure_diffs": all_structure_diffs,
    }


def score_paths(
    gold_path: str | Path,
    candidate_path: str | Path,
    reference: str = "agent",
    threshold: float = 0.9,
) -> dict:
    g = json.loads(Path(gold_path).read_text())
    c = json.loads(Path(candidate_path).read_text())
    return score(g, c, reference=reference, threshold=threshold)
