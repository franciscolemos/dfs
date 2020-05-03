# Using a Python dictionary to act as an adjacency list
import pdb
import numpy as np
from recovery.repositories import *
import recovery.actions.funcsDate as fD
from recovery.actions import scenario
from datetime import datetime
from recovery.actions import domains #domains is updated at each iteration
import recovery.actions.dfs2 as aD #it is not necessary to import the entire package, only some modules
from recovery.actions import feasibility
from recovery.actions import solution
import random
import copy
import time
from itertools import product

class ARP:
    def __init__(self, path):
        self.solution = {}
        self.visited = [] # Array to keep track of visited nodes.
        self.criticalFlight = []
        self.fixedFlights = []
        self.movingFlights = []
        self.flightRotationDic = readRotation.readRotation(path, "rotations.csv").read2FlightRotationDic() #{flightDate:aircraft}
        self.minDate = self.flightRotationDic['minDate']
        maxDate = self.flightRotationDic['maxDate']
        self.configDic = readConfig.readConfig(path, "config.csv", self.minDate).read2Dic()
        self.aircraftRotationDic = readRotation.readRotation(path, "rotations.csv").read2AircraftRotationDic() #{aircraft:flightSchedule}
        self.flightDic = readFlights.readFlights(path, "flights.csv").read2Dic()  
        self.aircraftDic = readAircrafts.readAircrafts(path, "aircraft.csv", self.minDate).read2Dic()
        self.altAircraftDic = readAltAircraft.readAltAircraft(path, "alt_aircraft.csv", self.minDate).read2Dic()
        self.altAirportSA = readAltAirports.readAltAirport(path, "alt_airports.csv", self.minDate).read2SA() #atttrib. of SA
        self.altFlightDic = readAltFlights.readAltFlights(path, "alt_flights.csv").read2Dic()
        self.distSA = readDist.readDist(path, "dist.csv").read2SA()
        i = schedules.initialize(self.aircraftRotationDic, self.altAircraftDic, self.altFlightDic, 
            self.aircraftDic, self.flightDic, path, self.minDate)
        i.aircraftSchedule() #included flight and aircr. disr. and, maint. {aircraft:flightSA}
        self.aircraftScheduleDic = i.aircraftScheduleDic #1 aircraft to n flights
        i.flightSchedule()
        self.flightScheduleSA = i.flightScheduleSA #all the flights + room to un-cancel flights for airport cap. purpose
        self.itineraryDic = readItineraries.readItineraries(path,"itineraries.csv").read2Dic()
        #determine the planning horizon
        endDateTime = datetime.combine(datetime.date(self.configDic['endDate']),
            datetime.time(self.configDic['endTime']))
        if maxDate < endDateTime:
            self.flightRotationDic['maxDate'] = endDateTime 
            maxDate = endDateTime 
        noDays = fD.dateDiffDays(maxDate, self.minDate) + 1 # + 1 day for arr. next()
        self.fSNOTranspComSA = self.flightScheduleSA[self.flightScheduleSA['family'] != "TranspCom"]
        self.airportDic = readAirports.readAirports(path, "airports.csv", noDays, self.altAirportSA, []).read2Dic() #does not include noDep/noArr 

        scenario.echo(len(self.flightDic), len(self.aircraftDic), len(self.airportDic),
                    len(self.itineraryDic),
                    #-1,
                    len(self.altFlightDic), len(self.altAircraftDic),
                    len(self.altAirportSA), noDays - 1)

        self.domainFlights = domains.flights(self.configDic)

        self.solutionARP = []

    def initialize(self, aircraft): #check if the roation is feasible
        #TODO
        #check if rotation includes maint.
        #if it includes maint. it has to be removed
        
        rotation = self.fSNOTranspComSA[self.fSNOTranspComSA['aircraft'] == aircraft]
        rotation = rotation[(rotation['cancelFlight'] == 0) & (rotation['flight']!= '')] #only flying flights
        rotation = np.sort(rotation, order = 'altDepInt') #sort ascending
        #check rotation feasibility
        infContList = feasibility.continuity(rotation) #cont.
        infTTList = feasibility.TT(rotation) #TT
        
        rotationMaint = np.sort(self.aircraftScheduleDic[aircraft], order = 'altDepInt') #select the aircr. and sort the rotation
        _rotationMaint = rotationMaint[rotationMaint['flight'] == 'm'] #find if the rotation has maint. scheduled
        infMaintList = []
        if len(_rotationMaint) > 0:
            infMaintList = feasibility.maint(rotationMaint) # find if maint. const. is infeas.
        
        infDepList = feasibility.dep(rotation, self.airportDic) #airp. dep. cap.
        infArrList = feasibility.arr(rotation, self.airportDic) #airp. arr. cap.
        try:
            feasible = len(infContList) + len(infTTList) + len(infMaintList) + len(infDepList) + len(infArrList)

            print("feasible:", len(infContList), len(infTTList), len(infMaintList), len(infDepList), len(infArrList))
            if feasible == 0:
                self.solutionARP.append(rotation) #save the feasible rotation
                solution.saveAirportCap(rotation, self.airportDic) #update the airp. cap.
                return -1, []
            else:
                
                    #print("infeasiblities:", infContList, infTTList, infMaintList, infDepList, infArrList)
                    index = min(np.concatenate((infContList, infTTList, infMaintList, infDepList, infArrList), axis = None)) #find tme min. index; wgere the problem begins
                    return int(index), rotation #because it has to include the aircraft to export the solution
        except Exception as e:
            print("Exception initialize:", e)
            import pdb; pdb.set_trace()
        #visualize the graphs
    
    def findSolution(self):
        
        aircraftList =  list(self.aircraftDic.keys())
        random.shuffle(aircraftList)
        import copy; aircraftTmpList = copy.deepcopy(aircraftList)
        print("rotationSize, noCombos, delta0, delta1")
        aircraftSolList = [] #list of aircraft that have a feasibe rotation
        start = time.time()
        _noCombos = 0.1
        while len(aircraftSolList) != len(aircraftList): #verify if the lists have the same size
            print("No. combos", _noCombos * 10**6)
            for aircraft in aircraftTmpList: #iterate through the aircraft list
                # if aircraft == "A318#33":
                #     import pdb; pdb.set_trace()
                
                index, rotation = self.initialize(aircraft) #save a feasible rotation or return the index of inf.

                if(index != -1): #search the solution
                    fixedFlights = self.domainFlights.fixed(rotation[index:])#find the fixed flights
                    movingFlights = rotation[index:] if fixedFlights.size == 0 else rotation[index:][rotation[index:] != fixedFlights]
                    flightRanges, noCombos = self.domainFlights.ranges(movingFlights, self.airportDic, _noCombos)
                    
                    if noCombos == -1:
                        print("Continue")
                        continue

                    # start = time.time()
                    flightCombinations = product(*flightRanges.values())
                    print("flightCombination: ", noCombos, len(list(set(aircraftList) - set(aircraftSolList))))
                    # delta0 = time.time() - start
                    # start = time.time()
                    
                    for combo in flightCombinations: #generate the possible combinations
                        copyRotation = copy.deepcopy(rotation)
                        # print("combo :", combo)
                        solution.newRotation(combo, copyRotation[index:]) 
                        # print("comboRotation: \n", copyRotation)
                        # import pdb; pdb.set_trace()
                        copyRotation = copyRotation[copyRotation['cancelFlight'] != 1 ]#only with flights not cancelled
                        if len(copyRotation) == len(copyRotation[:index]): #cause the recovery only has cancelled flights
                            # print("only cancelled flights")
                            # import pdb; pdb.set_trace()
                            continue
                        copyRotation = np.sort(copyRotation, order = 'altDepInt')
                        if len(feasibility.continuity(copyRotation)) > 0: continue #cont.
                        if len(feasibility.TT(copyRotation)) > 0: continue
                        infMaintList = []
                        if len(feasibility.dep(copyRotation, self.airportDic)) > 0: continue #airp. dep. cap. (might not be necessary)
                        if len(feasibility.arr(copyRotation, self.airportDic)) > 0: continue #airp. arr. cap. (might not be necessary)
                        print("solution found!!!!")
                        self.solutionARP.append(copyRotation) #save the feasible rotation (to be replaced) 
                        solution.saveAirportCap(copyRotation, self.airportDic) # update the airp. cap.(to be replaced)
                        break
                        #import pdb; pdb.set_trace()
                        
                        



                   
                    #self.solutionARP.append(rotation[index:]) #save the feasible rotation (to be replaced) 
                    #solution.saveAirportCap(rotation[index:], self.airportDic) # update the airp. cap.(to be replaced) 
                    # self.solutionARP.append(rotation[:index]) #save the feasible rotation (to be replaced) 
                    # solution.saveAirportCap(rotation[:index], self.airportDic) # update the airp. cap.(to be replaced)
                aircraftSolList.append(aircraft) #add the aircraft w/ feasible solution
                print(len(aircraftSolList))
            _noCombos += 0.1
            aircraftTmpList = list(set(aircraftList) - set(aircraftSolList)) #check the differences between two lists
        
        delta1 = time.time() - start
        print(len(flightRanges), noCombos, delta0, delta1)
        import pdb; pdb.set_trace()  

if __name__ == "__main__":
    for path in paths.paths:
        #add while loop
        arp = ARP(path)
        arp.findSolution()
        #import pdb; pdb.set_trace()
        solution.export(arp.solutionARP, arp.itineraryDic, arp.minDate, path)