"""
Generate the r2SCAN H(P) scan for Al4C3, restarting from the converged PBE
HP scan (hp_curves/Al4C3_<phase>/P<pressure>/) already on disk.

Rationale: VASP's own recommendation for meta-GGA (SCAN/r2SCAN) runs is to
restart from a converged semi-local (GGA) WAVECAR/CHGCAR rather than
starting cold -- meta-GGA SCF convergence is markedly more robust that
way. Since the PBE scan already produced a converged, relaxed structure
*and* WAVECAR/CHGCAR at all 11 pressures for all 7 phases, every r2SCAN
point can be seeded directly from its own same-pressure PBE counterpart:

    hp_curves/Al4C3_<phase>/P<p>/{CONTCAR,POTCAR,WAVECAR,CHGCAR}
      -> hp_curves_r2SCAN/Al4C3_<phase>/P<p>/{POSCAR,POTCAR,WAVECAR,CHGCAR}

This removes the need for the sequential inter-pressure restart chain
used in the PBE scan (gen_hp_runs.py): every point already has its own
independent, high-quality starting guess, so the 11 points of a phase can
in principle run in any order / in parallel. We still group them one
phase per SLURM job (run_chain.sh, one node, 11 points in sequence) to
keep the same submission footprint as the PBE campaign, but there is no
CONTCAR/WAVECAR/CHGCAR copying *between* points anymore.

All DFT parameters (ENCUT, EDIFF, KSPACING, ISIF=8, PSTRESS grid) are
kept identical to the PBE scan so that PBE vs r2SCAN differ by the
functional alone. Meta-GGA-specific flags added: METAGGA=R2scan,
LASPH=.TRUE. (aspherical PAW corrections, required for correct meta-GGA
forces/stress), ADDGRID=.TRUE. (finer real-space grid for the
kinetic-energy-density gradient terms), LMIXTAU=.TRUE. (mix the kinetic
energy density too, needed for stable meta-GGA charge mixing).

This script only writes local files (POSCAR/POTCAR/WAVECAR/CHGCAR/
INCAR.relax/job.sh/run_chain.sh) -- it does NOT submit anything to SLURM.
"""
import os
import shutil

HP_BASE = os.path.dirname(os.path.abspath(__file__))          # hp_curves/
REPO = os.path.dirname(HP_BASE)                                # repo root
R2SCAN_BASE = os.path.join(REPO, "hp_curves_r2SCAN")

PHASES = ["Pnma-VII", "Pbam", "Pnma", "R-3m", "Pnma-III", "anti-CaFe2O4", "I-43d"]
PRESSURES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

INCAR_TMPL = """SYSTEM = Al4C3 {phase} - r2SCAN H(P) scan @ {p} GPa (ISIF=8)

# electronic
PREC    = Accurate
ENCUT   = 600
EDIFF   = 1E-5
ISMEAR  = 0
SIGMA   = 0.05

# meta-GGA: r2SCAN, restarting from the converged PBE WAVECAR/CHGCAR at
# this same pressure (hp_curves/Al4C3_{phase}/P{p}/) -- VASP's recommended
# way to get robust meta-GGA SCF convergence
METAGGA  = R2scan
LASPH    = .TRUE.
ADDGRID  = .TRUE.
LMIXTAU  = .TRUE.
ISTART   = 1
ICHARG   = 1

# k-points (same coarse mesh as the PBE scan, for a like-for-like comparison)
KSPACING = 0.2
KGAMMA   = .TRUE.

# ionic + volume relaxation under external pressure, cell shape fixed
IBRION  = 2
ISIF    = 8
NSW     = 200
EDIFFG  = -0.01
PSTRESS = {pstress:.1f}        ! kBar = {p} GPa

# parallelization (per benchmark: KPAR>1 outperforms NPAR>1 on these
# systems; user-specified KPAR=8, NPAR left at default)
KPAR    = 8

# output
LWAVE   = .TRUE.
LCHARG  = .TRUE.
"""

JOB_TMPL = """#!/bin/sh
# Standalone fallback: run ONLY this pressure point by hand. The normal
# path is Al4C3_{phase}/run_chain.sh (one node, whole 11-point series).
#SBATCH --job-name=r2scan_{phase}_P{p}
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=vasp.log
#SBATCH --time=12:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

cp INCAR.relax INCAR
{{ time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; }} 2>> vasp.log
if ! grep -q "General timing" OUTCAR 2>/dev/null; then
    echo "VASP relax step did not finish cleanly -- aborting" >> vasp.log
    exit 1
fi
"""

RUN_CHAIN_TMPL = """#!/bin/sh
# r2SCAN H(P) scan for Al4C3_{phase}: 11 pressure points, each already
# seeded from its own converged PBE WAVECAR/CHGCAR (no inter-point
# restart needed here, unlike the PBE chain) -- run sequentially on one
# node to keep the same one-job-per-phase submission footprint.
#SBATCH --job-name=r2scan_{phase}
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=r2scan_{phase}.log
#SBATCH --time=96:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

BASE="$SLURM_SUBMIT_DIR"

run_step() {{
    local dir="$1"
    echo "$(date '+%F %T') === starting $dir ==="
    cd "$BASE/$dir" || exit 1
    cp INCAR.relax INCAR
    {{ time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; }} 2>> vasp.log
    if ! grep -q "General timing" OUTCAR 2>/dev/null; then
        echo "$(date '+%F %T') VASP did not finish cleanly in $dir -- aborting chain" >> "$BASE/r2scan_{phase}.log"
        exit 1
    fi
    echo "$(date '+%F %T') === finished $dir ==="
}}

{step_calls}
echo "$(date '+%F %T') === Al4C3_{phase}: r2SCAN 0-100 GPa series done ==="
"""


def make_dir(phase, p):
    src = os.path.join(HP_BASE, f"Al4C3_{phase}", f"P{p}")
    dst = os.path.join(R2SCAN_BASE, f"Al4C3_{phase}", f"P{p}")
    os.makedirs(dst, exist_ok=True)

    for fname, newname in [("CONTCAR", "POSCAR"), ("POTCAR", "POTCAR"),
                            ("WAVECAR", "WAVECAR"), ("CHGCAR", "CHGCAR")]:
        srcf = os.path.join(src, fname)
        if not os.path.isfile(srcf):
            raise FileNotFoundError(f"missing {srcf} -- run the PBE scan for this point first")
        shutil.copy(srcf, os.path.join(dst, newname))

    with open(os.path.join(dst, "INCAR.relax"), "w") as f:
        f.write(INCAR_TMPL.format(phase=phase, p=p, pstress=p * 10.0))

    with open(os.path.join(dst, "job.sh"), "w") as f:
        f.write(JOB_TMPL.format(phase=phase, p=p))
    os.chmod(os.path.join(dst, "job.sh"), 0o755)
    return dst


def main():
    manifest = []
    for phase in PHASES:
        phase_dir = os.path.join(R2SCAN_BASE, f"Al4C3_{phase}")
        for p in PRESSURES:
            make_dir(phase, p)
            manifest.append((phase, p))

        step_calls = "\n".join(f'run_step "P{p}"' for p in PRESSURES)
        with open(os.path.join(phase_dir, "run_chain.sh"), "w") as f:
            f.write(RUN_CHAIN_TMPL.format(phase=phase, step_calls=step_calls))
        os.chmod(os.path.join(phase_dir, "run_chain.sh"), 0o755)

    with open(os.path.join(R2SCAN_BASE, "run_manifest.txt"), "w") as f:
        f.write("phase\tpressure_GPa\tseed_source (PBE, same phase/pressure)\n")
        for phase, p in manifest:
            f.write(f"{phase}\t{p}\thp_curves/Al4C3_{phase}/P{p}\n")

    print(f"Generated {len(manifest)} run directories and {len(PHASES)} run_chain.sh "
          f"(1 SLURM job/node per phase) under {R2SCAN_BASE}.")
    print("Nothing submitted to SLURM -- files only.")


if __name__ == "__main__":
    main()
