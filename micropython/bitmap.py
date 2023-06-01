import struct

class BitMap:
    def __init__(self,image, width, height):
        self.image=image
        self.width=width
        self.height=height
    
    @classmethod
    def from_file(cls, file_name):
        image, width, height=read_bmp(file_name)
        return BitMap(image, width, height)

    def pixelart(self, invert=False):
        rowlen=self.width//8 +(1 if self.width%8 else 0)
        for line_idx in range(self.height):
            line=''
            for col_idx in range(rowlen):
                data=self.image[col_idx+line_idx*rowlen]
                for pixel_idx in range(min(8,self.width-col_idx*8)):
                    val=bool(data<<pixel_idx & 0x80)
                    if invert:
                        val=not val
                    line += ('  ' if val else 'xx')
            print(line)


    def crop(self,x,y,w,h):        
        start=x//8
        end=(x+w)//8+(1 if (x+w)%8 else 0)
        rowlen=w//8+(1 if w%8 else 0)
        img_rolen=self.width//8+(1 if self.width%8 else 0)
        #data=[]        
        data=bytearray(rowlen*h)
        for i in range(h):
            # mask first x % 8 bits, 
            line=int.from_bytes(self.image[img_rolen*(y+i)+start:img_rolen*(y+i)+end]  , 'big') 
            line=line << (x%8)
            # line &= ~(2**(w%8)-1)
            if (x%8 +w%8)>8:
                line=line >> 8
            #data.append(line.to_bytes(w//8+(1 if w%8 else 0), 'big')) 
            data[i*rowlen:(i+1)*rowlen]=line.to_bytes(w//8+(1 if w%8 else 0), 'big')
        return BitMap(data,w,h)


def byte2bit(data, num):
    base = int(num // 8)
    shift = 7-int(num % 8)
    return bool((data[base] >> shift) & 0x1)


def read_bmp(fn):
    with open(fn, "rb") as image_file:
        file_type, file_size, _,_,offset, bmhsz, w,h,n_pl,bpp, compression, img_sz=struct.unpack('<2si2h4i2h2i', image_file.read(38))
        if file_type!= b'BM':
            raise ValueError('this is not a bitmap file: {}'.format(file_type))
        if bpp!=1:
            raise ValueError('should be b/w bitmap, but found {} bit colors'.format(bpp))
        image_file.seek(offset)
        image= bytearray(img_sz)
        rowlen=w//8+(1 if w%8 else 0)
        image= bytearray(rowlen*h)
        rowlen_extra=(32-w%32)//8 if w%32 else 0
        for i in range(h):
            line=image_file.read(rowlen)
            image[(h-i-1)*rowlen:(h-i)*rowlen]=line
            _=image_file.read(rowlen_extra)
    return image, w,h
