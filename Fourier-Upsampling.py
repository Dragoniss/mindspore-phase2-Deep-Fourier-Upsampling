#!/usr/bin/env python
# coding=utf-8
'''
Author: zhou man
Date: 2022-3-6
'''
import os
import mindspore
import mindspore.nn as nn
from mindspore.dataset.vision import *
from mindspore.dataset.transforms import *


class freup_Areadinterpolation(nn.Module):
    def __init__(self, channels):
        super(freup_Areadinterpolation, self).__init__()

        self.amp_fuse = nn.SequentialCell(nn.Conv2d(channels,channels,1,1,0),nn.LeakyReLU(0.1,inplace=False),
                                      nn.Conv2d(channels,channels,1,1,0))
        self.pha_fuse = nn.SequentialCell(nn.Conv2d(channels,channels,1,1,0),nn.LeakyReLU(0.1,inplace=False),
                                      nn.Conv2d(channels,channels,1,1,0))

        self.post = nn.Conv2d(channels,channels,1,1,0)

    def forward(self, x):
        N, C, H, W = x.shape
        ###############################
        #fft_x = mindspore.fft.fft2(x)#fast fourier transform is not supported in mindspore
        ###############################
        mag_x = mindspore.ops.abs(fft_x)
        pha_x = mindspore.ops.angle(fft_x)

        Mag = self.amp_fuse(mag_x)
        Pha = self.pha_fuse(pha_x)
        
        amp_fuse = Mag.repeat_interleave(2, dim=2).repeat_interleave(2, dim=3)
        pha_fuse = Pha.repeat_interleave(2, dim=2).repeat_interleave(2, dim=3)

        real = amp_fuse * mindspore.ops.cos(pha_fuse)
        imag = amp_fuse * mindspore.ops.sin(pha_fuse)
        out = mindspore.ops.complex(real, imag)
        
        ###############################
        #output = mindspore.fft.ifft2(out)#inverse fast fourier transform is not supported in mindspore
        ###############################
        
        output = mindspore.ops.abs(output)
        
        crop = mindspore.ops.ZerosLike(x)
        crop[:, :, 0:int(H/2), 0:int(W/2)] = output[:, :, 0:int(H/2), 0:int(W/2)]
        crop[:, :, int(H/2):H, 0:int(W/2)] = output[:, :, int(H*1.5):2*H, 0:int(W/2)]
        crop[:, :, 0:int(H/2), int(W/2):W] = output[:, :, 0:int(H/2), int(W*1.5):2*W]
        crop[:, :, int(H/2):H, int(W/2):W] = output[:, :, int(H*1.5):2*H, int(W*1.5):2*W]
        crop = mindspore.ops.interpolate(crop, (2*H, 2*W))

        return self.post(crop)


class freup_Periodicpadding(nn.Module):
    def __init__(self, channels):
        super(freup_Periodicpadding, self).__init__()

        self.amp_fuse = nn.Sequential(nn.Conv2d(channels,channels,1,1,0),nn.LeakyReLU(0.1,inplace=False),
                                      nn.Conv2d(channels,channels,1,1,0))
        self.pha_fuse = nn.Sequential(nn.Conv2d(channels,channels,1,1,0),nn.LeakyReLU(0.1,inplace=False),
                                      nn.Conv2d(channels,channels,1,1,0))

        self.post = nn.Conv2d(channels,channels,1,1,0)

    def forward(self, x):

        N, C, H, W = x.shape
        ###############################
        #fft_x = torch.fft.fft2(x)    #fast fourier transform is not supported in mindspore
        ###############################
        mag_x = mindspore.ops.abs(fft_x)
        pha_x = mindspore.ops.angle(fft_x)

        Mag = self.amp_fuse(mag_x)
        Pha = self.pha_fuse(pha_x)

        amp_fuse = mindspore.ops.Tile(Mag, (2, 2))
        pha_fuse = mindspore.ops.Tile(Pha, (2, 2))

        real = amp_fuse * mindspore.ops.cos(pha_fuse)
        imag = amp_fuse * mindspore.ops.sin(pha_fuse)
        out = mindspore.ops.complex(real, imag)

        output = torch.fft.ifft2(out)
        output = mindspore.ops.abs(output)

        return self.post(output)


class freup_Cornerdinterpolation(nn.Module):
    def __init__(self, channels):
        super(freup_Cornerdinterpolation, self).__init__()

        self.amp_fuse = nn.SequentialCell(nn.Conv2d(channels, channels, 1, 1, 0), nn.LeakyReLU(0.1, inplace=False),
                                      nn.Conv2d(channels, channels, 1, 1, 0))
        self.pha_fuse = nn.SequentialCell(nn.Conv2d(channels, channels, 1, 1, 0), nn.LeakyReLU(0.1, inplace=False),
                                      nn.Conv2d(channels, channels, 1, 1, 0))

        # self.post = nn.Conv2d(channels,channels,1,1,0)

    def forward(self, x):
        N, C, H, W = x.shape
        ###############################
        #fft_x = torch.fft.fft2(x)    #fast fourier transform is not supported in mindspore
        ###############################
        fft_x = torch.fft.fft2(x)  # n c h w
        mag_x = mindspore.ops.abs(fft_x)
        pha_x = mindspore.ops.angle(fft_x)

        Mag = self.amp_fuse(mag_x)
        Pha = self.pha_fuse(pha_x)

        r = x.size(2)  # h
        c = x.size(3)  # w

        I_Mup = mindspore.ops.Zeros((N, C, 2 * H, 2 * W)).cuda()
        I_Pup = mindspore.ops.Zeros((N, C, 2 * H, 2 * W)).cuda()

        if r % 2 == 1:  # odd
            ir1, ir2 = r // 2 + 1, r // 2 + 1
        else:  # even
            ir1, ir2 = r // 2 + 1, r // 2
        if c % 2 == 1:  # odd
            ic1, ic2 = c // 2 + 1, c // 2 + 1
        else:  # even
            ic1, ic2 = c // 2 + 1, c // 2

        I_Mup[:, :, :ir1, :ic1] = Mag[:, :, :ir1, :ic1]
        I_Mup[:, :, :ir1, ic2 + c:] = Mag[:, :, :ir1, ic2:]
        I_Mup[:, :, ir2 + r:, :ic1] = Mag[:, :, ir2:, :ic1]
        I_Mup[:, :, ir2 + r:, ic2 + c:] = Mag[:, :, ir2:, ic2:]

        if r % 2 == 0:  # even
            I_Mup[:, :, ir2, :] = I_Mup[:, :, ir2, :] * 0.5
            I_Mup[:, :, ir2 + r, :] = I_Mup[:, :, ir2 + r, :] * 0.5
        if c % 2 == 0:  # even
            I_Mup[:, :, :, ic2] = I_Mup[:, :, :, ic2] * 0.5
            I_Mup[:, :, :, ic2 + c] = I_Mup[:, :, :, ic2 + c] * 0.5

        I_Pup[:, :, :ir1, :ic1] = Pha[:, :, :ir1, :ic1]
        I_Pup[:, :, :ir1, ic2 + c:] = Pha[:, :, :ir1, ic2:]
        I_Pup[:, :, ir2 + r:, :ic1] = Pha[:, :, ir2:, :ic1]
        I_Pup[:, :, ir2 + r:, ic2 + c:] = Pha[:, :, ir2:, ic2:]

        if r % 2 == 0:  # even
            I_Pup[:, :, ir2, :] = I_Pup[:, :, ir2, :] * 0.5
            I_Pup[:, :, ir2 + r, :] = I_Pup[:, :, ir2 + r, :] * 0.5
        if c % 2 == 0:  # even
            I_Pup[:, :, :, ic2] = I_Pup[:, :, :, ic2] * 0.5
            I_Pup[:, :, :, ic2 + c] = I_Pup[:, :, :, ic2 + c] * 0.5

        real = I_Mup * mindspore.ops.cos(I_Pup)
        imag = I_Mup * mindspore.ops.sin(I_Pup)
        
        out = mindspore.ops.complex(real, imag)
        ###############################
        #output = torch.fft.ifft2(out)# fast fourier transform is not supported in mindspore
        ###############################

        output = mindspore.ops.abs(output)

        return output




class fresadd(nn.Module):
    def __init__(self, in_channels=32, channels=32):
        super(fresadd, self).__init__()

        self.opspa = ConvBlock(in_channels, channels, 5, 1, 2, activation=None, norm=None, bias = False)
        self.opfre = freup_Periodicpadding(channels)

        self.fuse1 = nn.Conv2d(channels, channels,1,1,0)
        self.fuse2 = nn.Conv2d(channels, channels,1,1,0)
        self.fuse = nn.Conv2d(channels, channels,1,1,0)

    def forward(self,x):

        x1 = x
        x2 = mindspore.ops.interpolate(x1,scale_factor=0.5,mode='bilinear')
        x3 = mindspore.ops.interpolate(x1, scale_factor=0.25, mode='bilinear')

        x1 = self.opspa(x1)
        x2 = self.opspa(x2)
        x3 = self.opspa(x3)

        x3f = self.opfre(x3)
        x3s = mindspore.ops.interpolate(x3, size=(x2.size()[2], x2.size()[3]), mode='bilinear')
        x32 = self.fuse1(x3f + x3s)

        x2m = x2 + x32

        x2f = self.opfre(x2m)
        x2s = mindspore.ops.interpolate(x2m,size=(x1.size()[2],x1.size()[3]),mode='bilinear')
        x21 = self.fuse2(x2f + x2s)

        x1m = x1 + x21
        x = self.fuse(x1m)

        return x



class frescat(nn.Module):
    def __init__(self, in_channels=32, channels=32):
        super(frescat, self).__init__()


        self.opspa = ConvBlock(in_channels, channels, 5, 1, 2, activation=None, norm=None, bias = False)
        self.opfre = freup_Periodicpadding(channels)

        self.fuse1 = nn.Conv2d(2*channels, channels,1,1,0)
        self.fuse2 = nn.Conv2d(2*channels, channels,1,1,0)
        self.fuse = nn.Conv2d(2*channels, channels,1,1,0)

    def forward(self,x):

        x1 = x
        x2 = mindspore.ops.interpolate(x1,scale_factor=0.5,mode='bilinear')
        x3 = mindspore.ops.interpolate(x1, scale_factor=0.25, mode='bilinear')

        x1 = self.opspa(x1)
        x2 = self.opspa(x2)
        x3 = self.opspa(x3)

        x3f = self.opfre(x3)
        x3s = mindspore.ops.interpolate(x3, size=(x2.size()[2], x2.size()[3]), mode='bilinear')
        x32 = self.fuse1(mindspore.ops.Concat([x3f,x3s],dim=1))

        x2m = x2 + x32

        x2f = self.opfre(x2m)
        x2s = mindspore.ops.interpolate(x2m,size=(x1.size()[2],x1.size()[3]),mode='bilinear')
        x21 = self.fuse2(mindspore.ops.Concat([x2f,x2s],dim=1))

        # x1m = x1 + x21
        x = self.fuse(mindspore.ops.Concat([x1,x21],dim=1))

        return x