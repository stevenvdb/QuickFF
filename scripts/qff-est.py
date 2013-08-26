#! /usr/bin/env python

from optparse import OptionParser

from quickff.system import System
from quickff.model import Model
from quickff.program import Program
from quickff.fftable import FFTable

def parser():
    usage = "%prog [options] fns"
    description = 'This script is part of QuickFF. It calculates the harmonic'+\
                  'ff parameters a system specified in the files fns.'
    parser = OptionParser(usage=usage, description=description)
    parser.add_option(
        '--eirule', default=-1, type=int,
        help='Defines the exclusion rule for the electrostatic interactions. '  +\
             'If set to -1, no electrostatic interactions are taken into '      +\
             'account during force field fitting. If the rule is set to '       +\
             '0,1,2,3: pairs seperated by less then or equal to 0,1,2,3 bonds ' +\
             'respectively are excluded from ei interactions. [default=-1]'
    )
    parser.add_option(
        '--charge-scheme', default=None,
        help='Defines the charge scheme for which the charges will be extracted ' +\
             'from the Horton-formatted HDF5 file given in fns. [default=%default]'
    )
    parser.add_option(
        '--atypes-level', default=None,
        help='Assign atom types according to level ATYPES_LEVEL. LOW will '     +\
             'assign atom types based only on atom number. MEDIUM will assign ' +\
             'atom types based on atom number and the number of neighbors. '    +\
             'HIGH will assign atom types based on atom number, number of '     +\
             'neighbors and the nature of the neighbors. HIGHEST will assign '  +\
             'atom types based on atom index. NONE will not guess but use the ' +\
             'atom types defined in the input files fns. [default=%default]'
    )
    parser.add_option(
        '--suffix', default='',
        help = "Suffix that will be added to all output files. [default='']"
    )
    options, fns = parser.parse_args()
    return fns, options

def main():
    #Parse args
    fns, options = parser()
    #Setup system, model and program
    system = System.from_files(fns, charge_scheme=options.charge_scheme)
    if options.atypes_level is not None:
        system.guess_ffatypes(options.atypes_level)
    else:
        system.average_charges_ffatypes()
    system.determine_ics_from_topology()
    model = Model.from_system(system, eirule=options.eirule)
    program = Program(system, model)
    #Run program
    ff = program.run()
    #Make output
    ff.dump_ffit2('pars_ffit2%s.txt' % options.suffix, mode='w')
    ff.dump_yaff('pars_yaff%s.txt' % options.suffix, mode='w')
    system.dump_charges_yaff(
        'pars_yaff%s.txt' % options.suffix,
        options.eirule, mode='a'
    )
    system.dump('system%s.chk' % options.suffix)

if __name__=='__main__':
    main()
