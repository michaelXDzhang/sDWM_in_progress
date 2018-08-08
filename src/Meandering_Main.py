"""
author: Augustin Grosdidier
date: 02/07/2018

Running Core of the meandering computation process.
Computing for MannBox and at the end for LESBox.

Mainly Based on 'A Pragmatic Approach oh the Meandering' GLarsen
Work with the 'Simplification' for the moment (very fast and relevant for a MannBox)
But it could be improved with no simplification easily.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
import math as m
from matplotlib import animation
import copy

from DWM_GClarsenPicks import get_Rw

import WindTurbine as wt

from ReadTurbulence import *

from cTurb import *

from Polar_Interpolate_Data_Plan import *

import time

def DWM_extract_meandering_from_TurbBox(MannBox, WindFarm):
    """
    Notice: in Future Work we can add the fact that the Turbulence Box becomes slower through the windfarm
    :param filename:
    :param WindFarm:
    :param WT:
    :return:
    """
    # WT location in the streamwise (come from meta.z_vec of Make Grid in sDWM):
    # [0  4  8 12 17 21 25 30]
    # ---- # For Test, this have to come from sDWM and so to be a parameter # ---- #
    WindFarm.stream_location_z = [2*ld for ld in WindFarm.stream_location_z] # [R]
    # reverse index location: originally the wind farm is index like this: 7 6 5 4 3 2 1 0 (upstream to downstream)
    WindFarm.stream_location_z = WindFarm.stream_location_z[::-1]
    WindFarm.stream_location_z = [abs(ld-max(WindFarm.stream_location_z)) for ld in WindFarm.stream_location_z]
    #                       : now 0 1 2 3 4 5 6 7
    print 'WindFarm.stream_location_z ', WindFarm.stream_location_z
    #then [0,  4,  8, 12, 17, 21, 25]
    # then [0,  4,  8, 12, 17, 21]
    # then [0,  4,  8, 12, 17]
    # then [0,  4,  8, 12] etc...
    WindFarm.nodim_lenght = WindFarm.stream_location_z[-1]

    video = False

    # -------------------------------- # INITIALIZATION # ------------------------------------ #
    MannBox, WindFarm = Init_Turb(MannBox, WindFarm)


    # What Can we do for a not constant spacing
    # Not Implemented for now for the not crude approach
    #"""
    RW = {}
    LD = {}
    for Wake_index in range(len(WindFarm.stream_location_z)):
        ld_ref = WindFarm.stream_location_z[Wake_index]
        tho_ref = ld_ref / MannBox.U
        Ld = [abs(ld - ld_ref) for ld in WindFarm.stream_location_z[Wake_index:]]
        RW[Wake_index] = get_Rw(x=Ld, R=1., TI=MannBox.TI, CT=WindFarm.CT)
        LD[Wake_index] = Ld
    print RW
    print LD
    #raw_input('....')
    #"""
    # -------------- # Meandering Computation for each plan of interest # --------------------------- #
    # Ld is the list of the distance between generating plan and the plans of interest
    #Ld = WindFarm.stream_location_z  # We are at a specified distance so we can get the wake radius at this distance
                                     # (doesn't change in time)
                                     # A simple stationary semi-analytical wake model Gunner C. Larsen (2009)

    Meand_Mann = meand_mann()
    if MannBox.CorrectionDelay:
        # We want to begin the simulation when the first plan go out of the WindFarm Box
        MannBox.delay = WindFarm.nodim_lenght / MannBox.U
        print 'delay is:', MannBox.delay
    # The data do not exceed the simulation time defined in class object (cMeand or cMann)
    T = [ti for ti in MannBox.ti[:] if ti < MannBox.SimulationTime]

    ############ OLD LOOP for Debug only ###################
    # This is a really crude approach of the algorithm to handle all the wake! So more computation time.
    if MannBox.loop_debug:
        start_time = time.time()
        WAKES = [] # list holding all wakes generated by each turbines
        for WT_index in range(len(WindFarm.stream_location_z)):
            # creates the list ld of interest
            # all the distances are calculate for reference WT, we delete WT upstream to the WT ref
            ld_ref = WindFarm.stream_location_z[WT_index]
            Ld = [abs(ld-ld_ref) for ld in WindFarm.stream_location_z[WT_index:]]

            # For each ld in Ld, we get a data matrix structured like this: column 1: time(s), column 2: yc, column 3: zc
            # we store these matrixs in a list along Ld

            Wake = []

            tho_ref = ld_ref / MannBox.U

            for ld in Ld:
                print 'Ld: ', ld

                ts_vc_wc =[]
                # as x_b = U*tho, tho = x_b/U (here x_b = ld)
                tho_rel = ld / MannBox.U  # time for the first wake release to reach the studied plan at ld

                # Get Wake radius function of the transportation time (seems at this distance)
                if MannBox.WakeExpansion:
                    # ----# Get the wake radius #----#
                    Rw = get_Rw(x=ld, R=1., TI=MannBox.TI, CT=WindFarm.CT)  # resulted Rw is no dimensionalized
                    MannBox.WakeRadius_for_this_Plan = Rw
                    MannBox.Af = m.pi * (2 * MannBox.WakeRadius_for_this_Plan) ** 2
                boolref = False
                for ts in T:
                    if MannBox.CorrectionDelay:
                        ts = ts + MannBox.delay
                        if ld == 0.:
                            vc_wc = [0., 0.]
                        else:
                            vc_wc = Wake_Dynamic_at_Ld(ld, ts - tho_ref-tho_rel, MannBox, Meand_Mann)
                            #vc_wc = Wake_Dynamic_at_Ld(ld, ts, MannBox, Meand_Mann)
                        ts_vc_wc.append([ts-MannBox.delay] + vc_wc)
                    else:
                        if ts - tho < 0:
                            ts_vc_wc.append([ts, np.nan, np.nan])
                        else:

                            vc_wc = Wake_Dynamic_at_Ld(ld, ts - tho, MannBox, Meand_Mann)
                            if not boolref:
                                boolref = True
                                vc_wc_ref = vc_wc
                            ts_vc_wc.append([ts]+vc_wc)

                ts_vc_wc = np.array(ts_vc_wc)
                ts_yc_zc = ts_vc_wc
                if not MannBox.CorrectionDelay:
                    NaN_index = np.isnan(ts_yc_zc[:, 1])
                    ts_yc_zc[NaN_index, 1] = vc_wc_ref[0]
                    ts_yc_zc[NaN_index, 2] = vc_wc_ref[1]

                ts_yc_zc[:, 1:3] = ld/MannBox.U * ts_yc_zc[:, 1:3]
                Wake.append(ts_yc_zc)
            WAKES.append(Wake)
        print 'Computation time for crude approach: ', time.time() - start_time



    ######NEW Loops
    # 2 kinds of loop possible: One wake can be use for every wake in the WF (big assumption) (Mannbox considered for one WT)
    # or multiple wake created as the first wake with wake expansion and constant WF CT (Mannbox considered for the entire WF)
    if not MannBox.loop_debug:
        ################################################################################################################

        ################################################################################################################
        if MannBox.multiplewake_build_on_first_wake:
            print '------------------------- MULTIPLE WAKE BUILD ON THE FIRST WAKE METHOD PROCESSING ------------------'
            if MannBox.SimulationTime != None:
                T_Mannbox = [ti for ti in MannBox.ti[:] if ti < MannBox.SimulationTime+MannBox.delay]
            else:
                T = [ti for ti in MannBox.ti[:] if ti < MannBox.ti[-1]- MannBox.delay]
                T_Mannbox = [ti for ti in MannBox.ti[:] if ti < MannBox.ti[-1]]

            # You should admit a constant spacing between turbines


            # ------------------------ # INTERPOLATION LOOP # -------------------------------------------------------- #
            print '------------------------- TURB BOX INTERPOLATION PROCESSING ----------------------------------------'
            tstart = time.time()
            Interpo_Integrate = interpo_integrate()
            Interpo_Integrate.F_tm_fvc_fwc = []
            for t_M in T_Mannbox:
                tm_vc_wc = []
                for char in ['vfluct', 'wfluct']:
                    Meand_Mann.wake_center_location = (0, 0)  # due to simplification
                    MannBox.plan_of_interest = get_plan_of_interest(MannBox, ti=t_M, component_char=char)

                    # ----# Interpolation Part (WakeCentered) #----#

                    Interpo_Integrate = Interpolate_plan(MannBox, Interpo_Integrate, Meand_Mann)
                    tm_vc_wc.append(Interpo_Integrate.f_cart)
                Interpo_Integrate.F_tm_fvc_fwc.append(tm_vc_wc)
            print 'computation time for interpo: ', time.time()- tstart

            print np.shape(Interpo_Integrate.F_tm_fvc_fwc)
            # --------------------- # INTREGRATION PROCESS FOR FirST WAKE # ------------------------------------- #
            print '------------------------- INTREGRATION FOR FirST WAKE PROCESSING -----------------------------------'
            start_time = time.time()
            # same spacing & same wake expansion behaviour for each wake, so we can calcutate just one wake to build the other
            WAKES = []  # list holding all wakes generated by each turbines

            #Computation for the first wake only. tho ref =0
            Wake = []
            tho_ref = 0
            for ld in WindFarm.stream_location_z:
                print 'Ld: ', ld

                ts_vc_wc = []
                # as x_b = U*tho, tho = x_b/U (here x_b = ld)
                tho_rel = ld / MannBox.U  # time for the first wake release to reach the studied plan at ld

                # Get Wake radius function of the transportation time (seems at this distance)
                if MannBox.WakeExpansion:
                    # ----# Get the wake radius #----#
                    Rw = get_Rw(x=ld, R=1., TI=MannBox.TI, CT=WindFarm.CT)  # resulted Rw is no dimensionalized
                    MannBox.WakeRadius_for_this_Plan = Rw
                    MannBox.Af = m.pi * (2 * MannBox.WakeRadius_for_this_Plan) ** 2
                boolref = False
                for ts in T:
                    # print 'ts: ', ts
                    if MannBox.CorrectionDelay:
                        ts = ts + MannBox.delay
                        if ld == 0.:  # and ld_ref!=WindFarm.stream_location_z[-1]:
                            vc_wc = [0., 0.]
                        else:
                            vc_wc = Wake_Dynamic_at_Ld_optim(ts - tho_ref - tho_rel, MannBox, Meand_Mann,
                                                             Interpo_Integrate)
                            # vc_wc = Wake_Dynamic_at_Ld(ld, ts, MannBox, Meand_Mann)
                        ts_vc_wc.append([ts - MannBox.delay] + vc_wc)
                    else:
                        if ts - tho_rel < 0:
                            ts_vc_wc.append([ts, np.nan, np.nan])
                        else:

                            vc_wc = Wake_Dynamic_at_Ld(ld, ts - tho, MannBox, Meand_Mann)
                            if not boolref:
                                boolref = True
                                vc_wc_ref = vc_wc
                            ts_vc_wc.append([ts] + vc_wc)

                ts_vc_wc = np.array(list(ts_vc_wc))
                if not MannBox.CorrectionDelay:
                    NaN_index = np.isnan(ts_yc_zc[:, 1])
                    ts_yc_zc[NaN_index, 1] = vc_wc_ref[0]
                    ts_yc_zc[NaN_index, 2] = vc_wc_ref[1]

                Wake.append(ts_vc_wc)
            WAKES.append(list(Wake))
            print 'Computation time for integrate: ', time.time() - start_time

            # --------------------- # POST PROCESSING TO BUILD OTHER WAKEs # ------------------------------------- #
            print '------------------------- POST PROCESSING TO BUILD OTHER WAKEs -------------------------------------'
            # Built other wake with first one
            start_time = time.time()
            for WT_index in range(1, len(WindFarm.stream_location_z)):
                # creates the list ld of interest
                # all the distances are calculate for reference WT, we delete WT upstream to the WT ref
                ld_ref = WindFarm.stream_location_z[WT_index]
                Ld = np.array([abs(ld - ld_ref) for ld in WindFarm.stream_location_z[WT_index:]])
                # For each ld in Ld, we get a data matrix structured like this: column 1: time(s), column 2: yc, column 3: zc
                # we store these matrixs in a list along Ld

                wake_to_add = copy.deepcopy(WAKES[0][WT_index:])

                # ------------ # POST PROCESSING TO apply OTHER WAKEs ld/U from simplification # ----------------- #
                for i_ld in range(len(Ld)):
                    ld = float(Ld[i_ld])
                    wake_to_add[i_ld][:][:, 1:3] = ld/MannBox.U * wake_to_add[i_ld][:][:, 1:3]
                WAKES.append(wake_to_add)

            # --------------------- # Post Processing apply ld/U to first wake # --------------------------------- #
            wake_to_change = copy.deepcopy(WAKES[0])
            for i_ld in range(len(WindFarm.stream_location_z)):
                ld = float(WindFarm.stream_location_z[i_ld])
                wake_to_change[i_ld][:][:, 1:3] = ld/MannBox.U * wake_to_change[i_ld][:][:, 1:3]
            WAKES[0] = wake_to_change

            print 'Computation time for Post Process: ', time.time()-start_time



        if not MannBox.multiplewake_build_on_first_wake:

            if MannBox.SimulationTime != None:
                T_Mannbox = [ti for ti in MannBox.ti[:] if ti < MannBox.SimulationTime+MannBox.delay]
            else:
                T = [ti for ti in MannBox.ti[:] if ti < MannBox.ti[-1]- MannBox.delay]
                T_Mannbox = [ti for ti in MannBox.ti[:] if ti < MannBox.ti[-1]]



        # ---------------------------- # INTERPOLATION LOOP # -------------------------------------------------------- #
            print '------------------------- TURB BOX INTERPOLATION PROCESSING ----------------------------------------'
            Interpo_Integrate = interpo_integrate()
            Interpo_Integrate.F_tm_fvc_fwc = []
            tstart = time.time()
            for t_M in T_Mannbox:
                tm_vc_wc = []
                for char in ['vfluct', 'wfluct']:
                    Meand_Mann.wake_center_location = (0, 0)  # due to simplification
                    MannBox.plan_of_interest = get_plan_of_interest(MannBox, ti=t_M, component_char=char)

                    # ----# Interpolation Part (WakeCentered) #----#
                    Interpo_Integrate = Interpolate_plan(MannBox, Interpo_Integrate, Meand_Mann)
                    tm_vc_wc.append(Interpo_Integrate.f_cart)

                Interpo_Integrate.F_tm_fvc_fwc.append(tm_vc_wc)
            print 'computation time for interpo: ', time.time() - tstart

            print np.shape(Interpo_Integrate.F_tm_fvc_fwc)

        # ---------------------------- # INTEGRATION LOOP # ---------------------------------------------------------- #
            print '------------------------- TURB BOX INTEGRATION PROCESSING ----------------------------------------'
            tstart = time.time()
            WAKES = []
            for WAKE_id in range(len(WindFarm.stream_location_z)):
                Wake = []
                for i_ld in range(len(LD[WAKE_id])):

                    ld = LD[WAKE_id][i_ld]

                    Rw = RW[WAKE_id][i_ld]
                    MannBox.WakeRadius_for_this_Plan = Rw
                    MannBox.Af = m.pi * (2 * MannBox.WakeRadius_for_this_Plan) ** 2


                    tho_ref = LD[0][WAKE_id]/MannBox.U

                    print 'Ld: ', ld

                    ts_vc_wc = []
                    # as x_b = U*tho, tho = x_b/U (here x_b = ld)
                    tho_rel = ld / MannBox.U  # time for the first wake release to reach the studied plan at ld

                    # Get Wake radius function of the transportation time (seems at this distance)
                    boolref = False
                    for ts in T:
                        if MannBox.CorrectionDelay:
                            ts = ts + MannBox.delay
                            #print 'ts: ', ts

                            if ld == 0.:  # and ld_ref!=WindFarm.stream_location_z[-1]:
                                vc_wc = [0., 0.]
                            else:
                                #print 'tho_ref', tho_ref
                                #print 'tho_rel', tho_rel
                                vc_wc = Wake_Dynamic_at_Ld_optim(ts - tho_ref - tho_rel, MannBox, Meand_Mann, Interpo_Integrate)

                            ts_vc_wc.append([ts - MannBox.delay] + vc_wc)

                        else:
                            if ts - tho_rel < 0:
                                ts_vc_wc.append([ts, np.nan, np.nan])
                            else:

                                vc_wc = Wake_Dynamic_at_Ld(ld, ts - tho, MannBox, Meand_Mann)
                                if not boolref:
                                    boolref = True
                                    vc_wc_ref = vc_wc
                                ts_vc_wc.append([ts] + vc_wc)

                    #print 'tsvcwc shape: ',np.shape(ts_vc_wc)
                    ts_vc_wc = np.array(ts_vc_wc)
                    ts_yc_zc = ts_vc_wc
                    if not MannBox.CorrectionDelay:
                        NaN_index = np.isnan(ts_yc_zc[:, 1])
                        ts_yc_zc[NaN_index, 1] = vc_wc_ref[0]
                        ts_yc_zc[NaN_index, 2] = vc_wc_ref[1]

                    ts_yc_zc[:, 1:3] = ld / MannBox.U * ts_yc_zc[:, 1:3]
                    Wake.append(ts_vc_wc)
                WAKES.append(Wake)
            print np.shape(WAKES)
            print 'Computation time to integrate: ', time.time() - tstart
            #raw_input('....')


            # Not Implemented
    ####NEW LOOP FOR FAST RESULT BASED ON WAKE EXPANSION



    #Plot Part
    # Plot each Wake
    if MannBox.RESULT_plot:
        Plot_each_Wake(WAKES, WindFarm)
        Plot_Wakes_at_each_ld(WAKES, WindFarm)
        #Plot_Wakes_at_each_ld_in_MannBox_referential(WAKES, WindFarm, MannBox)
    DATA = WAKES
    np.save('WAKES',DATA)
    print 'Wake Radius Data saved...'
    return WAKES

def Init_Turb(MannBox, WindFarm):

    video = False

    # -------------------------- # SIZE THE TURBULENT BOXES # ------------------------ #
    # sizing mann for the biggest wake?
    # Get the max wake radius to size correctly the Mann box,
    # (be careful if you don't use the 'simplification' described by Larsen,
    # you must manage the wake movement in addition of the wake radius to size the turbulent box.
    # (note: not yet implemented but we can also positionate rightly the turbulent Box to be close to the ground
    # and we could manage the ground effect on the meandering)
    # for the moment the wake movement doesn't need to take care of the ground (no need to implement reflecting surface)
    WindFarm.Rw_Max = get_Rw(x=WindFarm.nodim_lenght, R=1., TI=MannBox.TI, CT=WindFarm.CT)
    print 'Rw max in WindFarm is: ', WindFarm.Rw_Max
    if MannBox.Box_Kind == 'Mann':
        MannBox = sizing_MannBox(MannBox, WindFarm)  # put: , windFarm_lenght=0.) for the first function of  Main loop
    print 'ly/2: ', MannBox.ly/2
    print 'dt: ', MannBox.dt

    # -------------------------- # INITIALIZATION # --------------------------------- #

    print 'Total simulation time for the entire MannBox: ', MannBox.ti[-1]  # 819,2s in total

    # ---- # Get the wake radius # ---- #
    MannBox.WakeRadius_for_this_Plan = 1. # the wake generating plan rotor radius = wake radius (we assumed)
    MannBox.Af = m.pi * (2 * MannBox.WakeRadius_for_this_Plan) ** 2

    ################################################################################################

    # Initialization if no 'Simplification'
    """
    # ---- # Compute for the two component for the generating plan # ---- #
    # According to 'Wake Meandering: A Pragmatic Approach' (2008) by Larsen and co.
    # We deal just with v, w component
    for char in ['vfluct', 'wfluct']:
        MannBox.plan_of_interest = get_plan_of_interest(MannBox, ti=0, component_char=char)

        # ---- # Interpolation Part (WakeCentered) # ---- #
        Interpo_Integrate = interpo_integrate()
        Interpo_Integrate = Interpolate_plan(MannBox, Interpo_Integrate, Meand_Mann)

        # ---- # Integration Part # ---- #
        Interpo_Integrate = polar_mesh_value(MannBox, Interpo_Integrate)
        Final_Integral_Value = Trapz_for_Integrate_general_grid(Interpo_Integrate)

        # ---- # Calculate the characteristic velocity # ---- #
        Meand_Mann.init_vc_wc.append(Final_Integral_Value / MannBox.Af)  # [vc, wc]
    #"""

    return MannBox, WindFarm

def Wake_Dynamic_at_Ld(ld, ti, MannBox, Meand_Mann):
    """
    Based on Simplification part of " Pragmatic Approach of wake meandering "
    Double Assumptions:
        - Restricted to wake deficit behaviour at a given downstream distance from the wake generating Wind Turbine
        - Perfect correlation between the characteristic transversal and vertical velocities in all 'cross section'
        of the relevant turbulent box /!\

    "
    A priori, the simplification is believed to be a reasonable approximation for moderate downstream distances,
    where the wake centre displacements are modest, and where the change in the driving large-scale turbulence
    structures therefore also is moderate in the relevant spatial regime. For larger downstream distances, account
    should be taken to the spatial variability of the large-scale turbulence components, and the simplification
    consequently breaks down.
    "
    :param Ld: float
    :return:
    """
    # Caluculation to get Center position directly
    bool_center = False
    # Calculation to get Characteristic Velocities (this way have to be used for the MEANDERING MAIN)
    bool_velocity = True
    # (Ld, y_g(Ld/U; t0+tho), z_g(Ld/U; t0+tho)
    # (y_g, z_g) = Ld/U * [vc(U(T-ti), 0, 0), wc(U(T-ti),0,0)]


    # Determine vc and wc at U(T-ti), 0, 0:
    yc_zc = []
    vc_wc = []
    for char in ['vfluct', 'wfluct']:
        Meand_Mann.wake_center_location = (0, 0) # due to simplification
        MannBox.plan_of_interest = get_plan_of_interest(MannBox, ti=ti, component_char=char)

        # ----# Interpolation Part (WakeCentered) #----#
        Interpo_Integrate = interpo_integrate()
        Interpo_Integrate = Interpolate_plan(MannBox, Interpo_Integrate, Meand_Mann)

        # ----# Integration Part #----#
        Interpo_Integrate = polar_mesh_value(MannBox, Interpo_Integrate)
        Final_Integral_Value = Trapz_for_Integrate_general_grid(Interpo_Integrate)

        # ----# Calculate the characteristic velocity #----#
        if bool_center:
            yc_zc.append(ld/MannBox.U * Final_Integral_Value / MannBox.Af)
        if bool_velocity:
            vc_wc.append(Final_Integral_Value / MannBox.Af)
    if bool_center:
        return yc_zc
    if bool_velocity:
        return vc_wc

def Wake_Dynamic_at_Ld_optim(ti, MannBox, Meand_Mann, Interpo_Integrate):
    """
    Work with new loop. Computation time optimised. Because we don't add some useless interpolation due to the old loop
    :param ld:
    :param ti:
    :param MannBox:
    :param Meand_Mann:
    :return:
    """
    # Caluculation to get Center position directly
    # Calculation to get Characteristic Velocities (this way have to be used for the MEANDERING MAIN)
    bool_velocity = True
    # (Ld, y_g(Ld/U; t0+tho), z_g(Ld/U; t0+tho)
    # (y_g, z_g) = Ld/U * [vc(U(T-ti), 0, 0), wc(U(T-ti),0,0)]

    #ti = ts +delay - tho_ref - tho_rel
    index_tm = int(round(ti/MannBox.dt))
    #print 'index_tm:', index_tm


    # Determine vc and wc at U(T-ti), 0, 0:
    vc_wc = []
    for char in ['vfluct', 'wfluct']:
        if char == 'vfluct':
            Interpo_Integrate.f_cart = Interpo_Integrate.F_tm_fvc_fwc[index_tm][0]
        if char == 'wfluct':
            Interpo_Integrate.f_cart = Interpo_Integrate.F_tm_fvc_fwc[index_tm][1]
        Meand_Mann.wake_center_location = (0, 0)  # due to simplification


        # ----# Integration Part #----#
        Interpo_Integrate = polar_mesh_value(MannBox, Interpo_Integrate)
        Final_Integral_Value = Trapz_for_Integrate_general_grid(Interpo_Integrate)

        # ----# Calculate the characteristic velocity #----#
        if bool_velocity:
            vc_wc.append(Final_Integral_Value / MannBox.Af)
    if bool_velocity:
        return list(vc_wc)
#----------------------# TEST #------------------------#


"""
filename = '1028'       # must come from sDWM Input
R_wt = 46.5             # can come from sDWM
U = 11.7                # can come from sDWM / or LES
WTG = 'NY2'             # can come from sDWM
HH = 90. #Hub height    # can come from sDWM

Rw = 1.  # try with no expansion

WindFarm = windfarm()
WindFarm.U_mean = U
WindFarm.WT_R = R_wt
WindFarm.WT_Rw = Rw
WindFarm.TI = 0.06
#WindFarm.lenght = 4000.

WT = wt.WindTurbine('Windturbine', '../WT-data/'+WTG+'/'+WTG+'_PC.dat',HH,R_wt) # already present in sDWM

########################################################################################################################

start_time = time.time()
TurBox, WindFarm = pre_init_turb(filename, WindFarm, WT)
WindFarm.stream_location_z = [0,  4,  8, 12, 17, 21, 25, 30] # [D]
WAKES = Mann_Main(TurBox, WindFarm)
print time.time() - start_time

print 'Result: ', WAKES
print 'Shape: ', np.shape(WAKES)

if False:
    DATA = WAKES
    print DATA
    np.save('C:/Users/augus/Documents/Stage/Codes/Mann_Turbulence/Result/Center_Position_in_time_Lillgrund/z_time_center_location', DATA)
    print 'Wake Radius Data saved...'
#"""
