# boot.py -- run on boot-up

import network
import math
import time
import ntptime
from machine import RTC
import urequests as requests
import uasyncio as asyncio
import json



LIGHTS=[[1,3,4,5], [1,3,4], [1,3],[1,2], [1],[0], [0]]

def TimeoutError(Exception):
    pass

def save_thresholds(temperature=[5,10,15,20,30], rain=.1):
    with open('thresholds.json', 'w') as f:
        f.write(json.dumps({'temperature': temperature, 'rain': rain}))

def get_zone(temperature, rain):
    # zones:>30: sonnenchreme, <30 t-shirt, <20 pulli, rain: regenjacke, <15: jacke,  <10: Mütze,  <5: Handschuhe
    with open('thresholds.json', 'r') as f:
        th = json.loads(f.read().strip())
    print('Thresholds: ', th)
    if temperature < th['temperature'][0]:
        return 0, LIGHTS[0]
    if temperature < th['temperature'][1]:
        return 1, LIGHTS[1]
    if temperature < th['temperature'][2]:
        return 2, LIGHTS[2]
    if rain > th['rain']:
        return 3, LIGHTS[3]
    if temperature > th['temperature'][4]:
        return 6, LIGHTS[6]
    if temperature > th['temperature'][3]:
        return 5, LIGHTS[5]
    return 4, LIGHTS[4]


def save_wifi(ssid=None, pw=None):
    with open('credentials.txt', 'w') as f:
        if ssid is None:
            f.write('')
        else:
            f.write(f'{ssid}\t{pw}')


def read_credentials():
    wlan = list()
    with open('credentials.txt', 'r') as f:
        # this file should contain ssid<space>pw, one per line
        for line in f:
            wlan.append(line.strip().split())
            print(wlan[-1][0])
    try:
        return wlan[-1]
    except IndexError:
        print('no wifi specified')
        return None, None


async def connect_wlan(ssid, pw, timeout=5000):
    if ssid is None:
        return False
    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    print('connecting')
    await asyncio.sleep(0)
    if not sta.isconnected():

        print('connecting to {}'.format(ssid))
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            sta.connect(ssid, pw)
            print('connecting to wlan {}, ip is {}'.format(
                ssid, sta.ifconfig()[0]))
            for i in range(5):
                print('attempt {}, ip is {}'.format(i, sta.ifconfig()[0]))
                if sta.isconnected():
                    return True
                await asyncio.sleep(1)
            print('timeout')
        print('failed to connect')
        return False
    print('connected to wlan, {}'.format(sta.ifconfig()))
    return True

def heatcolor(temp, brightness=255):
    temp=min(max(temp, 0),1)
    if temp<1/3:
        red=.33-.17*temp*3
        green=.33+.66*temp*3
        blue=.66-.51*temp*3
    elif temp<2/3:
        red=.15+.6*(temp-1/3)*3
        green=1-.25*(temp-1/3)*3
        blue=.15-.15*(temp-1/3)*3
    else:
        red=.75+.25*(temp-2/3)*3
        green=.75-.25*(temp-2/3)*3
        blue=0
    return int(red*brightness), int(green*brightness), int(blue*brightness)


def rainbow(pos, brightness):
    red = int(max(1-pos*3, 0, pos*3-2)*brightness)
    green = int((pos*3 if pos < 1/3 else max(2-pos*3, 0))*brightness)
    blue = int((max(pos*3-1, 0) if pos < 2/3 else 3-pos*3)*brightness)
    return [red, green, blue]


def colorband(np, pos=0, colormap=rainbow, np_diff=.05, brightness=64):
    assert brightness < 2**8
    assert 0 <= pos <= 1
    assert np_diff < 1
    for i in range(len(np)):
        pos += np_diff
        if pos > 1:
            pos -= 1
        np[i] = (colormap(pos, brightness))
    np.write()


def kitt(np, pos=0, width=5, brightness=64, color=(1, 0, 0)):
    assert brightness < 2**8
    assert 0 <= pos <= 1
    scale = brightness/sum(color)
    pos = pos*(len(np)+2)-1
    for i in range(len(np)):
        dist = abs(i-pos)
        if dist > width/2:
            np[i] = [0, 0, 0]
        else:
            hann = 1/2+1/2*math.cos(2*math.pi*dist/width)
            np[i] = [int(c*scale*hann) for c in color]
    np.write()


async def np_animation(np, fun=colorband, steps=10, back=False, sleeptime=.1, *args, **kwargs):
    pos = 0
    while True:
        for pos in range(steps+1):
            fun(np, pos/steps, *args, **kwargs)
            await asyncio.sleep(sleeptime)
        if back:
            for pos in reversed(range(steps+1)):
                fun(np, pos/steps, *args, **kwargs)
                await asyncio.sleep(sleeptime)


def is_dst(m, d, wd):
    '''is daylight saving?'''
    if m < 3:
        return False
    if m > 10:
        return False
    if m > 4 and m < 9:
        return True
    # last sunday in Mar/Oct at 2am
    days_to_month_end = 31-d
    days_to_sunday = 6-wd
    # two hours to eraly, but good enough
    if (m == 3 and days_to_month_end >= days_to_sunday) or (m == 10 and days_to_month_end < days_to_sunday):
        return False
    return True


WOCHENTAG = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']


def set_local_time():
    # if needed, overwrite default time server
    ntptime.host = "1.europe.pool.ntp.org"
    try:
        # make sure to have internet connection
        ntptime.settime()
        rtc = RTC()
        _, m, d, _, _, _, wd, _ = time.localtime()
        timezone_diff = +2 if is_dst(m, d, wd) else +1   # CEST or CET
        sec = ntptime.time()
        y, m, d, h, minute, sec, wd, yd = time.localtime(
            int(sec + timezone_diff*3600))
        rtc.datetime((y, m, d, wd, h, minute, sec, 0))
        #rtc.datetime((year, month, day, 0, hours, minutes, seconds, 0))
        now = time.localtime()
        print("Local time after synchronization: {8},  {2}.{1}.{0}, {3}:{4}:{5} Uhr ".format(
            *now, WOCHENTAG[now[6]]))
    except Exception as e:
        print("Error syncing time: ", e)


def get_weather(lat='52.44063307786537', lon='13.31702513975539'):
    url = 'https://api.brightsky.dev/current_weather?lat={lat}&lon={lon}'
    resp = requests.get(url.format(lat=lat, lon=lon))
    weather = resp.json()['weather']
    return weather

def get_weather_fc(lat='52.44063307786537', lon='13.31702513975539'):
    y, m, d, h, _, _, wd, _ = time.localtime()
    time_offset = '+02' if is_dst(m, d, wd) else '+01'
    start = '{y}-{m}-{d}T{h}:00{offset}:00'.format(
        y=y, m=m, d=d, h=h, offset=time_offset)
    last = '{y}-{m}-{d}T{h}:00{offset}:00'.format(
        y=y, m=m, d=d, h=h+1, offset=time_offset)
    url = 'https://api.brightsky.dev/weather?lat={lat}&lon={lon}&date={date}&last_date={last}'
    resp = requests.get(url.format(lat=lat, lon=lon, date=start, last=last))
    weather = resp.json()['weather'][0]
    return weather
