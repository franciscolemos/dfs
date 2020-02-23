import pdb
import datetime
#import fileExport as fE
import time
#import funcsDate as fD
#import initialize as i
from numpy import array
import numpy as np
from pprint import pprint
import pandas as pd


def continuity(flightSchedule):
    flightContList = []
    if not np.all(flightSchedule['destination'][:-1] == flightSchedule['origin'][1:]): #continuity destination of the cur. needs to equal to origin of the next
        for cur, nxt in zip(flightSchedule[:-1], flightSchedule[1:]): #check which flight
            if(cur['destination'] != nxt['origin']):
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