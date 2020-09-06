# Using a Python dictionary to act as an adjacency list
import pdb
import numpy as np
from recovery.repositories import *
import recovery.actions.funcsDate as fD
from recovery.actions import scenario
from datetime import datetime
from recovery.actions import domains #domains is updated at each iteration
from recovery.actions import feasibility
from recovery.actions import solution
from recovery.actions import solutionUtils
from recovery.actions import cost
import random
import copy
import time
from itertools import product
from recovery.dal.classesDtype import dtype as dt
from recovery.actions.funcsDate import int2DateTime
import pandas as pd
import collections

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
        flightOrder =  collections.OrderedDict(sorted(self.flightDic.items())) #order dictionary
        self.maxFlight = flightOrder.popitem()[0] #get the value for the last key = max. flight
        self.aircraftDic, self.aircraftSA = readAircrafts.readAircrafts(path, "aircraft.csv", self.minDate).read2Dic()
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
        self.airportOriginaltDic = readAirports.readAirports(path, "airports.csv", noDays, self.altAirportSA, []).read2Dic() #does not include noDep/noArr 

        scenario.echo(len(self.flightDic), len(self.aircraftDic), len(self.airportOriginaltDic),
                    len(self.itineraryDic),
                    #-1,
                    len(self.altFlightDic), len(self.altAircraftDic),
                    len(self.altAirportSA), noDays - 1)

        self.domainFlights = domains.flights(self.configDic)

        self.solutionARP = {}

    def initialize(self, aircraft, airportDic, delta = 1, saveAirportCap = True): #check if the roation is feasible
        rotationOriginal = self.fSNOTranspComSA[self.fSNOTranspComSA['aircraft'] == aircraft]

        #rotationOriginal = rotationOriginal[rotationOriginal['flight']!= ''] #remove created flights
        if len(rotationOriginal[rotationOriginal['flight'] == '']):
            aircDisr =  self.altAircraftDic.get(aircraft, None) #check if the airc. has broke period
            if aircDisr != None: #check if the airc. has broke period
                rotationOriginal, self.maxFlight = solution.newAircraftFlights(rotationOriginal, self.distSA, 
                self.maxFlight, aircDisr['endInt'], self.configDic) #create new flights and update self.maxFlight
                solution.verifyNullFlights(rotationOriginal)#verify if there are any null flights

                #consider using available airc.
                #generates feasible solution however it is not appropriate to handle other types of disruption
                #it is necessary to implement GA
            else: #the fligth has been cancelled
                rotationOriginal, self.maxFlight = solution.newFlights(rotationOriginal, self.distSA, 
                self.maxFlight, -1, self.configDic)
        
        rotation = rotationOriginal[(rotationOriginal['cancelFlight'] == 0) ] #only flying flights
        rotation = np.sort(rotation, order = 'altDepInt') #sort ascending
        #check rotation feasibility
        infContList = feasibility.continuity(rotation) #cont.
        infTTList = feasibility.TT(rotation) #TT
        
        rotationMaint = np.sort(self.aircraftScheduleDic[aircraft], order = 'altDepInt') #select the aircr. and sort the rotation
        self._rotationMaint = rotationMaint[rotationMaint['flight'] == 'm'] #find if the rotation has maint. scheduled
        infMaintList = []
        if len(self._rotationMaint) > 0:
            infMaintList = feasibility.maint(rotationMaint) # find if maint. const. is infeas.
        
        infDepList = feasibility.dep(rotation, airportDic, delta) #airp. dep. cap.
        infArrList = feasibility.arr(rotation, airportDic, delta) #airp. arr. cap.
        
        try:
            feasible = len(infContList) + len(infTTList) + len(infMaintList) + len(infDepList) + len(infArrList)

            #print("feasible:", len(infContList), len(infTTList), len(infMaintList), len(infDepList), len(infArrList))
            if feasible == 0:
                if saveAirportCap:
                    self.solutionARP[aircraft] = rotationOriginal #save the feasible rotation w/ cancelled flights
                    solution.saveAirportCap(rotation, airportDic) #update the airp. cap. only w/ cancelFlight == 0
                return -1, [] #for repair to determine if the problem is dep. or arr.
            else:
                #print("infeasiblities:", infContList, infTTList, infMaintList, infDepList, infArrList)
                index = min(np.concatenate((infContList, infTTList, infMaintList, infDepList, infArrList), axis = None)) #find tme min. index; wgere the problem begins
                #firstFlight = rotationOriginal[rotationOriginal['depInt'] >= self.configDic['startInt']][0]
                #index = np.in1d(rotationOriginal, firstFlight).nonzero()[0]
                return int(index), rotationOriginal #because it has to include the aircraft to export the solution
        except Exception as e:
            print("Exception initialize:", e)
            import pdb; pdb.set_trace()
        #visualize the graphs
    
    def addMaint(self, aircraft):
        rotationMaint = np.zeros(1, dt.dtypeFS)
        rotationMaint['aircraft'][0] = aircraft
        rotationMaint['flight'][0] = 'm'
        rotationMaint['origin'][0] = self._rotationMaint['origin'][0]
        rotationMaint['depInt'][0] = self._rotationMaint['depInt'][0]
        rotationMaint['altDepInt'][0] = self._rotationMaint['altDepInt'][0]
        rotationMaint['destination'][0] = self._rotationMaint['destination'][0]
        rotationMaint['arrInt'][0] = self._rotationMaint['arrInt'][0]
        rotationMaint['altArrInt'][0] = self._rotationMaint['altArrInt'][0]
        return rotationMaint

    def loopAircraftList(self, aircraftList, airportDic): 
        import copy; aircraftTmpList = copy.deepcopy(aircraftList)
        solutionKpiExport = []
        noFlights = 0
        noCancelledFlights = 0
        aircraftSolList = [] #list of aircraft that have a feasibe rotation
        _noCombos = 0.1 #order of magnitude for the no. of combos
        infAirc = []
        feasible = -1
        while len(aircraftSolList) != len(aircraftList): #verify if the lists have the same size
            remainAirc = len(list(set(aircraftList) - set(aircraftSolList)))
            for aircraft in aircraftTmpList: #iterate through the aircraft list
                print(aircraft)
                if('TranspCom' in aircraft): #immediatly add the surface transport
                    aircraftSolList.append(aircraft)
                    rotation = self.flightScheduleSA[self.flightScheduleSA['aircraft'] == aircraft]
                    self.solutionARP[aircraft] = rotation
                    continue
                index, rotationOriginal  = self.initialize(aircraft, airportDic) #save a feasible rotation or return the index of inf.
                if(index != -1): #search the solution
                    #import pdb; pdb.set_trace()
                    rotation = copy.deepcopy(rotationOriginal) #copy the original rotation 
                    fixedFlights = self.domainFlights.fixed(rotation[index:]) #find the fixed flights: disrupted and outside RTW
                    if fixedFlights.size == 0: #if there are no fixed flights
                        movingFlights = rotation[index:]
                    else:#if there are fixed flights remove them from the remianing rotation
                        movingFlights = np.setdiff1d(rotation[index:], fixedFlights) 
                    airpCapCopy = copy.deepcopy(airportDic) #copy the airp. cap. solution
                     #flight ranges and combinations only for moving flight after disruption index with updated airp. cap. for fixed flights
                    flightRanges, noCombos, singletonList = self.domainFlights.ranges(rotation[index:], airpCapCopy, _noCombos)
                    
                    if noCombos == -1: #excssive no. combos
                        continue #resume next aircraft
   
                    while len(singletonList) >= 1: #[(flight, 'dep')]
                        #import pdb; pdb.set_trace()
                        airc2Cancel = solution.singletonRecovery(self.solutionARP, singletonList, airpCapCopy, self.configDic) 
                        if airc2Cancel == -1:
                            import pdb; pdb.set_trace()
                            return 1, aircraft, _noCombos, len(aircraftSolList),  noFlights, noCancelledFlights
                        else:
                            print("airc2Cancel: ", airc2Cancel)
                            airportDic = copy.deepcopy(airpCapCopy) #update airportDic
                            aircraftSolList = list(set(aircraftSolList) - set([airc2Cancel])) #remove the aircraft from aircraftSolList
                            rotationPop = self.solutionARP.pop(airc2Cancel, None) #remove the rotation from self.solutionARP
                            flightRanges, noCombos, singletonList = self.domainFlights.ranges(rotation[index:], airpCapCopy) #_noCombos = -1, delta = 1

                    start = time.time()

                    solution.verifyFlightRanges(flightRanges, rotation, index) #check if flight ranges has the same size of rotation[index:]
                    
                    rotationMaint = []
                    if len(self._rotationMaint) > 0:
                        rotationMaint = self.addMaint(aircraft) #creates the maint to be later added to the rotation
                    flightCombinations = product(*flightRanges.values()) #find all the combinations
                    solutionValue = [] #initializes the solution value for later appraisal

                    for combo in flightCombinations: #loop through the possible combinations
                        allConstraints = feasibility.allConstraints(rotationOriginal, combo, index
                        , movingFlights, fixedFlights, airpCapCopy, self._rotationMaint, rotationMaint) #check the sol. feas.
                        if allConstraints == -1:
                            continue
                        if allConstraints == -2: #airp. cap. problem
                            return 1, aircraft, _noCombos, len(aircraftSolList),  noFlights, noCancelledFlights 
                        solutionValue.append(solution.value(combo))
                    try:
                        df = pd.DataFrame(solutionValue)
                        df = df.sort_values(by=[0, 1], ascending=[False, True])
                    except:
                        #import pdb; pdb.set_trace()
                        infAirc.append([aircraft, rotationOriginal, index])
                        print(infAirc)
                        feasible = -2
                        aircraftSolList.append(aircraft) 
                        continue
                        #return 1, aircraft, _noCombos, len(aircraftSolList),  noFlights, noCancelledFlights 
                        #import pdb; pdb.set_trace()
                                      
                    solution.newRotation(df.iloc[0][2], rotationOriginal[index:]) #generates the best rotation
                    
                    
                    solRot = rotationOriginal[rotationOriginal['cancelFlight'] == 0] #later will be used to pick first flight
                    solRot = np.sort(solRot, order = 'altDepInt')
                    originAirport = self.aircraftDic[aircraft]['originAirport']
                    initPosFeas = feasibility.initialPosition(solRot[0], originAirport)
                    if len(initPosFeas) > 0: #infeas. init. pos.
                        solutionUtils.wipRecover()
                        distInitRot = self.distSA[(self.distSA['origin'] == originAirport) & (self.distSA['destination'] == solRot[0]['origin'])]
                        distInitRot = distInitRot['dist'][0]
                        #find airp. time slot for dep. @origin
                        originSlots = airportDic[originAirport]
                        originSlots = originSlots[originSlots['endInt'] < (solRot[0]['altDepInt'] - distInitRot)]
                        originSlots = originSlots[originSlots['capDep'] > originSlots['noDep']]
                        #find airp. time slot for arr. @dest.
                        destSlots = airportDic[solRot[0]['origin']]
                        destSlots = destSlots[destSlots['startInt'] < solRot[0]['altDepInt']]
                        destSlots = destSlots[destSlots['capArr'] > destSlots['noArr']]

                        otherIntervals = []
                        i = -1; offset = -1
                        for x in destSlots: #instatiate dest. slots
                            otherIntervals.append(solutionUtils.interval(x['startInt'], x['endInt']))
                        for os in originSlots:
                            obj1 = solutionUtils.interval(os['startInt'], os['endInt']) + distInitRot #start end dist
                            try: 
                                i, offset = obj1.findIntersection(otherIntervals)
                                print(i, offset, os)
                                break
                            except:
                                continue
                        if i != -1: #check if there is a taxi flight
                            taxiFlight = np.zeros(1, dtype = dt.dtypeFS)
                            taxiFlight[0] = copy.deepcopy(solRot[0])

                            taxiFlight['origin'] = originAirport
                            taxiFlight['depInt'] = os['startInt'] + offset #dep.
                            taxiFlight['altDepInt'] = taxiFlight['depInt'] # alt dep.

                            flightDate = int2DateTime(taxiFlight['depInt'][0], self.configDic['startDate']) #datetime when the broken period ends
                            flightDate = flightDate.strftime('%d/%m/%y') #because the sol.checker has a bug
                            self.maxFlight += 1
                            flight = str(self.maxFlight) + flightDate

                            taxiFlight['destination'][0] = solRot[0]['origin'] #origin of the first flight in sol. rot.
                            taxiFlight['arrInt'] = taxiFlight['depInt'][0] + distInitRot
                            taxiFlight['altArrInt'] = taxiFlight['arrInt'][0]
                            taxiFlight['flight'] = flight
                            taxiFlight['cancelFlight'] = 0
                            taxiFlight['newFlight'] = 1
                            taxiFlight['altAirc']  = 0
                            taxiFlight['altFlight'] = 0
                            rotationOriginal = np.concatenate((rotationOriginal, taxiFlight))
                            
                        else: #cancel the rotation
                            print("No available taxi flight")
                            for sr in solRot:
                                if sr['origin'] != originAirport:
                                    sr['cancelFlight'] = 1
                                else:
                                    break
                            rotationOriginal[rotationOriginal['cancelFlight'] == 0] = solRot
                            #import pdb; pdb.set_trace()

                        print("inf. init. pos.")
                        #import pdb; pdb.set_trace()    

                    self.solutionARP[aircraft] = rotationOriginal #save the feasible rotation (to be replaced) 
                    solution.saveAirportCap(rotationOriginal, airportDic) # update the airp. cap.(to be replaced)
                    noFlights += len(rotationOriginal[rotationOriginal['cancelFlight'] == 0])
                    noCancelledFlights +=  len(rotationOriginal[rotationOriginal['cancelFlight'] == 1])

                    delta1 = time.time() - start

                    solutionKpiExport.append([aircraft, delta1, len(flightRanges), noCombos, singletonList, len(solutionValue)])

                else:
                    rotation = self.fSNOTranspComSA[self.fSNOTranspComSA['aircraft'] == aircraft]
                    noFlights += len(rotation[rotation['cancelFlight'] == 0] )
                    noCancelledFlights += len(rotation[rotation['cancelFlight'] == 1])
                #import pdb; pdb.set_trace()
                aircraftSolList.append(aircraft) #add the aircraft w/ feasible solution
                print(aircraft, len(aircraftSolList), _noCombos)
            
            #import pdb; pdb.set_trace()
            _noCombos += 0.1 #increase the order of magnitude of the no. of combos
            aircraftTmpList = list(set(aircraftList) - set(aircraftSolList)) #check the differences between two lists
            aircraftTmpList.sort()

        dfSolutionKpiExport = pd.DataFrame(solutionKpiExport, columns = ["aircraft", "delta1", "noFlights", "noCombos", "singletonList", "noSolutions"])
        dfSolutionKpiExport.to_csv("dfSolutionKpiExport02.csv", header = True, index = False)

        return [feasible, infAirc]


    def findSolution(self):
        print("go delta1 aircraft _noCombos noAircrafts  noFlights noCancelledFlights ")
        solutionFound = [0]
        aircraftList = self.aircraftSA['aircraft'] 
        #aircraftList = list(self.aircraftDic.keys())
        #import pdb; pdb.set_trace()
        go = 0
        while solutionFound[0] != -1:
            start = time.time()
            go += 1
            #aircraftList.sort()
            #random.seed(go)
            #random.shuffle(aircraftList)
            self.solutionARP = {}
            airportDic = copy.deepcopy(self.airportOriginaltDic)
            solutionFound = self.loopAircraftList(aircraftList, airportDic) #airportDic will be updated
            #import pdb; pdb.set_trace()
            if solutionFound[0] == -1:
                print("Partial feasible solution found!!!")
                solutionARP = []
                for rotation in self.solutionARP.values(): #convert the sol. into no array
                    solutionARP.append(rotation)
                self.fSNOTranspComSA = np.concatenate(solutionARP).ravel()

                #verify the partial solution
                for aircraft in aircraftList: #verify if the solution is feasible
                    if('TranspCom' in aircraft):
                        continue
                    index, rotationOriginal = self.initialize(aircraft, airportDic, 0, False)
                    if(index != -1):
                        print('infeasible partial solution')
                        import pdb; pdb.set_trace()
                        fixedFlights = self.domainFlights.fixed(rotationOriginal[index])
                        if fixedFlights['flight'] == rotationOriginal[index]['flight']:
                            continue
                        print(aircraft)
                        foundIndex = np.in1d(self.fSNOTranspComSA, rotationOriginal[index:]).nonzero()[0] #find the indices that need to be deleted
                        self.fSNOTranspComSA = np.delete(self.fSNOTranspComSA, foundIndex) #delete the indices
                        for  flight in rotationOriginal[index:]:
                            flight['cancelFlight'] = 1

                        self.fSNOTranspComSA = np.concatenate((self.fSNOTranspComSA, rotationOriginal[index:])) #add the new rotation to the solution

                        solution.airpCapRemove(rotationOriginal[index:], airportDic) #update airp. cap.
                        #import pdb; pdb.set_trace()
                        #self.repair(rotationOriginal[index:], airportDic)
                
                self.solutionARP = self.fSNOTranspComSA
            else:
                print("Inf. sol.")
                import pdb; pdb.set_trace()
            delta1 = time.time() - start
            print(go, delta1, solutionFound)
            #cost.total()
    
    def repair(self, rotation, airportDic):
        #cancel all the flights until the end of the rotation
        for  flight in rotation:
            flight['cancelFlight'] = 1
        solution.airpCapRemove(rotation, airportDic) #remove the remaining part of the rotation

if __name__ == "__main__":
    
    for path in paths.paths:

        start = time.time()
        dataSet = path.split("/")[-1]
        print("Dataset: ", dataSet)
        arp = ARP(path)
        # #cost.total(arp.flightScheduleSA, arp.itineraryDic, arp.configDic)
        arp.findSolution()
        #solution.export2CSV(arp.solutionARP, dataSet)
        #arp.solutionARP = solution.importCSV(dataSet)
        solution.updateItin(arp.solutionARP, arp.itineraryDic)
        solution.export(arp.solutionARP, arp.itineraryDic, arp.minDate, path)
        delta1 = time.time() - start
        print("Solution time for the ARP: ", delta1)