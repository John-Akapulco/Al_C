"""
Generate the directory tree for the third Al4C3 H(P) campaign: a combined
PBE+r2SCAN scan at higher precision (ENCUT=800 eV, KSPACING=0.05, vs.
600 eV/0.2 in the first two campaigns), 0-70 GPa every 10 GPa, for the 7
phases still in play (I-43d dropped: its r2SCAN chain kept crashing at
P40 with numerical instabilities at the coarser settings and was not
worth chasing at this precision).

Unlike the earlier campaigns (independent PBE chain, then a separate
r2SCAN chain seeded fresh from each PBE point), this one is a SINGLE
linear chain per phase, alternating PBE and r2SCAN at each pressure and
always restarting (ISTART=1, ICHARG=1: WAVECAR+CHGCAR) from whatever the
immediately preceding step produced, plus its CONTCAR as the new POSCAR:

  P0_PBE -> P0_r2SCAN -> P10_PBE -> P10_r2SCAN -> ... -> P70_PBE -> P70_r2SCAN

Only P0_PBE has no predecessor: it is seeded from the best converged
structure already on hand for that phase, the r2SCAN@0GPa CONTCAR from
the previous (600 eV/0.2) campaign (hp_curves_r2SCAN/Al4C3_<phase>/P0/),
re-relaxed here from scratch electronically at the new ENCUT/KSPACING.

One SLURM node is reserved per phase for the whole 16-step chain, same
footprint as the earlier campaigns.
"""
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)

PHASES = ["Fd-3m", "Pnma-III", "Pnma", "Pnma-VII", "R-3m", "Pbam", "anti-CaFe2O4"]

PRESSURES = [0, 10, 20, 30, 40, 50, 60, 70]

# every step of every phase's chain, in execution order, as (label, method)
STEPS = [(p, method) for p in PRESSURES for method in ("PBE", "r2SCAN")]

PBE_TMPL = """SYSTEM = Al4C3 {phase} - 800eV/0.05 H(P) scan @ {p} GPa, PBE (ISIF=8)

# electronic
PREC    = Accurate
ENCUT   = 800
EDIFF   = 1E-5
ISMEAR  = 0
SIGMA   = 0.05

# k-points (finer mesh than the 600 eV/0.2 campaigns)
KSPACING = 0.05
KGAMMA   = .TRUE.

# ionic + volume relaxation under external pressure, cell shape fixed
IBRION  = 2
ISIF    = 8
NSW     = 200
EDIFFG  = -0.01
PSTRESS = {pstress:.1f}        ! kBar = {p} GPa

# electronic restart from the immediately preceding step in this chain
# (WAVECAR/CHGCAR copied by run_chain.sh); P0_PBE has no predecessor
{istart_block}
# parallelization (per earlier benchmark: KPAR>1 outperforms NPAR>1)
KPAR    = 8

# output -- WAVECAR/CHGCAR kept so the *next* step in the chain can
# restart from them (ISTART=1, ICHARG=1)
LWAVE   = .TRUE.
LCHARG  = .TRUE.
"""

R2SCAN_TMPL = """SYSTEM = Al4C3 {phase} - 800eV/0.05 H(P) scan @ {p} GPa, r2SCAN (ISIF=8)

# electronic
PREC    = Accurate
ENCUT   = 800
EDIFF   = 1E-5
ISMEAR  = 0
SIGMA   = 0.05

# meta-GGA: r2SCAN, restarting from the PBE WAVECAR/CHGCAR at this same
# pressure (previous step in the chain) -- VASP's recommended way to get
# robust meta-GGA SCF convergence
METAGGA  = R2scan
LASPH    = .TRUE.
ADDGRID  = .TRUE.
LMIXTAU  = .TRUE.
ISTART   = 1
ICHARG   = 1

# k-points (same finer mesh as the PBE step, for a like-for-like comparison)
KSPACING = 0.05
KGAMMA   = .TRUE.

# ionic + volume relaxation under external pressure, cell shape fixed
IBRION  = 2
ISIF    = 8
NSW     = 200
EDIFFG  = -0.01
PSTRESS = {pstress:.1f}        ! kBar = {p} GPa

# parallelization (per earlier benchmark: KPAR>1 outperforms NPAR>1)
KPAR    = 8

# output
LWAVE   = .TRUE.
LCHARG  = .TRUE.
"""

RUN_CHAIN_TMPL = """#!/bin/sh
# 800eV/0.05 combined PBE+r2SCAN H(P) chain for Al4C3_{phase}: 0-70 GPa
# every 10 GPa, alternating PBE/r2SCAN at each pressure, each step
# restarting from the immediately preceding one (WAVECAR+CHGCAR+CONTCAR),
# except P0_PBE which is seeded from the earlier 600eV/0.2 r2SCAN@0GPa
# CONTCAR. See gen_hp_runs_800eV.py for the full scheme.
#SBATCH --job-name=hires_{phase}
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=hires_{phase}.log
#SBATCH --time=240:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

BASE="$SLURM_SUBMIT_DIR"

run_step() {{
    local dir="$1" prev="$2"
    echo "$(date '+%F %T') === starting $dir (prev=${{prev:-none}}) ==="
    cd "$BASE/$dir" || exit 1
    if [ -n "$prev" ]; then
        cp "../$prev/CONTCAR" POSCAR
        cp "../$prev/WAVECAR" WAVECAR
        cp "../$prev/CHGCAR" CHGCAR
    fi
    cp INCAR.relax INCAR
    {{ time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; }} 2>> vasp.log
    if ! grep -q "General timing" OUTCAR 2>/dev/null; then
        echo "$(date '+%F %T') VASP did not finish cleanly in $dir -- aborting chain" >> "$BASE/hires_{phase}.log"
        exit 1
    fi
    echo "$(date '+%F %T') === finished $dir ==="
}}

{step_calls}
echo "$(date '+%F %T') === Al4C3_{phase}: 800eV/0.05 PBE+r2SCAN 0-70 GPa chain done ==="
"""


def make_incar(phase, p, method, has_prev):
    if method == "PBE":
        istart_block = "ISTART  = 1\nICHARG  = 1\n" if has_prev else "ISTART  = 0\n"
        return PBE_TMPL.format(phase=phase, p=p, pstress=p * 10.0, istart_block=istart_block)
    else:
        return R2SCAN_TMPL.format(phase=phase, p=p, pstress=p * 10.0)


def main():
    manifest = []
    for phase in PHASES:
        phase_dir = os.path.join(BASE, f"Al4C3_{phase}")
        seed_src = os.path.join(REPO, "hp_curves_r2SCAN", f"Al4C3_{phase}", "P0")

        sequence = []  # (label, prev_label)
        prev_label = None
        for p, method in STEPS:
            label = f"P{p}_{method}"
            rdir = os.path.join(phase_dir, label)
            os.makedirs(rdir, exist_ok=True)

            has_prev = prev_label is not None
            with open(os.path.join(rdir, "INCAR.relax"), "w") as f:
                f.write(make_incar(phase, p, method, has_prev))

            shutil.copy(os.path.join(seed_src, "POTCAR"), os.path.join(rdir, "POTCAR"))
            if label == "P0_PBE":
                shutil.copy(os.path.join(seed_src, "CONTCAR"), os.path.join(rdir, "POSCAR"))

            sequence.append((label, prev_label))
            manifest.append((phase, p, method, prev_label))
            prev_label = label

        step_calls = "\n".join(
            f'run_step "{label}" "{prev if prev is not None else ""}"'
            for label, prev in sequence
        )
        with open(os.path.join(phase_dir, "run_chain.sh"), "w") as f:
            f.write(RUN_CHAIN_TMPL.format(phase=phase, step_calls=step_calls))
        os.chmod(os.path.join(phase_dir, "run_chain.sh"), 0o755)

    with open(os.path.join(BASE, "run_manifest.txt"), "w") as f:
        f.write("phase\tpressure_GPa\tmethod\tdepends_on_step\n")
        for phase, p, method, prev in manifest:
            f.write(f"{phase}\t{p}\t{method}\t{prev if prev else '-'}\n")

    print(f"Generated {len(manifest)} run directories across {len(PHASES)} phases "
          f"({len(STEPS)} steps/phase, 0-70 GPa, ENCUT=800, KSPACING=0.05).")


if __name__ == "__main__":
    main()
