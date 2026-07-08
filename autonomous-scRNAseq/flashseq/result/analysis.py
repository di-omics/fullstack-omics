"""Generate the downstream single-cell analysis script (protocol section 12.12).

Protocol 12.12 hands the UMI count matrices off to Seurat (R) or scanpy (python) but
gives no analysis parameters. This produces a runnable scanpy stub that assembles the
per-cell umi_tools count matrices into an AnnData and runs a standard single-cell
workflow (QC filter, normalize, HVG, PCA, neighbors, Leiden, UMAP, marker genes).

External dependency (not bundled): scanpy. The analysis parameters come from
protocol_params.yaml `analysis.downstream` and are EXPERT DEFAULTS, not protocol values.
"""

from __future__ import annotations

from pathlib import Path

from ..params import Params


def generate_scanpy_analysis(p: Params) -> str:
    d = p.protocol["analysis"].get("downstream", {})
    min_genes = d.get("min_genes_per_cell", 200)
    min_cells = d.get("min_cells_per_gene", 3)
    max_mito = d.get("max_pct_mito", 20)
    n_hvg = d.get("n_top_hvg", 2000)
    n_pcs = d.get("n_pcs", 30)
    res = d.get("leiden_resolution", 1.0)

    return f'''#!/usr/bin/env python3
"""flashseq_analysis.py -- FLASH-seq UMI downstream analysis (protocol section 12.12).

Loads the per-cell umi_tools count matrices (FEATURECOUNTS/*.umi.counts.tsv.gz) into a
single AnnData and runs a standard scanpy workflow to a clustered UMAP + marker genes.

RESEARCH USE ONLY -- not clinically validated. Author: di.
EXTERNAL DEPENDENCY: scanpy (pip install scanpy). Parameters below are EXPERT DEFAULTS,
not protocol values (protocol 12.12 gives none). Tune them for your data.
"""
import glob
import os
import sys

try:
    import scanpy as sc
    import pandas as pd
    import anndata as ad
except ImportError:
    sys.exit("[flashseq] Missing dependency: scanpy/pandas/anndata. `pip install scanpy`.")

# ---- Parameters (expert defaults; NOT from the protocol) --------------------
COUNTS_GLOB = os.environ.get("COUNTS_GLOB", "FEATURECOUNTS/*.umi.counts.tsv.gz")
OUT_H5AD = os.environ.get("OUT_H5AD", "flashseq.analyzed.h5ad")
MIN_GENES_PER_CELL = {min_genes}
MIN_CELLS_PER_GENE = {min_cells}
MAX_PCT_MITO = {max_mito}
N_TOP_HVG = {n_hvg}
N_PCS = {n_pcs}
LEIDEN_RESOLUTION = {res}


def load_counts(pattern):
    """Assemble per-cell umi_tools count TSVs (columns: gene, count) into cells x genes."""
    files = sorted(glob.glob(pattern))
    if not files:
        sys.exit(f"[flashseq] No count matrices matched {{pattern}}. Run flashseq_pipeline.sh first.")
    series = {{}}
    for f in files:
        cell_id = os.path.basename(f).split(".umi.counts")[0]
        df = pd.read_csv(f, sep="\\t")
        # umi_tools count output: a 'gene' column and a 'count' column.
        gene_col = "gene" if "gene" in df.columns else df.columns[0]
        count_col = "count" if "count" in df.columns else df.columns[-1]
        series[cell_id] = df.set_index(gene_col)[count_col]
    mat = pd.DataFrame(series).fillna(0).T  # cells (rows) x genes (cols)
    return ad.AnnData(mat)


def main():
    adata = load_counts(COUNTS_GLOB)
    print(f"[flashseq] Loaded {{adata.n_obs}} cells x {{adata.n_vars}} genes")

    # QC filter
    sc.pp.filter_cells(adata, min_genes=MIN_GENES_PER_CELL)
    sc.pp.filter_genes(adata, min_cells=MIN_CELLS_PER_GENE)
    adata.var["mito"] = adata.var_names.str.upper().str.startswith(("MT-", "MT."))
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mito"], inplace=True, percent_top=None)
    adata = adata[adata.obs["pct_counts_mito"] < MAX_PCT_MITO].copy()
    print(f"[flashseq] After QC: {{adata.n_obs}} cells x {{adata.n_vars}} genes")

    # Normalize + log
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)

    # HVG, scale, PCA, neighbors, cluster, UMAP
    sc.pp.highly_variable_genes(adata, n_top_genes=N_TOP_HVG)
    adata.raw = adata
    adata = adata[:, adata.var["highly_variable"]].copy()
    sc.pp.scale(adata, max_value=10)
    sc.tl.pca(adata, n_comps=min(N_PCS, adata.n_obs - 1, adata.n_vars - 1))
    sc.pp.neighbors(adata, n_pcs=min(N_PCS, adata.n_obs - 1))
    sc.tl.leiden(adata, resolution=LEIDEN_RESOLUTION)
    sc.tl.umap(adata)
    sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon")

    adata.write(OUT_H5AD)
    print(f"[flashseq] Wrote {{OUT_H5AD}} with {{adata.obs['leiden'].nunique()}} clusters.")


if __name__ == "__main__":
    main()
'''


def write_analysis(p: Params, out_dir: Path | str) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = out / "flashseq_analysis.py"
    script.write_text(generate_scanpy_analysis(p), encoding="utf-8")
    script.chmod(0o755)
    return {"analysis": str(script)}
