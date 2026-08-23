"""
Collect E(P), V(P), H(P) results from the Al4C3 r2SCAN enthalpy-vs-pressure scan.

Walks hp_curves_r2SCAN/Al4C3_<phase>/P<pressure>/OUTCAR, extracts the converged
total energy E (VASP "free  energy   TOTEN"), cell volume V ("volume of
cell") and enthalpy H = E + P*V (VASP prints it directly as "enthalpy is
TOTEN" when PSTRESS != 0; at P=0, H = E) together with the atom count, and
writes per-phase .dat files (pressure_GPa, {E,V,H}_per_fu) suitable for
\\addplot table in pgfplots, plus a combined results_hp.csv.

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
VOLUME_RE = re.compile(r"volume of cell :\s*([\d.]+)")


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

    e_matches = FREE_ENERGY_RE.findall(text)
    if not e_matches:
        return None
    e_total = float(e_matches[-1])

    h_matches = ENTHALPY_RE.findall(text)
    h_total = float(h_matches[-1]) if h_matches else e_total  # PSTRESS=0 => H = E

    v_matches = VOLUME_RE.findall(text)
    volume = float(v_matches[-1]) if v_matches else None

    contcar = os.path.join(rundir, "CONTCAR")
    poscar = os.path.join(rundir, "POSCAR")
    src = contcar if os.path.isfile(contcar) and os.path.getsize(contcar) > 0 else poscar
    natoms = natoms_from_poscar(src)
    return e_total, volume, h_total, natoms, converged


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
                rows.append((phase, p, "", "", "", "", "", "", "", "pending"))
                continue
            e_total, volume, h_total, natoms, converged = res
            fu = natoms / ATOMS_PER_FU
            e_per_fu = e_total / fu
            v_per_fu = volume / fu if volume is not None else ""
            h_per_fu = h_total / fu
            rows.append((
                phase, p, natoms,
                f"{e_total:.6f}", f"{e_per_fu:.6f}",
                f"{volume:.6f}" if volume is not None else "",
                f"{v_per_fu:.6f}" if v_per_fu != "" else "",
                f"{h_total:.6f}", f"{h_per_fu:.6f}",
                "converged" if converged else "unconverged",
            ))

    csv_path = os.path.join(BASE, "results_hp.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["phase", "pressure_GPa", "natoms",
                     "E_total_eV", "E_per_fu_eV",
                     "V_total_A3", "V_per_fu_A3",
                     "H_total_eV", "H_per_fu_eV", "status"])
        w.writerows(rows)
    print(f"Wrote {csv_path} ({len(rows)} rows)")

    # per-phase .dat files (converged points only) for pgfplots \addplot table
    by_phase = {}
    for phase, p, natoms, e_total, e_per_fu, v_total, v_per_fu, h_total, h_per_fu, status in rows:
        if status != "converged":
            continue
        by_phase.setdefault(phase, []).append(
            (p, float(e_per_fu), float(v_per_fu), float(h_per_fu))
        )

    for phase, pts in by_phase.items():
        pts.sort()
        with open(os.path.join(BASE, f"hp_{phase}.dat"), "w") as f:
            f.write("P_GPa H_eV_per_fu\n")
            for p, e, v, h in pts:
                f.write(f"{p} {h:.6f}\n")
        with open(os.path.join(BASE, f"hp_E_{phase}.dat"), "w") as f:
            f.write("P_GPa E_eV_per_fu\n")
            for p, e, v, h in pts:
                f.write(f"{p} {e:.6f}\n")
        with open(os.path.join(BASE, f"hp_V_{phase}.dat"), "w") as f:
            f.write("P_GPa V_A3_per_fu\n")
            for p, e, v, h in pts:
                f.write(f"{p} {v:.6f}\n")
        print(f"Wrote hp_{{,E_,V_}}{phase}.dat ({len(pts)} converged points)")

    n_converged = sum(1 for r in rows if r[-1] == "converged")
    print(f"{n_converged}/{len(rows)} runs converged so far")


if __name__ == "__main__":
    main()
