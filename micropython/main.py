# main.py -- put your code here!
from servo import Servo
from display import Display
import neopixel
import time
from machine import deepsleep, Pin, I2C, ADC
import esp32
import utils
from utils import save_wifi as wifi
from utils import save_thresholds

from bitmap import BitMap
import uasyncio as asyncio

# initialization
wakeup_pin = Pin(4, Pin.IN, pull=Pin.PULL_UP,value=1, hold=True)

power_pin = Pin(33, Pin.OUT, value=1)  # activate VBAT
battery_pin = ADC(Pin(35), atten=ADC.ATTN_11DB)
vbat = battery_pin.read_uv()/1000000*2
print('battery voltage: {}V'.format(vbat))
i2c = I2C(0, scl=Pin(22), sda=Pin(21))
display = Display(i2c, 128, 40, False, start_msg=None)
# battery between 3.5 (empty) and 4V (full)
display.battery(80, 10, charge=max(0, min(100, (vbat-3.5)/.5*100)))
display.text('{:.1f}V'.format(vbat),80, 24)
if vbat < 3.5:
    display.show()
    power_pin.value(0)  # VBat inactive
    
    esp32.wake_on_ext0(pin = wakeup_pin, level = esp32.WAKEUP_ALL_LOW)
    time.sleep(3)
    display.poweroff()
    deepsleep()


np = neopixel.NeoPixel(Pin(17), 6)
servo = Servo(pin=Pin(16), pwm_freq=50, min_ms=.4,
              max_ms=2.15, range_degrees=90)


# shutdown 
def shutdown():
    for i in range(len(np)):
        np[i] = 0, 0, 0
    np.write()
    servo.pwm.deinit()
    print('go to sleep...')
    power_pin.value(0)  # inactive
    # _ = wakeup_pin.irq(handler=None, trigger=Pin.IRQ_FALLING,
    #                   wake=DEEPSLEEP)  # configure wakeup
    esp32.wake_on_ext0(pin = wakeup_pin, level = esp32.WAKEUP_ALL_LOW)
    display.poweroff()
    
    deepsleep()
icon_names = [['cloud', 'rainbow', 'snow', 'clear-day'], ['cloudy', 'rain', 'cloudy-wind', 'wind'],
              ['partly-cloudy-day', 'clear-night', 'sleet', 'degree'], ['unknown', 'wifi', 'None', 'None']]
icons_all = BitMap.from_file('weather-icon-set.bmp')
icons = {}

for i in range(4):
    for j in range(4):
        if icon_names[i][j] != 'None':
            icons[icon_names[i][j]] = icons_all.crop(30*j, 30*i, 30, 30)

icons['partly-cloudy-night'] = icons['partly-cloudy-day']
icons['fog'] = icons['cloud']
icons['hail'] = icons['snow']
icons['thunderstorm'] = icons['rain']

numbers_all = BitMap.from_file('numbers.bmp')
numbers = {}
for i in range(10):
    numbers[str(i)] = numbers_all.crop(20*i, 0, 20, 30)
numbers[','] = numbers_all.crop(200, 0, 10, 30)
numbers['.'] = numbers_all.crop(210, 0, 10, 30)
numbers['-'] = numbers_all.crop(220, 0, 15, 30)
del numbers_all


del icons_all
# del icon_names
gc.collect()

# missing icons


display.draw_image(icons['wifi'], 40, 2, invert=True)
display.show()


async def main():
    display_task = asyncio.create_task(display.cycle_images(
        [None, icons['wifi']], 40, 2, invert=True, delay=.2))
    neopixel_task = asyncio.create_task(utils.np_animation(
        np, fun=utils.colorband, steps=30, np_diff=.05, brightness=30))
    # neopixel_task=asyncio.create_task(utils.np_animation(np, fun= utils.kitt,steps=20, back=True, brightness=10))
    servo_task=asyncio.create_task(servo.steps(positions=[0, 1/3, 2/3, 1, 2/3, 1/3, 0,-1/3, -2/3,-1, -2/3, -1/3 ],  sleeptime=1/6))
    connected = False
    connected = await utils.connect_wlan(*utils.read_credentials())
    #await asyncio.sleep(10)
    
    display_task.cancel()
    display.draw_image(icons['wifi'], 40, 2, invert=True)
    if not connected:
        for shift in range(3):
            display.line(39+shift, 2, 69+shift, 32, 1)
            display.line(39+shift, 32, 69+shift, 2, 1)
            display.show()
            
    else:
        #todo: depend on machine.reset_cause() 
        
        #display.fill_rect(0,0,128,32,False)
        display.fill(0)
        display.draw_image( icons['unknown'], 0,2, True)
        display.draw_image( icons['unknown'], 45,2, True)
        display.draw_image( icons['unknown'], 90,2, True)
        #display.text('Messstation',32,24)
        display.show()
        

        wetter = utils.get_weather()
        if wetter['temperature'] is None:
            utils.set_local_time()
            display.fill_rect(0,24,128,8,False)
            display.text('Vorhersage',32,24)
            display.show()
            wetter = utils.get_weather_fc()

        for k, v in wetter.items():
            print('{}: {}'.format(k, v))

        display.fill(0)
        # display.text(['{} and {}'.format(wetter['condition'], wetter['icon']),'{}*C'.format(wetter['temperature'])], valign=1, halign=1)
        # display.draw_image(icons.get(str(wetter.get('icon')), icons['unknown']), 0,2,True)
        print('draw icon')
        display.draw_image(icons.get(str(wetter.get('icon')), icons['unknown']), 0, 0, True)
        offset = 30
        if wetter.get('temperature') is None:
            display.draw_image(icons['unknown'], offset, 2, True)
        else:
            for c in str(wetter['temperature']):
                digit = numbers[c]
                display.draw_image(digit, offset, 2, True)
                offset += digit.width
            display.draw_image(icons['degree'], offset, 2, True)
        rain=wetter.get('precipitation_10', wetter.get('precipitation'))
        if rain:
            msg='{}mm'.format(rain)
            display.fill_rect(0,24,8*len(msg),8,False)
            display.text(msg,0,25)
        display.show()

        temp_range = (5, 25)
        if wetter.get('temperature') is not None and rain is not None:
            servo_task.cancel()
            neopixel_task.cancel()

            zone, lights=utils.get_zone(wetter['temperature'], rain)
            color=utils.heatcolor(wetter['temperature']/30, 50)
            for i in range(6):
                if i in lights:
                    np[i]=color
                else:
                    np[i]=0,0,0
            np.write()
            # servo_pos = ((wetter['temperature']-temp_range[0]) /
            #            (temp_range[1]-temp_range[0])-.5)*2
            servo_pos=(zone-3)/3
            servo_pos = max(min(servo_pos, 1), -1)
            
            servo.set(servo_pos)
    await asyncio.sleep(12)

    neopixel_task.cancel()
    servo_task.cancel()

asyncio.run(main())

# condition: dry┃fog┃rain┃sleet┃snow┃hail┃thunderstorm┃
# icon in clear-day | clear-night | partly-cloudy-day | partly-cloudy-night | cloudy | fog | wind | rain | sleet | snow | hail | thunderstorm




shutdown()