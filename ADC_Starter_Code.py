
import piplates.ADCplate as ADC
import time

import numpy as np  
import matplotlib.pyplot as plt
plt.ion() # turn on interactive mode
 
addr=0    # This is the address of the ADC plate. Only need to change this if you are controlling multiple plates.
N=1000     # This is the number of data points that you collect before plotting it on the graph. Max value of 4096 points 
data=list()   #initialize the list
 
print(ADC.getID(addr))
ADC.setMODE(addr,'ADV')  


ADC.configINPUT(addr,'D0',13,True)  #Configure D0 input for 1007 sps. See documentation to adjust the samples per second.



while True:
    ADC.startSTREAM(addr,N)    #Start ADC in streaming mode. Flag an event when N data points are collected
    t0=time.time()             #start time tracking
       
    go=True
    while(go):
        while(ADC.check4EVENTS(addr)!=True):   #Check for events
        # Start of foreground tasks
            pass
        # End of foreground tasks
        if (ADC.getEVENTS(addr) & 0x80):       #read event register when event detected. Use 0x80 to ignore possible events from digital pins 
            go=False                           #if the event is == ADCcomplete then get out of while loop and fetch data
    data.extend(ADC.getSTREAM(addr))   
    ADC.stopSTREAM(addr)               #stop the STREAM

    T= time.time()-t0   # Total aquisition time
    Ntot = len(data)   # Total number of readings 
    
    FFT = np.abs(np.fft.fft(data))/Ntot   # Compute abs value of FFT in volts. Double sided
    # Convert to single sided voltage:
    # You must convert Ntot/2_+1 into an integer for it to work with the indices of an array, because its by default a float
    V1 = FFT[0:int(Ntot/2+1)]    # First half is for positive frequency. See this article for more details: https://selfnoise.co.uk/resources/signals-and-dft/dft-even-odd-n/
    # The indicies will change slightly depending on if you have an even or odd number of data points in the time domain
    V1[1:-2]=2*V1[1:-2] # Multiply by 2 except for DC component and Nyquist frequency. -1 represents the end of the array at the Nyquist frequency

    t = np.linspace(0, T, num=Ntot)  #  Time axis in seconds
    freq = 1/T*np.linspace(0, int(Ntot/2+1),int(Ntot/2+1))   # Frequency axis in Hz

    
    plt.figure(1)
    plt.clf()
    plt.plot(t,data)
    plt.xlabel('Time [s]')
    plt.ylabel('Voltage [V]')

    
     

    plt.figure(2)
    plt.clf()
    plt.plot(freq,V1)
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Voltage [V]')
    #plt.ylim((0,0.001))    # This is how you can adjust x and y limits if you want. 
    #plt.xlim((80,110))
    
           
    plt.show()
    plt.pause(0.0001) # Pause for a bit to have a enough time to show the plot. 
    
        
    
    data[0:(N)]= []     # Reset data
    
     
    


