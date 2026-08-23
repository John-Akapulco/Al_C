#!/bin/bash
# Submit the Al4C3 800eV/0.05 combined PBE+r2SCAN H(P) campaign: one
# SLURM job per phase, each reserving a single node for its entire
# 16-step chain (0-70 GPa, alternating PBE/r2SCAN -- see
# gen_hp_runs_800eV.py). I-43d is dropped from this campaign.
#
# NOT executed automatically -- run manually after review:
#   cd hp_curves_800eV && ./submit_chain.sh | tee submitted_ids.txt

set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PHASES=(Fd-3m Pnma-III Pnma Pnma-VII R-3m Pbam anti-CaFe2O4)

for phase in "${PHASES[@]}"; do
    pdir="$BASE/Al4C3_${phase}"
    jid=$(cd "$pdir" && sbatch run_chain.sh | awk '{print $4}')
    echo -e "${phase}\t${jid}"
done
