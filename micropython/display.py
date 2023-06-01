import uos, machine
from machine import UART
from machine import Pin
import time
import ssd1306
import math
import uasyncio as asyncio

# class DisplayNotFoundException(Exception):
#    pass

class Display(ssd1306.SSD1306_I2C):
     
    def __init__(self, i2c, width=128, height=64, upsidedown=True, start_msg='starting...'):
        
        devices = i2c.scan()
        
        print('i2c devices found:',len(devices))
        if len(devices)==0:
            #raise DisplayNotFoundException("No I2C devices found")    
            print("no device found, trying 0x3c")
            devices=[0x3c]
        for device in devices: 
            print("Decimal address: ",device," | Hex address: ",hex(device))
        #oled = ssd1306.SSD1306_I2C(128, 64, i2c, 0x3c)
       
        super().__init__(width, height, i2c, devices[0])
        self.set_orientation(upsidedown)
        self.fill(0)
        if start_msg is not None:
            self.text(start_msg,valign=1, halign=1)
        self.show()

    def set_orientation(self, upsidedown):   
        self.upsidedown=upsidedown
        if upsidedown: 
            self.i2c.writeto_mem(self.addr, 0x00, b'\xc0') #flip
            self.i2c.writeto_mem(self.addr, 0x00, b'\xa0') #mirror   
        else:
            self.i2c.writeto_mem(self.addr, 0x00, b'\xc8') #unflip
            self.i2c.writeto_mem(self.addr, 0x00, b'\xa8') #unmirror   
    
    def text(self, text,x1=0, y1=0, x2=None, y2=None, linebreak=True, halign=0, valign=0, linespace=1):
        if x2 is None:
            x2=self.width
        if y2 is None:
            y2=self.height
        lines=[]
        charsize=(8,8)#with x height

        if type(text) is not list:
            text=[text]
        
        if linebreak:
            for l in text:
                while l:
                    br=(x2-x1)//charsize[1]
                    lines.append(l[:br])
                    l=l[br:]
                    #todo implement linebreak at words                    
                
            else:
                lines.append(l)             
        else:
            lines=text
        maxwidth=0
        for l in lines:
            if len(l)*charsize[0]>maxwidth:
                maxwidth=len(l)*charsize[0]
        x=x1
        y=y1
        if valign==2:
            y=y2-(charsize[1]+linespace)*len(lines)
        elif valign==1:
            y=(y1+y2-(charsize[1]+linespace)*len(lines))//2
        for l in lines:
            if halign==2:
                x=x2-charsize[0]*len(l)
            elif halign==1:
                x=(x1+x2-charsize[0]*len(l))//2
            super().text(l, x, y)
            y=y+linespace+charsize[1]
        
        return(x,maxwidth+x,y-(charsize[1]+linespace)*len(lines),y)
        #todo return true x bounding box cordinates in case of halign !=0

    def circle(self, x,y,r,start=0, end=math.pi*2, steps=20):
        theta=[start+i*(end-start)/steps for i in range(1,steps+1)]   
        xprev=x + int(r*math.cos(start))
        yprev=y + int(r*math.sin(start))    
        for t in theta:
            xn=x + int(r*math.cos(t))
            yn=y + int(r*math.sin(t)  )  
            self.line(xprev, yprev, xn, yn,1)
            xprev=xn
            yprev=yn
            
    def draw_image(self, image, x,y, invert=False, key=-1):        
        rowlen=image.width//8 +(1 if image.width%8 else 0)
        for line_idx in range(image.height):
            for col_idx in range(rowlen):
                data=image.image[col_idx+line_idx*rowlen]
                for pixel_idx in range(min(8,image.width-col_idx*8)):
                    val=bool(data<<pixel_idx & 0x80)
                    if invert:
                        val=not val
                    if val!=key:
                        self.pixel(x+col_idx*8+pixel_idx,y+line_idx,val)

    async def cycle_images(self, images, x,y,invert=False, key=-1,delay=1):
        h,w=next((image.height,image.width) for image in images if image is not None)
        while True:
            for image in images:
                if image is not None:
                    self.draw_image(image, x,y,invert, key)
                else:
                    self.fill_rect(x,y,w,h,not invert)
                self.show()
                await asyncio.sleep(delay)

    def battery(self, x,y,width=30, height=10, charge=50):
        box_w=int(width*.9)
        box_w_charge=int(box_w*charge/100)
        self.fill_rect(x, y,box_w_charge, height, 1)
        self.rect(x+box_w_charge, y,box_w-box_w_charge, height, 1)
        self.fill_rect(x+box_w, y+int(height/3),width-box_w, int(height/3), 1)

    #def fill_rect(self, x, y, w, h, c):
    #    for i in range(w):
    #        self.vline(x+i,y,h,c)

    def smiley(self, x,y,r=30, happiness=4):
        self.circle(x,y,r)
        #self.circle(x,y,r//5)#nose
        self.line(x,y-r//5, x-r//5, y+r//5,1)#nose
        self.line(x-r//5, y+r//5,x+r//20,y+r//5,1)
        self.circle(x+r//2, y-r//2 ,r//8)#right eye
        self.circle(x-r//2, y-r//2 ,r//8)#left eye
        if happiness==4:
            self.circle(x, y+r//4, r//2, start=0,end=math.pi)
        elif happiness==3:
            self.circle(x, y-r//2, r, start=math.pi/4,end=3*math.pi/4)
        elif happiness==2:
            self.line(x+r//2, y+r//2, x-r//2, y+r//2,1)
        elif happiness==1:
            self.circle(x, y+3*r//2, r, start=11/8*math.pi,end=13/8*math.pi) 
        elif happiness==0:
            self.circle(x, y+r, r//2,start=10/8*math.pi,end=14/8*math.pi)
        
    def chart(self,values,title=None, xlab=None, ylab=None,  print_last=False, xlim=None, ylim=None):
        xo=[3,self.width-3]
        yo=[3,self.height-3]#offset    
        if title is not None:
            yo[0]+=8        
            self.text(title, halign=1,linebreak=False)
            
        if ylab is not None:
            xo[0]+=8
            self.text(ylab,0,yo[0],xo[0],yo[1])
        if xlab is not None:
            yo[1]-=8
            self.text(xlab,x1=xo[0],y1=yo[1]+3, halign=1, valign=2, linebreak=False)
       
        if xlim is None:     
            xlim=[0,len(values)]
        if ylim is None:
            if values:
                ylim=[0, max(values)]
            else:
                ylim=[0,0]
        if ylim[1]-ylim[0]<5:
            ylim[1]=ylim[0]+5

        self.line(xo[0]-2,yo[0]-2,xo[0]-2,yo[1]+2,1)#y axis
        self.line(xo[0]-2,yo[1]+2, xo[1]+2,yo[1]+2,1)#x axis
        prev=[]
        xs=(xo[1]-xo[0])/(xlim[1]-xlim[0])
        ys=(yo[1]-yo[0])/(ylim[1]-ylim[0])
        for x,y in enumerate(values):
            if x<xlim[0]:
                continue
            point=(xo[0]+round((x-xlim[0])*xs), yo[1]-round(y*ys))
            if prev:
                self.line(prev[0], prev[1], point[0], point[1],1)
            prev=point
            if x > xlim[1]:
                break



def byte2bit(data, num):
    base = int(num // 8)
    shift = 7-int(num % 8)
    return bool((data[base] >> shift) & 0x1)

    

