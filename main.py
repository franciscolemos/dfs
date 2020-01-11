# Using a Python dictionary to act as an adjacency list
import pdb
import numpy as np
import repositories.data as data
import repositories.airportCap as aC
from repositories.flightSchedule import fs
import actions.dfs2 as aD
from actions import critical
from actions import domains
#TODO
#Re-factor according to the flighSchedule
#Create the initial solution

solution = {
    '724001/03/08':[],
    '724301/03/08':[],
    '286601/03/08':[],
    '286701/03/08':[],
    '530301/03/08':[],
    '530002/03/08':[],
    'm':[],
    '736602/03/08':[],
    '736902/03/08':[],
    '737002/03/08':[]
}
visited = [] # Array to keep track of visited nodes.
criticalFlight = critical.flightMaint(fs) #define the critical flight
domainsFlights = domains.flights(data.configDic)
fixedFlights = domainsFlights.fixed(fs)
movingFlights = np.setdiff1d(fs, fixedFlights,True)
pdb.set_trace()
#TODO
#(remove flights that can be moved)
#initialize ranges 

index = 0
dfs = aD.dfs(data, solution) #init. class in actions layer
while(index != -1):
    startFlight = data.flightSchedule[index] #starting flight to start the dfs
    index = dfs.dfs(visited, data.graphFs, startFlight)
    if(index != -1): #solution not found
        pass
        #define the critical flight
        #delete the loop files
        #update the flightSchedule with partial solution
        #save the partial solution
        #create new solution from the flightSchedule
    print(dfs.solution)
    pdb.set_trace()
