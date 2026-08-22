"""
Collect H(P) results from the Al4C3 enthalpy-vs-pressure scan.

Walks hp_curves/Al4C3_<phase>/P<pressure>/OUTCAR, extracts the converged
enthalpy H = E + P*V (VASP prints it directly as "enthalpy is  TOTEN"
when PSTRESS != 0) and the atom count, and writes a per-phase .dat file
(pressure_GPa, H_per_fu_eV) suitable for \\addplot table in pgfplots, plus
a combined results_hp.csv.

Run this after the SLURM chains (submit_chain.sh) have completed, or at
any point to see partial results for the branches already converged.
"""
import csv
import os
import re
import glob

BASE = os.path.dirname(os.path.abspath(__file__))
ATOMS_PER_FU = 7  # Al4C3 = 4 Al + 3 C

PRESSURES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

# VASP only prints "enthalpy is  TOTEN" when PSTRESS != 0 (i.e. not at the
# P=0 GPa endpoint); there H = E, read from the plain "free  energy  TOTEN"
# line instead (last occurrence = converged ionic step).
ENTHALPY_RE = re.compile(r"enthalpy is\s+TOTEN\s*=\s*([-\d.]+)\s*eV")
FREE_ENERGY_RE = re.compile(r"free  energy   TOTEN\s*=\s*([-\d.]+)\s*eV")


def natoms_from_poscar(path):
    with open(path) as f:
        lines = f.readlines()
    return sum(int(x) for x in lines[6].split())


def read_result(rundir):
    outcar = os.path.join(rundir, "OUTCAR")
    if not os.path.isfile(outcar):
        return None
    with open(outcar, errors="ignore") as f:
        text = f.read()
    converged = "reached required accuracy" in text
    matches = ENTHALPY_RE.findall(text)
    if matches:
        h_total = float(matches[-1])
    else:
        matches = FREE_ENERGY_RE.findall(text)
        if not matches:
            return None
        h_total = float(matches[-1])  # PSTRESS=0 => H = E
    contcar = os.path.join(rundir, "CONTCAR")
    poscar = os.path.join(rundir, "POSCAR")
    src = contcar if os.path.isfile(contcar) and os.path.getsize(contcar) > 0 else poscar
    natoms = natoms_from_poscar(src)
    return h_total, natoms, converged


def main():
    phase_dirs = sorted(glob.glob(os.path.join(BASE, "Al4C3_*")))
    rows = []
    for pdir in phase_dirs:
        phase = os.path.basename(pdir).replace("Al4C3_", "")
        for p in PRESSURES:
            rundir = os.path.join(pdir, f"P{p}")
            if not os.path.isdir(rundir):
                continue
            res = read_result(rundir)
            if res is None:
                rows.append((phase, p, "", "", "", "pending"))
                continue
            h_total, natoms, converged = res
            h_per_fu = h_total / (natoms / ATOMS_PER_FU)
            rows.append((phase, p, natoms, f"{h_total:.6f}", f"{h_per_fu:.6f}",
                         "converged" if converged else "unconverged"))

    csv_path = os.path.join(BASE, "results_hp.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["phase", "pressure_GPa", "natoms", "H_total_eV", "H_per_fu_eV", "status"])
        w.writerows(rows)
    print(f"Wrote {csv_path} ({len(rows)} rows)")

    # per-phase .dat files (converged points only) for pgfplots \addplot table
    by_phase = {}
    for phase, p, natoms, h_total, h_per_fu, status in rows:
        if status != "converged":
            continue
        by_phase.setdefault(phase, []).append((p, float(h_per_fu)))

    for phase, pts in by_phase.items():
        pts.sort()
        dat_path = os.path.join(BASE, f"hp_{phase}.dat")
        with open(dat_path, "w") as f:
            f.write("P_GPa H_eV_per_fu\n")
            for p, h in pts:
                f.write(f"{p} {h:.6f}\n")
        print(f"Wrote {dat_path} ({len(pts)} converged points)")

    n_converged = sum(1 for r in rows if r[-1] == "converged")
    print(f"{n_converged}/{len(rows)} runs converged so far")


if __name__ == "__main__":
    main()
