from machine import PWM
import time
import math
import uasyncio as asyncio

class Servo:
    def __init__(self,pin,pwm_freq=50, min_ms=1, max_ms=2, range_degrees=90):
        min_duty=1024*min_ms/(1000/pwm_freq)
        max_duty=1024*max_ms/(1000/pwm_freq)
        self.range_degrees=range_degrees
        self.center=(min_duty+max_duty)/2
        self.dev=(max_duty-min_duty)/2
        self.pwm = PWM(pin,freq=pwm_freq, duty=int(self.center))
        
    def set(self,position=None, degrees=None):
        if position is None:
            position=(degrees / self.range_degrees) * 2 - 1
        if abs(position)>1:
            raise ValueError('deviation of {} exceeds range [-1, 1]'.format(position))
        self.pwm.duty(int(self.center+position*self.dev))
    
    def offset(self, position=None, degrees=None):
        if position is None:
            position=(degrees / self.range_degrees) * 2
        self.set(self.position+position)
        self.center+=self.dev*position

    
    @property
    def position(self):
        return (self.pwm.duty()-self.center)/self.dev
    
    @property
    def degrees(self):
        return (self.position+1)/2*self.range_degrees

    async def goto(self,position=None, degrees=None,timespan=1, sleeptime=.1):
        if position is None:
            position=(degrees / self.range_degrees) * 2 - 1
        start_pos=self.position
        direction=position-start_pos
        timespan*=1000 # in ms
        start_time=time.ticks_ms()
        while True:
            passed=time.ticks_diff(time.ticks_ms(), start_time)
            self.set(start_pos+direction*min(1,passed/timespan))
            if passed>=timespan:
                return
            await asyncio.sleep(sleeptime)
         

    async def steps(self,positions=None, degrees=None,sleeptime=.5):
        if positions is None:
            positions=[d / self.range_degrees * 2 - 1 for d in degrees]
        i=0
        while True:
            if i==len(positions):
                i=0
            self.set(positions[i])
            i+=1
            await asyncio.sleep(sleeptime)

    async def sin(self,pos1=-1, pos2=1, freq=1, sleeptime=.1):
        if pos2<pos1:
            pos1, pos2= pos2, pos1
        ampl=(pos2-pos1)/2
        center=(pos1+pos2)/2
        start_dist_rel=abs((self.position-center)/ampl)
        await self.goto(center, timespan=start_dist_rel/freq, sleeptime=sleeptime)
        start_time=time.ticks_ms()
        while True:
            passed=time.ticks_diff(time.ticks_ms(), start_time)
            x=math.sin(passed/1000*2*math.pi*freq)
            self.set(x*ampl +center)
            await asyncio.sleep(sleeptime)
