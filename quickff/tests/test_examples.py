# -*- coding: utf-8 -*-
# QuickFF is a code to quickly derive accurate force fields from ab initio input.
# Copyright (C) 2012 - 2018 Louis Vanduyfhuys <Louis.Vanduyfhuys@UGent.be>
# Steven Vandenbrande <Steven.Vandenbrande@UGent.be>,
# Jelle Wieme <Jelle.Wieme@UGent.be>,
# Toon Verstraelen <Toon.Verstraelen@UGent.be>, Center for Molecular Modeling
# (CMM), Ghent University, Ghent, Belgium; all rights reserved unless otherwise
# stated.
#
# This file is part of QuickFF.
#
# QuickFF is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# QuickFF is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
#
#--
import numpy as np
import os

from molmod.units import *
from molmod.constants import lightspeed
from molmod.periodic import periodic as pt

from yaff import System

from quickff.tools import set_ffatypes
from quickff.program import DeriveFF
from quickff.settings import Settings
from quickff.context import context

from common import log, read_system, tmpdir

def test_h2():
    #frequency of H2 stretch mode in gaussian.fchk calculation is 4416.656/cm
    #and an equilibrium bond length of 0.7442380 A. This test checks if the
    #force field predicts the same values
    r0 = 0.7442380*angstrom
    freq = (2*np.pi)*4416.65640485*lightspeed/centimeter
    mass = pt['H'].mass/2 #reduced mass for the H2 stretch mode
    #Load system, model and pert. theory and estimate ff
    with log.section('NOSETST', 2):
        system, ai = read_system('H2/gaussian.fchk')
        set_ffatypes(system, 'low')
        program = DeriveFF(system, ai, Settings())
        program.do_pt_generate()
        program.do_pt_estimate()
        K_pt, rv_pt = program.valence.get_params(0, only='all')
        program.do_hc_estimatefc(['HC_FC_DIAG'])
        K_hc, rv_hc = program.valence.get_params(0, only='all')
    #print results
    print('')
    print('AI     :    K = %.3f kjmol/A^2    q0 = %.6f A' %(mass*freq**2/(kjmol/angstrom**2), r0/angstrom))
    print('FF (PT):    K = %.3f kjmol/A^2    q0 = %.6f A' %(K_pt/(kjmol/angstrom**2), rv_pt/angstrom))
    print('FF (HC):    K = %.3f kjmol/A^2    q0 = %.6f A' %(K_hc/(kjmol/angstrom**2), rv_hc/angstrom))
    print('')
    #perform assertion checks
    assert abs(K_pt/(mass*freq**2)-1.0) < 1e-3
    assert abs(rv_pt/r0-1.0) < 1e-3
    assert abs(K_hc/(mass*freq**2)-1.0) < 1e-3
    assert abs(rv_hc/r0-1.0) < 1e-3
    assert abs(K_hc/K_pt-1.0) < 1e-6
    assert abs(rv_hc/rv_pt-1.0) < 1e-6


def test_output_charmm22():
    with log.section('NOSETST', 2):
        system, ai = read_system('ethanol/gaussian.fchk')
        set_ffatypes(system, 'low')
        with tmpdir('test_output_charmm22') as dn:
            fn_yaff = os.path.join(dn, 'pars_cov.txt')
            fn_charmm22_prm = os.path.join(dn, 'test.prm')
            fn_charmm22_psf = os.path.join(dn, 'test.psf')
            fn_sys = os.path.join(dn, 'system.chk')
            settings = Settings(
                do_cross_ASS=False, do_cross_ASA=False,
                fn_yaff=fn_yaff, fn_sys=fn_sys,
                fn_charmm22_prm=fn_charmm22_prm,
                fn_charmm22_psf=fn_charmm22_psf,
            )
            program = DeriveFF(system, ai, settings)
            program.run()
            assert os.path.isfile(fn_yaff)
            assert os.path.isfile(fn_charmm22_prm)
            assert os.path.isfile(fn_charmm22_psf)
            assert os.path.isfile(fn_sys)

            # Count the number of BOND, ANGLES and DIHEDRAL lines in the PRM file.
            counts = {}
            with open(fn_charmm22_prm, 'r') as f:
                for line in f:
                    print(line)
                    line = line[:line.find('!')].strip()
                    if len(line) == 0:
                        continue
                    if line in ['BONDS','ANGLES', 'DIHEDRALS', 'IMPROPER']:
                        key = line
                        counts[key] = 0
                    else:
                        counts[key] += 1
            assert counts['BONDS'] == 4
            assert counts['ANGLES'] == 5
            assert counts['DIHEDRALS'] == 3
            assert counts['IMPROPER'] == 0

            # Count the number atoms, bonds, angles and dihedrals in the PSF file and
            # check for consistency.
            with open(fn_charmm22_psf, 'r') as f:
                natom = 0
                assert next(f) == 'PSF\n'
                for line in f:
                    if '!NATOM' in line:
                        natom = int(line.split()[0])
                        break
                assert natom == system.natom
                for iatom in range(natom+1):
                    next(f)
                line = next(f)
                assert '!NBOND: bonds' in line
                nbond = int(line.split()[0])
                nline = int(np.ceil(nbond/4.0))
                numbers = (''.join([next(f) for iline in range(nline)])).split()
                assert len(numbers) == nbond*2
                next(f)
                line = next(f)
                assert '!NTHETA: angles' in line
                ntheta = int(line.split()[0])
                nline = int(np.ceil(ntheta/3.0))
                numbers = (''.join([next(f) for iline in range(nline)])).split()
                assert len(numbers) == ntheta*3
                next(f)
                line = next(f)
                assert '!NPHI: dihedrals' in line
                nphi = int(line.split()[0])
                nline = int(np.ceil(nphi/2.0))
                numbers = (''.join([next(f) for iline in range(nline)])).split()
                assert len(numbers) == nphi*4
                next(f)
                line = next(f)
                assert '!NIMPHI: impropers' in line
                nimphi = int(line.split()[0])
                assert nimphi == 0
