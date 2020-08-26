import datetime
from recovery.dal.classesDtype import dtype as dt
from recovery.actions import solution
import time
import copy
from numpy import array
import numpy as np
from pprint import pprint
import pandas as pd

def previous(flightSchedule):
    previousList = flightSchedule[(flightSchedule['previous'] != '0') & (flightSchedule['previous'] != '')] #because of created flights
    for flight in previousList: #flights w/ previous
        date = flight['flight'][-8:] #get the date
        #import pdb; pdb.set_trace()
        previousFlight = flight['previous'] + date #previous flight
        cancelFlight = flightSchedule[flightSchedule['flight'] == previousFlight]['cancelFlight']
        if (cancelFlight == 1) & (flight['cancelFlight'] != 1):
            return [-1] #next flight not cancelled
    return [] #feasible
def continuity(flightSchedule):
    index =  np.where(flightSchedule['destination'][:-1] != flightSchedule['origin'][1:]) # this matrix will be 1 row smaller 
    if len(index) > 2:
        import pdb; pdb.set_trace()
    return np.asarray(index).flatten() + 1 #the problem is on the next row in the original rotation

def TT(flightSchedule):
    index =  np.where(flightSchedule['altDepInt'][1:] - flightSchedule['altArrInt'][:-1] < flightSchedule['tt'][1:])
    if len(index) > 2:
        import pdb; pdb.set_trace()
    return np.asarray(index).flatten() + 1 #the problem is on the next row in the original rotation

def maint(flightSchedule):
    
    maintStart = flightSchedule[flightSchedule['flight'] == 'm']['altDepInt'][0]
    maintEnd = flightSchedule[flightSchedule['flight'] == 'm']['altArrInt'][0]
    maintOrigin = flightSchedule[flightSchedule['flight'] == 'm']['origin'][0]
    flightBeforeMaint = flightSchedule[(flightSchedule['altDepInt'] <= maintStart) & (flightSchedule['flight'] != 'm')]
    if len(flightBeforeMaint) > 0:
        flightBeforeMaint = flightBeforeMaint[-1]
    else:
        return [-1]
    

    #flights arr. after maint. start
    if (maintStart - flightBeforeMaint['altArrInt'] < 0) | (maintOrigin != flightBeforeMaint['destination']):
        index = np.where(flightSchedule['flight'] == flightBeforeMaint['flight'])
        return np.asarray(index).flatten()
    
    #flights departing during maint.
    flightDuringMaint = flightSchedule[(flightSchedule['altDepInt'] >= maintStart) & (flightSchedule['flight'] != 'm')
        & (flightSchedule['altDepInt'] <= maintEnd)]
    if len(flightDuringMaint) > 0:
        index = np.where(flightSchedule['flight']  == flightDuringMaint['flight'][0] )
        return np.asarray(index).flatten()

    return []

#dep. airp. cap.
def dep(flightSchedule, airportDic, delta = 1):
    flightDepList = []
    flightIndex = 0
    
    for flight in flightSchedule[flightSchedule['flight'] != '']:
        try:
            if flight['cancelFlight'] == 1: continue
            index = int(flight['altDepInt'] / 60)
            noDep = airportDic[flight['origin']][index]['noDep']
            capDep = airportDic[flight['origin']][index]['capDep']
            if noDep + delta > capDep:
                flightDepList.append(flightIndex)
                #import pdb; pdb.set_trace()
            flightIndex += 1
        except:
            print("index is out of bounds")
            import pdb; pdb.set_trace()
    return flightDepList 

#arr. airp. cap.
def arr(flightSchedule, airportDic, delta = 1):
    flightArrList = []
    flightIndex = 0
    
    for flight in flightSchedule[flightSchedule['flight'] != '']:
        if flight['cancelFlight'] == 1: continue
        index = int(flight['altArrInt'] / 60)
        noArr = airportDic[flight['destination']][index]['noArr']
        capArr = airportDic[flight['destination']][index]['capArr']
        if noArr + delta > capArr:
            flightArrList.append(flightIndex)
            #import pdb; pdb.set_trace()
        flightIndex += 1
    
    return flightArrList

def airportCap(airportDic):
    infeasCap = []
    for airport, capArr in airportDic.items():
        for cap in capArr:
            if cap['noArr'] > cap['capArr']:
                print('No. or arr.', cap['noArr'],' is bigger that arr. cap.', cap['capArr'], 'for airport', airport)
                infeasCap.append([airport, cap, 'arr.'])
            if cap['noDep'] > cap['capDep']:
                print('No. or dep.', cap['noDep'],' is bigger that dep. cap.', cap['capDep'], 'for airport', airport)
                infeasCap.append([airport, cap, 'dep.'])
    return infeasCap  

def allConstraints(rotationOriginal, combo, index, movingFlights, fixedFlights, airpCapCopy, _rotationMaint, rotationMaint):
    rotation = copy.deepcopy(rotationOriginal) #keep a copy of the original because of new rotation
    solution.newRotation(combo, rotation[index:]) #add the combo to the rotation
    solution.verifyCombo(combo, rotation, index) #compare the size of combo w/ rotation
    solution.verifyRotation(rotation, movingFlights, fixedFlights, index) #compare rotation size w/ ...
    rotationCopy = copy.deepcopy(rotation[rotation['cancelFlight'] != 1]) #only flights not cancelled in the copy
    rotationCopy = np.sort(rotationCopy, order = 'altDepInt')
    
    if len(continuity(rotationCopy)) > 0: #only flights not cancelled in the copy
        return -1 #cont.
    if len(TT(rotationCopy)) > 0: #only flights not cancelled in the copy
        return -1

    if (len(dep(rotationCopy, airpCapCopy)) > 0) | (len(arr(rotationCopy, airpCapCopy)) > 0):
        import pdb; pdb.set_trace()
        return -2                    
    if len(rotation[(rotation['previous'] != '0') & (rotation['previous'] != '')]) > 0: # because previous flight exist
        if len(previous(rotation)) > 0:
            return -1

    if (len(_rotationMaint) > 0):
        rotationMaintConcat = np.concatenate((rotationCopy, rotationMaint))
        rotationMaintConcat = np.sort(rotationMaintConcat, order = 'altDepInt')
        infMaintList = maint(rotationMaintConcat)
        if len(infMaintList) > 0:
            return -1

class ARP():

    def __init__(self, aircraftScheduleDic, flightRotationDic, infeasCapDepSA, infeasCapArrSA):
        self.aircraftScheduleDic = aircraftScheduleDic #{aircraft:[idFlight, date, origin, depInt, altDepInt, destination, arrInt, altArrInt], delay, broken, cancelFlight]}
        self.flightRotationDic = flightRotationDic #{flightDate:aircraft}
        self.infeasCapDepSA = infeasCapDepSA
        self.infeasCapArrSA = infeasCapArrSA
        self.infDic = {}
        for aircraft, flightSchedule in self.aircraftScheduleDic.items(): #run through the aircraft schedule
            flightSchedule = flightSchedule[flightSchedule['cancelFlight'] == 0] #only flying flights
            flightSchedule = np.sort(flightSchedule, order = 'altDepInt') #sort ascending
            self.infDic[aircraft] = {} #gets the infea. for each aircraft
            infContList = self.continuity(flightSchedule) #check continuity
            if infContList != None:
                self.infDic[aircraft]['cont'] = infContList
            infTTList = self.TT(flightSchedule)
            if infTTList != None:
                self.infDic[aircraft]['tt'] = infTTList
            if len(infeasCapDepSA) > 0:
                #airp. dep. cap.
                infDepList = self.capDep(flightSchedule)
                if len(infDepList) > 0:
                    self.infDic[aircraft]['capDep'] = infDepList
            if len(infeasCapArrSA) > 0:
                #airp.arr. cap.
                infArrList = self.capArr(flightSchedule)
                if len(infArrList) > 0:
                    self.infDic[aircraft]['capArr'] = infArrList
            #maint.
            
            if len(self.infDic[aircraft]) == 0: #clean dict. from empty values
                self.infDic.pop(aircraft, None)                

    def continuity(self, flightSchedule):
        if not np.all(flightSchedule['destination'][:-1] == flightSchedule['origin'][1:]): #continuity destination of the cur. needs to equal to origin of the next
            flightContList = []
            for cur, nxt in zip(flightSchedule[:-1], flightSchedule[1:]): #check which flight
                if(cur['destination'] != nxt['origin']):
                    #flightPair = flightSchedule[(flightSchedule['flight'] == cur['flight']) | (flightSchedule['flight'] == nxt['flight'])] #keep data as structured array
                    #flightContList.append(flightPair) #append the 2 structured arrays
                    #flightContList.append([cur['destination'], nxt['origin']]) #append the 2 structured arrays
                    flightContList.append(nxt['flight']) #append the flight
            return flightContList          

    def TT(self, flightSchedule):
        if not np.all(flightSchedule['altDepInt'][1:] - flightSchedule['altArrInt'][:-1] >= flightSchedule['tt'][1:]): #tt between two consecutive flights
            #pdb.set_trace()
            flightTTList = []
            for cur, nxt in zip(flightSchedule[:-1], flightSchedule[1:]): #check which flight
                if(nxt['altDepInt'] - cur['altArrInt'] < nxt['tt']):
                    #flightPair = flightSchedule[(flightSchedule['flight'] == cur['flight']) | (flightSchedule['flight'] == nxt['flight'])] #keep data as structured array
                    #flightTTList.append(flightPair) #append the 2 structured arrays
                    #flightTTList.append([cur['destination'], nxt['origin']]) #append the 2 structured arrays
                    flightTTList.append(nxt['flight']) #append the flight
            return flightTTList

    def capDep(self,flightSchedule):
        flightDepList = []
        for flight in flightSchedule:
            if self.infeasCapDepSA[(flight['altDepInt'] >= self.infeasCapDepSA['startInt']) & 
                (flight['altDepInt'] < self.infeasCapDepSA['endInt']) &
                (flight['origin'] == self.infeasCapDepSA['airport'])]:
                flightDepList.append(flight)
        return flightDepList

    def capArr(self,flightSchedule):
        flightArrList = []
        for flight in flightSchedule:
            if self.infeasCapArrSA[(flight['altArrInt'] >= self.infeasCapArrSA['startInt']) & 
                (flight['altArrInt'] < self.infeasCapArrSA['endInt']) &
                (flight['origin'] == self.infeasCapArrSA['airport'])]:
                flightArrList.append(flight)
        return flightArrList

    def maintenance(self, rotationList):
        pass