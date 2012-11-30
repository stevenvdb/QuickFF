#! /usr/bin/env python

from molmod.io.chk import load_chk
from molmod.io.psf import PSFFile
from molmod.io.xyz import XYZWriter
from molmod.units import *
from molmod.ic import *
from molmod.periodic import periodic as pt
from copy import deepcopy
import numpy as np, sys

from model import *
from ic import *
from evaluators import *
from tools import *
from fftable import FFTable

__all__=['System']

class System(object):
    def __init__(self, name, fn_chk, eikind=None, eirule=0):
        print 'SYSTEM  INIT: initializing system %s' %name
        self.name = name
        self.fn_chk = fn_chk
        self.sample = load_chk(fn_chk)
        self.eikind = eikind
        self.eirule = eirule
        
        print 'SYSTEM  INIT: Projecting translational and rotional dofs out of the hessian'
        self.Nat = len(self.sample['coordinates'])
        hess = self.sample['hessian'].reshape([3*self.Nat, 3*self.Nat])
        VTx, VTy, VTz = global_translation(self.sample['coordinates'])
        VRx, VRy, VRz = global_rotation(self.sample['coordinates'])
        U, S, Vt = np.linalg.svd( np.array([VTx, VTy, VTz, VRx, VRy, VRz]).transpose() )
        P = np.dot(U[:,6:], U[:,6:].T)
        hess_proj = np.dot(P, np.dot(hess, P))
        self.totmodel = HarmonicModel(self.sample['coordinates'], self.sample['forces'], hess_proj, name='Harmonic Total Energy')
        self.eimodel = ZeroModel()
        if eikind is not None:
            self.define_ei_model()
    
    def define_ei_model(self):    
        print 'SYSTEM    EI: Constructing electrostatic model'
        exclude = []
        if self.eirule>0:
            for bond in self.sample['bonds']:
                exclude.append([bond[0], bond[1]])
        if self.eirule>1:
            for bend in self.sample['bends']:
                exclude.append([bend[0], bend[2]])
        if self.eirule>2:
            for dihed in self.sample['dihedrals']:
                exclude.append([dihed[0], dihed[3]])
        if self.eikind=='Harmonic':
            forces_ei, hess_ei = electrostatics(self.sample, exclude_pairs=exclude)
            self.eimodel = HarmonicModel(self.sample['coordinates'], forces_ei, hess_ei, name='Harmonic Electrostatic Energy')
        elif self.eikind = 'Coulomb':
            self.eimodel = CoulombModel(self.sample['coordinates'], self.sample['charges'], name='Coulomb Electrostatic Energy', exclude_pairs=exclude)
        else:
            raise ValueError('Invalid model kind in System.define_ei_model, received %s' %self.mkind)

    def find_ic_patterns(self, icnames):
        print 'SYSTEM ICPAT: determining ic patterns'
        atypes = self.sample['ffatypes']
        self.ics = {}
        self.units = {}
        for icname, (kunit, qunit) in icnames.iteritems():
            match = []
            values = []
            if '%s' in icname: icname = icname %( (self.name.split('/')[0].upper(),)*icname.count('%') )
            self.units[icname] = {'k': kunit, 'q': qunit}
            ictypes = icname.split('/')[1].split('.')
            ickind = icname.split('/')[0]
            if ickind=='bond':
                assert len(ictypes)==2
                for bond in self.sample['bonds']:
                    if (atypes[bond[0]]==ictypes[0] and atypes[bond[1]]==ictypes[1]) or (atypes[bond[0]]==ictypes[1] and atypes[bond[1]]==ictypes[0]):
                        match.append(IC(bond, bond_length, name=icname+str(len(match))))
            elif ickind=='angle':
                assert len(ictypes)==3
                for bend in self.sample['bends']:
                    if (atypes[bend[0]]==ictypes[0] and atypes[bend[1]]==ictypes[1] and atypes[bend[2]]==ictypes[2]) \
                    or (atypes[bend[0]]==ictypes[2] and atypes[bend[1]]==ictypes[1] and atypes[bend[2]]==ictypes[0]):
                        match.append(IC(bend, bend_angle, name=icname+str(len(match))))
            elif ickind=='dihed':
                assert len(ictypes)==4
                for dihed in self.sample['dihedrals']:
                    if (atypes[dihed[0]]==ictypes[0] and atypes[dihed[1]]==ictypes[1] and atypes[dihed[2]]==ictypes[2] and atypes[dihed[3]]==ictypes[3]) \
                    or (atypes[dihed[0]]==ictypes[3] and atypes[dihed[1]]==ictypes[2] and atypes[dihed[2]]==ictypes[1] and atypes[dihed[3]]==ictypes[0]):
                        match.append(IC(dihed, dihed_angle, name=icname+str(len(match))))
            else:
                raise ValueError('Recieved invalid ic kind: %s' %ickind)
            if len(match)==0:
                print 'SYSTEM ICPAT: No match found for %s' %icname
            self.ics[icname] = match

    def test_ics(self, epsilon=1e-4, ntests=50, threshold=1e-5):
        print 'SYSTEM  TEST: testing ic gradient and hessian'
        for icname, ics in self.ics.iteritems():
            for ic in ics:
                ic.test(self.sample['coordinates'], epsilon=epsilon, ntests=ntests, threshold=threshold)
        print 'SYSTEM  TEST: testing non-bond pairs gradient and hessian'
        for i, itype in enumerate(self.sample['ffatypes']):
            for j, jtype in enumerate(self.sample['ffatypes'][:i]):
                if (i,j) in self.sample['bonds']: continue
                name = 'pair/%i(%s)-%i(%s)' %(i,itype,j,jtype)
                ic = IC([i,j], bond_length, name=name)
                ic.test(self.sample['coordinates'], epsilon=epsilon, ntests=ntests, threshold=threshold)

    def _get_neighbors(self, indices, depth=1):
        neighbors = deepcopy(indices)
        edge = deepcopy(indices)
        current = 0
        while current<depth:
            new_edge = []
            for index in edge:
                for neighbor in self.sample['neighbors'][index]:
                    if neighbor not in neighbors:
                        neighbors.append(neighbor)
                        new_edge.append(neighbor)
            edge = new_edge
            current += 1
        return neighbors
