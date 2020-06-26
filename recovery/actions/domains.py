import numpy as np
import copy
from recovery.repositories.data import maxDelay
from recovery.repositories.data import deltaT
from recovery.actions import feasibility

class flights:
    def __init__(self, configDic):
        self.configDic = configDic
        self.fsFixed = []
        self.criticalFligh = []

    def fixed(self, fs): #flights that cannot be moved => empty domains
        #import pdb; pdb.set_trace()
        fsOutRTW = fs[(fs['altDepInt'] < self.configDic['startInt']) | #flights outside RTW
                (fs['altDepInt'] > self.configDic['endInt'])] #flights outside RTW
        fsFixed = fs[(fs['depInt'] != fs['altDepInt']) & #flight is delayed
                    #(fs['broken'] != 1) & #flight not broken
                    (fs['cancelFlight'] != 1) & #flight not cancelled
                    ((fs['altDepInt'] >= self.configDic['startInt']) & #flight inside RTW
                    (fs['altDepInt'] <= self.configDic['endInt']))] #flight inside RTW
        fsMaint = fs[fs['flight'] == 'm'] #maint. is assumed to be a fixed flight
        self.fsFixed = np.concatenate([fsOutRTW, fsFixed, fsMaint])
        return self.fsFixed #return first set of flights that

    def remove(self, airportCap, movingFlights):
        for f in movingFlights:
            origin = f['origin']
            dep = f['altDepInt']
            airportCap[origin][int(dep/60)]['noDep'] -= 1
            destination = f['destination']
            arr = f['altArrInt']
            airportCap[destination][int(arr/60)]['noArr'] -= 1
        self.airportCap = copy.deepcopy(airportCap)
        return self.airportCap

    def criticalMaint(self):
        maintFlight = self.fs[self.fs['flight'] == 'm'] 
        airp = maintFlight['origin'][0]
        startInt = maintFlight['depInt'][0]
        self.criticalFligh = self.fs[(self.fs['destination'] == airp) & (self.fs['altArrInt'] <= startInt)][-1]
        #TODO
        #Initialize the domain
        return self.criticalFligh
    
    def ranges(self, rotation, airportDic, _noCombos, delta = 1): #only complying with airp. cap.
        domains = {}
        noCombos = 1
        singletonList = []
        try:
            for f in rotation: #iterate through the rotation
                domain = [] #initalize the empty domain for each flight
                if f['cancelFlight'] != 0:
                    continue
                if f['altDepInt'] != f['depInt']: #because it is a fixed flight
                    # print("Singleton!!!")
                    # import pdb; pdb.set_trace()
                    domain.append(0) #the only delay is zero
                    domains[f['flight']] = domain # because of combos
                    if len(feasibility.dep(rotation, airportDic)) > 0:
                        print("Singleton found with necessary backtracking for dep.")
                        singletonList.append([f,'dep'])
                        #import pdb; pdb.set_trace()
                    if len(feasibility.arr(rotation, airportDic)) > 0:
                        print("Singleton found with necessary backtracking for arr.")
                        singletonList.append([f, 'arr'])
                        #import pdb; pdb.set_trace()
                    continue
                if f['depInt'] < self.configDic['startInt']:#because it departs outside the RTW (another singleton)
                    domain.append(0) #the only delay is zero
                    domains[f['flight']] = domain # because of combos
                    if len(feasibility.dep(rotation, airportDic)) > 0:
                        print("Singleton found with necessary backtracking for dep.")
                        singletonList.append([f,'dep'])
                        #import pdb; pdb.set_trace()
                    if len(feasibility.arr(rotation, airportDic)) > 0:
                        print("Singleton found with necessary backtracking for arr.")
                        singletonList.append([f, 'arr'])
                    continue
                if f['depInt'] > self.configDic['endInt']: #because it departs outside the RTW (another singleton)
                    domain.append(0) #the only delay is zero
                    domains[f['flight']] = domain # because of combos
                    if len(feasibility.dep(rotation, airportDic)) > 0:
                        print("Singleton found with necessary backtracking for dep.")
                        singletonList.append([f,'dep'])
                        #import pdb; pdb.set_trace()
                    if len(feasibility.arr(rotation, airportDic)) > 0:
                        print("Singleton found with necessary backtracking for arr.")
                        singletonList.append([f, 'arr'])
                    continue
                domain = [-1] #add flight cancellation
                for t in range(0, maxDelay, deltaT): #find the feasible time slots
                    origin = f['origin']
                    dep = f['altDepInt'] + t
                    destination = f['destination']
                    arr = f['altArrInt'] + t
                    if arr > self.configDic['endInt']: #because the flight arrives outside the RTW
                        break #moves to the next flight  
                    if all([airportDic[origin][int(dep/60)]['noDep'] + delta <= airportDic[origin][int(dep/60)]['capDep'],
                        airportDic[destination][int(arr/60)]['noArr'] + delta <= airportDic[destination][int(arr/60)]['capArr']]):
                        domain.append(t)

                noCombos *= len(domain) #calculate as the end result of the size of the domain
                if noCombos > _noCombos * 10**5:
                    #import pdb; pdb.set_trace()
                    return [],  -1, []
                domains[f['flight']] = domain

        except Exception as ex:
            #print("Exception finding ranges@domains.py", ex.message)
            #import pdb; pdb.set_trace()
            return [],  -1, []

        if noCombos > _noCombos * 10**5:
            print("Excessive2: ", noCombos)
            import pdb; pdb.set_trace()
            return [],  -1

        return domains, noCombos, singletonList