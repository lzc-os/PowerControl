# --*--utf8--*--
import os
import sys
import threading
import tkinter.messagebox
from tkinter.tix import *
from tkinter.ttk import *
from ctypes import *
from tkinter import *
from tkinter import ttk
import winsound

DevType = c_uint

'''
    Device Type
'''
USBCAN1 = DevType(3)
USBCAN2 = DevType(4)
USBCANFD = DevType(6)
'''
    Device Index
'''
DevIndex = c_uint(0)  # 设备索引
'''
    Channel
'''
Channel1 = c_uint(0)  # CAN1
Channel2 = c_uint(1)  # CAN2
'''
    ECAN Status
'''
STATUS_ERR = 0
STATUS_OK = 1

'''
    Device Information
'''


class BoardInfo(Structure):
    _fields_ = [("hw_Version", c_ushort),  # 硬件版本号，用16进制表示
                ("fw_Version", c_ushort),  # 固件版本号，用16进制表示
                ("dr_Version", c_ushort),  # 驱动程序版本号，用16进制表示
                ("in_Version", c_ushort),  # 接口库版本号，用16进制表示
                ("irq_Num", c_ushort),  # 板卡所使用的中断号
                ("can_Num", c_byte),  # 表示有几路CAN通道
                ("str_Serial_Num", c_byte * 20),  # 此板卡的序列号，用ASC码表示
                ("str_hw_Type", c_byte * 40),  # 硬件类型，用ASC码表示
                ("Reserved", c_byte * 4)]  # 系统保留


class CAN_OBJ(Structure):
    _fields_ = [("ID", c_uint),  # 报文帧ID
                ("TimeStamp", c_uint),  # 接收到信息帧时的时间标识，从CAN控制器初始化开始计时，单位微秒
                ("TimeFlag", c_byte),  # 是否使用时间标识，为1时TimeStamp有效，TimeFlag和TimeStamp只在此帧为接收帧时有意义。
                ("SendType", c_byte),
                # 发送帧类型。=0时为正常发送，=1时为单次发送（不自动重发），=2时为自发自收（用于测试CAN卡是否损坏），=3时为单次自发自收（只发送一次，用于自测试），只在此帧为发送帧时有意义
                ("RemoteFlag", c_byte),  # 是否是远程帧。=0时为数据帧，=1时为远程帧
                ("ExternFlag", c_byte),  # 是否是扩展帧。=0时为标准帧（11位帧ID），=1时为扩展帧（29位帧ID）
                ("DataLen", c_byte),  # 数据长度DLC(<=8)，即Data的长度
                ("data", c_ubyte * 8),  # CAN报文的数据。空间受DataLen的约束
                ("Reserved", c_byte * 3)]  # 系统保留。


class INIT_CONFIG(Structure):
    _fields_ = [("acccode", c_uint32),  # 验收码。SJA1000的帧过滤验收码
                ("accmask", c_uint32),  # 屏蔽码。SJA1000的帧过滤屏蔽码。屏蔽码推荐设置为0xFFFF FFFF，即全部接收
                ("reserved", c_uint32),  # 保留
                ("filter", c_byte),  # 滤波使能。0=不使能，1=使能。使能时，请参照SJA1000验收滤波器设置验收码和屏蔽码
                ("timing0", c_byte),  # 波特率定时器0,详见动态库使用说明书7页
                ("timing1", c_byte),  # 波特率定时器1,详见动态库使用说明书7页
                ("mode", c_byte)]  # 模式。=0为正常模式，=1为只听模式，=2为自发自收模式。


cwdx = os.getcwd()


class ECAN(object):
    def __init__(self):
        self.dll = cdll.LoadLibrary(cwdx + '/ECanVci64.dll')
        if self.dll is None:
            print("DLL Couldn't be loaded")

    def OpenDevice(self, DeviceType, DeviceIndex):
        try:
            return self.dll.OpenDevice(DeviceType, DeviceIndex, 0)
        except:
            print("Exception on OpenDevice!")
            raise

    def CloseDevice(self, DeviceType, DeviceIndex):
        try:
            return self.dll.CloseDevice(DeviceType, DeviceIndex, 0)
        except:
            print("Exception on CloseDevice!")
            raise

    def InitCan(self, DeviceType, DeviceIndex, CanInd, Initconfig):
        try:
            return self.dll.InitCAN(DeviceType, DeviceIndex, CanInd, byref(Initconfig))
        except:
            print("Exception on InitCan!")
            raise

    def StartCan(self, DeviceType, DeviceIndex, CanInd):
        try:
            return self.dll.StartCAN(DeviceType, DeviceIndex, CanInd)
        except:
            print("Exception on StartCan!")
            raise

    def ReadBoardInfo(self, DeviceType, DeviceIndex):
        try:
            mboardinfo = BoardInfo()
            ret = self.dll.ReadBoardInfo(DeviceType, DeviceIndex, byref(mboardinfo))
            return mboardinfo, ret
        except:
            print("Exception on ReadBoardInfo!")
            raise

    def Receivce(self, DeviceType, DeviceIndex, CanInd, length):
        try:
            recmess = (CAN_OBJ * length)()
            ret = self.dll.Receive(DeviceType, DeviceIndex, CanInd, byref(recmess), length, 0)
            return length, recmess, ret
        except:
            print("Exception on Receive!")
            raise

    def Tramsmit(self, DeviceType, DeviceIndex, CanInd, mcanobj):
        try:
            # mCAN_OBJ=CAN_OBJ*2
            # self.dll.Transmit.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, POINTER(CAN_OBJ),
            # ctypes.c_uint16]
            return self.dll.Transmit(DeviceType, DeviceIndex, CanInd, byref(mcanobj), c_uint16(1))
        except:
            print("Exception on Tramsmit!")
            raise


# 加载动态库
ecan = ECAN()

if hasattr(sys, 'frozen'):
    os.environ['PATH'] = sys._MEIPASS + ":" + os.environ['PATH']
root = Tk()  # 初始化Tk()
root.title("PowerControl")
# root.geometry("800x1000")
root.resizable(width=False, height=False)
root.tk.eval('package require Tix')
musbcanopen = False
rec_CAN1 = 1
rec_CAN2 = 1
'''
读取数据
'''


def ReadCAN():
    global musbcanopen, rec_CAN1, rec_CAN2, flag_limit
    if musbcanopen:
        scount = 0
        while (scount < 50):
            scount = scount + 1
            len, rec, ret = ecan.Receivce(USBCAN2, DevIndex, Channel1, 1)
            if (len > 0 and ret == 1):
                mstr = "Rec: " + str(rec_CAN1)
                rec_CAN1 = rec_CAN1 + 1
                if rec[0].TimeFlag == 0:
                    mstr = mstr + " Time: "
                else:
                    mstr = mstr + " Time:" + hex(rec[0].TimeStamp).zfill(8)
                if rec[0].ExternFlag == 0:
                    mstr = mstr + " ID:" + hex(rec[0].ID).zfill(3) + " Format:Stand "
                else:
                    mstr = mstr + " ID:" + hex(rec[0].ID).zfill(8) + " Format:Exten "
                if rec[0].RemoteFlag == 0:
                    mstr = mstr + " Type:Data " + " Data: "
                    for i in range(0, rec[0].DataLen):
                        mstr = mstr + hex(rec[0].data[i]).zfill(2) + " "
                else:
                    mstr = mstr + " Type:Romte " + " Data: Remote Request"

                if listreadcan1.size() > 1000:
                    listreadcan1.delete(0, END)
                listreadcan1.insert("end", mstr)
                listreadcan1.see(listreadcan1.size())

                if rec[0].ID == int('0289F000', 16) + int(modulenumber.get()):
                    read_v = rec[0].data[0] * 16777216 + rec[0].data[1] * 65536 + rec[0].data[2] * 256 + rec[0].data[3]
                    read_i = rec[0].data[4] * 16777216 + rec[0].data[5] * 65536 + rec[0].data[6] * 256 + rec[0].data[7]
                    lb_m_v.configure(text='模块电压(V)：%.3f' % (read_v / 1000))
                    lb_m_i.configure(text='模块电流(A)：%.3f' % (read_i / 1000))
                    if flag_limit:
                        if (read_v / 1000 > float(set_vlimit.get())) or (read_i / 1000 > float(set_ilimit.get())):
                            power_off()
                            winsound.Beep(440, 1000)
                            power_conn()
                            tkinter.messagebox.showinfo("WARN", "电压或电流超出自定义限制，已关闭电源输出")


                if rec[0].ID == int('0286F000', 16) + int(modulenumber.get()):
                    read_ac = rec[0].data[0] * 256 + rec[0].data[1]
                    lb_m_acinput.configure(text="交流输入(V)：%.1f" % (read_ac / 10))

                if rec[0].ID == int('0284F000', 16) + int(modulenumber.get()):
                    data_group = rec[0].data[2]
                    data_temp = rec[0].data[4]
                    data_state0 = bin(rec[0].data[7])[2:].zfill(8)
                    data_state1 = bin(rec[0].data[6])[2:].zfill(8)
                    data_state2 = bin(rec[0].data[5])[2:].zfill(8)
                    lb_m_dispgroup.configure(text="模块组号：%d" % data_group)
                    lb_m_temp.configure(text="模块温度(°C)：%d" % data_temp)
                    for i in range(0, 8):
                        if data_state0[i] == '1':
                            lb_sel0[i].configure(bg="red")
                        else:
                            lb_sel0[i].configure(bg="green")
                        if data_state1[i] == '1':
                            lb_sel1[i].configure(bg="red")
                        else:
                            lb_sel1[i].configure(bg="green")
                        if data_state2[i] == '1':
                            lb_sel2[i].configure(bg="red")
                        else:
                            lb_sel2[i].configure(bg="green")

            len2, rec2, ret2 = ecan.Receivce(USBCAN2, DevIndex, Channel2, 1)
            if (len2 > 0 and ret2 == 1):
                mstr = "Rec: " + str(rec_CAN2)
                rec_CAN2 = rec_CAN2 + 1
                if rec2[0].TimeFlag == 0:
                    mstr = mstr + " Time: "
                else:
                    mstr = mstr + " Time:" + hex(rec2[0].TimeStamp).zfill(8)
                if rec2[0].ExternFlag == 0:
                    mstr = mstr + " ID:" + hex(rec2[0].ID).zfill(3) + " Format:Stand "
                else:
                    mstr = mstr + " ID:" + hex(rec2[0].ID).zfill(8) + " Format:Exten "
                if rec2[0].RemoteFlag == 0:
                    mstr = mstr + " Type:Data " + " Data: "
                    for i in range(0, rec2[0].DataLen):
                        mstr = mstr + hex(rec2[0].data[i]).zfill(2) + " "
                else:
                    mstr = mstr + " Type:Romte " + " Data: Remote Request"

                if listreadcan2.size() > 1000:
                    listreadcan2.delete(0, END)
                listreadcan2.insert("end", mstr)
                listreadcan2.see(listreadcan2.size())

        t = threading.Timer(0.03, ReadCAN)
        t.start()


t = threading.Timer(0.03, ReadCAN)


# python调用动态库默认参数为整型


def caninit():
    global musbcanopen, t, rec_CAN1, rec_CAN2
    if (musbcanopen == False):
        initconfig = INIT_CONFIG()
        initconfig.acccode = 0  # 设置验收码
        initconfig.accmask = 0xFFFFFFFF  # 设置屏蔽码
        initconfig.filter = 0  # 设置滤波使能
        mbaudcan1 = baudvaluecan1.get()
        mbaudcan2 = baudvaluecan2.get()
        # 打开设备
        if (ecan.OpenDevice(USBCAN2, DevIndex) != STATUS_OK):
            tkinter.messagebox.showinfo("ERROR", "OpenDevice Failed!")
            return
        initconfig.timing0, initconfig.timing1 = getTiming(mbaudcan1)
        initconfig.mode = 0
        # 初始化CAN1
        if (ecan.InitCan(USBCAN2, DevIndex, Channel1, initconfig) != STATUS_OK):
            tkinter.messagebox.showinfo("ERROR", "InitCan CAN1 Failed!")
            ecan.CloseDevice(USBCAN2, DevIndex)
            return
        # 初始化CAN2
        initconfig.timing0, initconfig.timing1 = getTiming(mbaudcan2)
        if (ecan.InitCan(USBCAN2, DevIndex, Channel2, initconfig) != STATUS_OK):
            tkinter.messagebox.showinfo("ERROR", "InitCan CAN2 Failed!")
            ecan.CloseDevice(USBCAN2, DevIndex)
            return
        if (ecan.StartCan(USBCAN2, DevIndex, Channel1) != STATUS_OK):
            tkinter.messagebox.showinfo("ERROR", "StartCan CAN1 Failed!")
            ecan.CloseDevice(USBCAN2, DevIndex)
            return
        if (ecan.StartCan(USBCAN2, DevIndex, Channel2) != STATUS_OK):
            tkinter.messagebox.showinfo("ERROR", "StartCan CAN2 Failed!")
            ecan.CloseDevice(USBCAN2, DevIndex)
            return
        musbcanopen = True
        rec_CAN1 = 1
        rec_CAN2 = 1
        btopen.configure(text="关闭CAN分析仪")
        btreadinfo.configure(state='normal')
        bt_send_CAN1.configure(state='normal')
        bt_send_CAN2.configure(state='normal')
        t = threading.Timer(0.03, ReadCAN)
        t.start()
    else:
        musbcanopen = False
        ecan.CloseDevice(USBCAN2, DevIndex)
        btopen.configure(text="打开CAN分析仪")
        lbsn.configure(text="SN:")
        btreadinfo.configure(state='disabled')
        bt_send_CAN1.configure(state='disabled')
        bt_send_CAN2.configure(state='disabled')


'''
读取SN号码
'''


def readmess():
    global musbcanopen
    if (musbcanopen == False):
        tkinter.messagebox.showinfo("ERROR", "请先打开CAN分析仪")
    else:
        mboardinfo, ret = ecan.ReadBoardInfo(USBCAN2, DevIndex)  # 读取设备信息需要在打开设备后执行
        if ret == STATUS_OK:
            mstr = ""
            for i in range(0, 10):
                mstr = mstr + chr(mboardinfo.str_Serial_Num[i])  # 结构体中str_Serial_Num内部存放存放SN号的ASC码
            lbsn.configure(text="SN:" + mstr)

        else:
            lbsn.configure(text="Read info Fault")


def getTiming(mbaud):
    if mbaud == "1M":
        return 0, 0x14
    if mbaud == "800k":
        return 0, 0x16
    if mbaud == "666k":
        return 0x80, 0xb6
    if mbaud == "500k":
        return 0, 0x1c
    if mbaud == "400k":
        return 0x80, 0xfa
    if mbaud == "250k":
        return 0x01, 0x1c
    if mbaud == "200k":
        return 0x81, 0xfa
    if mbaud == "125k":
        return 0x03, 0x1c
    if mbaud == "100k":
        return 0x04, 0x1c
    if mbaud == "80k":
        return 0x83, 0xff
    if mbaud == "50k":
        return 0x09, 0x1c


def clearcan1():
    listreadcan1.delete(0, END)


def clearcan2():
    listreadcan2.delete(0, END)


def sendcan1():
    global musbcanopen
    if (musbcanopen == False):
        tkinter.messagebox.showinfo("ERROR", "请先打开CAN分析仪")
    else:
        canobj = CAN_OBJ()
        canobj.ID = int(e_ID_CAN1.get(), 16)
        canobj.DataLen = int(ct_Length_CAN1['value'])
        canobj.data[0] = int(e_Data0_CAN1.get(), 16)
        canobj.data[1] = int(e_Data1_CAN1.get(), 16)
        canobj.data[2] = int(e_Data2_CAN1.get(), 16)
        canobj.data[3] = int(e_Data3_CAN1.get(), 16)
        canobj.data[4] = int(e_Data4_CAN1.get(), 16)
        canobj.data[5] = int(e_Data5_CAN1.get(), 16)
        canobj.data[6] = int(e_Data6_CAN1.get(), 16)
        canobj.data[7] = int(e_Data7_CAN1.get(), 16)
        canobj.RemoteFlag = rtr_CAN1.get()
        canobj.ExternFlag = ext_CAN1.get()
        ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)


def sendcan2():
    global musbcanopen
    if (musbcanopen == False):
        tkinter.messagebox.showinfo("ERROR", "请先打开CAN分析仪")
    else:
        canobj = CAN_OBJ()
        canobj.ID = int(e_ID_CAN2.get(), 16)
        canobj.DataLen = int(ct_Length_CAN2['value'])
        canobj.data[0] = int(e_Data0_CAN2.get(), 16)
        canobj.data[1] = int(e_Data1_CAN2.get(), 16)
        canobj.data[2] = int(e_Data2_CAN2.get(), 16)
        canobj.data[3] = int(e_Data3_CAN2.get(), 16)
        canobj.data[4] = int(e_Data4_CAN2.get(), 16)
        canobj.data[5] = int(e_Data5_CAN2.get(), 16)
        canobj.data[6] = int(e_Data6_CAN2.get(), 16)
        canobj.data[7] = int(e_Data7_CAN2.get(), 16)
        canobj.RemoteFlag = rtr_CAN2.get()
        canobj.ExternFlag = ext_CAN2.get()
        ecan.Tramsmit(USBCAN2, DevIndex, Channel2, canobj)


flag_led = 0


def led():
    global flag_led
    canobj = CAN_OBJ()
    canobj.ID = int("029400F0", 16) + int(modulenumber.get()) * 256
    canobj.DataLen = 8
    if flag_led:
        canobj.data[0] = 0
        flag_led = 0
    else:
        canobj.data[0] = 1
        flag_led = 1
    canobj.data[1] = 0
    canobj.data[2] = 0
    canobj.data[3] = 0
    canobj.data[4] = 0
    canobj.data[5] = 0
    canobj.data[6] = 0
    canobj.data[7] = 0
    canobj.RemoteFlag = 0
    canobj.ExternFlag = 1
    ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)


def set_add():
    canobj = CAN_OBJ()
    canobj.ID = int("029F3FF0", 16)
    canobj.DataLen = 8
    if addstr.get() == "自动设址":
        canobj.data[0] = 0
    else:
        canobj.data[0] = 1
    canobj.data[1] = 0
    canobj.data[2] = 0
    canobj.data[3] = 0
    canobj.data[4] = 0
    canobj.data[5] = 0
    canobj.data[6] = 0
    canobj.data[7] = 0
    canobj.RemoteFlag = 0
    canobj.ExternFlag = 1
    ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)


flag_conn = 0


def power_conn():
    global flag_conn, timer1
    canobj = CAN_OBJ()
    canobj.ID = int("028A00F0", 16) + int(modulenumber.get()) * 256
    canobj.DataLen = 8
    canobj.data[0] = 0
    canobj.data[1] = 0
    canobj.data[2] = 0
    canobj.data[3] = 0
    canobj.data[4] = 0
    canobj.data[5] = 0
    canobj.data[6] = 0
    canobj.data[7] = 0
    canobj.RemoteFlag = 0
    canobj.ExternFlag = 1

    if flag_conn:
        flag_conn = 0
        bt_conn.configure(text="建立电源通信", fg="red")
        timer1.cancel()
    else:
        flag_conn = 1
        bt_conn.configure(text="断开电源通信", fg="green")
        ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)
        polling()


flag_timer1 = 0


def polling():
    global flag_timer1, timer1
    flag_timer1 += 1
    canobj = CAN_OBJ()
    canobj.ID = int("028600F0", 16) + int(modulenumber.get()) * 256
    canobj.DataLen = 8
    canobj.data[0] = 0
    canobj.data[1] = 0
    canobj.data[2] = 0
    canobj.data[3] = 0
    canobj.data[4] = 0
    canobj.data[5] = 0
    canobj.data[6] = 0
    canobj.data[7] = 0
    canobj.RemoteFlag = 0
    canobj.ExternFlag = 1
    if flag_timer1 == 2:
        canobj.ID = int("028900F0", 16) + int(modulenumber.get()) * 256
    if flag_timer1 == 3:
        flag_timer1 = 0
        canobj.ID = int("028400F0", 16) + int(modulenumber.get()) * 256
    ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)

    timer1 = threading.Timer(0.2, polling)
    timer1.start()


timer1 = threading.Timer(0.2, polling)


def wall_in():
    canobj = CAN_OBJ()
    canobj.ID = int("029300F0", 16) + int(modulenumber.get()) * 256
    canobj.DataLen = 8
    canobj.data[0] = 0
    canobj.data[1] = 0
    canobj.data[2] = 0
    canobj.data[3] = 0
    canobj.data[4] = 0
    canobj.data[5] = 0
    canobj.data[6] = 0
    canobj.data[7] = 0
    canobj.RemoteFlag = 0
    canobj.ExternFlag = 1
    ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)


def power_on():
    canobj = CAN_OBJ()
    canobj.ID = int("029A00F0", 16) + int(modulenumber.get()) * 256
    canobj.DataLen = 8
    canobj.data[0] = 0
    canobj.data[1] = 0
    canobj.data[2] = 0
    canobj.data[3] = 0
    canobj.data[4] = 0
    canobj.data[5] = 0
    canobj.data[6] = 0
    canobj.data[7] = 0
    canobj.RemoteFlag = 0
    canobj.ExternFlag = 1
    ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)


def power_off():
    canobj = CAN_OBJ()
    canobj.ID = int("029A00F0", 16) + int(modulenumber.get()) * 256
    canobj.DataLen = 8
    canobj.data[0] = 1
    canobj.data[1] = 0
    canobj.data[2] = 0
    canobj.data[3] = 0
    canobj.data[4] = 0
    canobj.data[5] = 0
    canobj.data[6] = 0
    canobj.data[7] = 0
    canobj.RemoteFlag = 0
    canobj.ExternFlag = 1
    ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)


flag_sleep = 0


def power_sleep():
    global flag_sleep
    canobj = CAN_OBJ()
    canobj.ID = int("029900F0", 16) + int(modulenumber.get()) * 256
    canobj.DataLen = 8
    if flag_sleep:
        canobj.data[0] = 0
    else:
        canobj.data[0] = 1
    canobj.data[1] = 0
    canobj.data[2] = 0
    canobj.data[3] = 0
    canobj.data[4] = 0
    canobj.data[5] = 0
    canobj.data[6] = 0
    canobj.data[7] = 0
    canobj.RemoteFlag = 0
    canobj.ExternFlag = 1
    ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)


def set_v_i():
    data_v = int(set_v.get()) * 1000  # mV
    data_i = int(set_i.get()) * 1000  # mA
    canobj = CAN_OBJ()
    canobj.ID = int("029C00F0", 16) + int(modulenumber.get()) * 256
    canobj.DataLen = 8
    canobj.data[0] = data_v // 16777216
    canobj.data[1] = (data_v % 16777216) // 65536
    canobj.data[2] = (data_v % 655366) // 256
    canobj.data[3] = data_v % 256
    canobj.data[4] = data_i // 16777216
    canobj.data[5] = (data_i % 16777216) // 65536
    canobj.data[6] = (data_i % 65536) // 256
    canobj.data[7] = data_i % 256
    canobj.RemoteFlag = 0
    canobj.ExternFlag = 1
    ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)


def set_group():
    canobj = CAN_OBJ()
    canobj.ID = int("029600F0", 16) + int(modulenumber.get()) * 256
    canobj.DataLen = 8
    canobj.data[0] = int(e_group.get())
    canobj.data[1] = 0
    canobj.data[2] = 0
    canobj.data[3] = 0
    canobj.data[4] = 0
    canobj.data[5] = 0
    canobj.data[6] = 0
    canobj.data[7] = 0
    canobj.RemoteFlag = 0
    canobj.ExternFlag = 1
    ecan.Tramsmit(USBCAN2, DevIndex, Channel1, canobj)


flag_limit = 0


def soft_v_i():
    global flag_limit
    if flag_limit:
        flag_limit = 0
        lb_m_limit_state.configure(bg="gray")
    else:
        flag_limit = 1
        lb_m_limit_state.configure(bg="green")


lb1 = Label(root, text="CAN1波特率:", bd=3, font=("Arial", 12))
lb1.grid(row=1, column=0, padx=1, pady=1, sticky='w')
lb2 = Label(root, text="CAN2波特率:", bd=3, font=("Arial", 12))
lb2.grid(row=2, column=0, padx=1, pady=1, sticky='w')
lbsn = Label(root, text="SN:", bd=3, font=("Arial", 15), width=15)
lbsn.grid(row=1, column=3, padx=0, pady=5, sticky='w', rowspan=2)
bt_conn = Button(root, text="建立电源通信", bd=3, font=("Arial", 15), command=power_conn, fg="red")
bt_conn.grid(row=1, column=4, pady=5, rowspan=2)

tabcontrol = ttk.Notebook(root, height=600, width=1066)
tab1 = ttk.Frame(tabcontrol)
tab2 = ttk.Frame(tabcontrol)
tab3 = ttk.Frame(tabcontrol)
tabcontrol.grid(row=3, columnspan=5, sticky='nw')
tabcontrol.add(tab1, text="CAN1")
tabcontrol.add(tab2, text="CAN2")
tabcontrol.add(tab3, text="PowerControl")
baudvaluecan1 = StringVar()
baudvaluecan1.set("125k")
baudvaluecan2 = StringVar()
baudvaluecan2.set("125k")
baudvalues = ["1M", "800k", "666k", "500k", "400k", "250k", "200k", "125k", "100k", "80k", "50k"]
can1com = tkinter.ttk.Combobox(master=root, state="readonly", font=("Arial", 12), textvariable=baudvaluecan1,
                               values=baudvalues, width=10)
can1com.grid(row=1, column=1, padx=1, pady=1, sticky='w')
can2com = tkinter.ttk.Combobox(master=root, state="readonly", font=("Arial", 12), textvariable=baudvaluecan2,
                               values=baudvalues, width=10)
can2com.grid(row=2, column=1, padx=1, pady=1, sticky='w')
btopen = Button(root, text="打开CAN分析仪", command=caninit)
btopen.grid(row=1, column=2, padx=1, pady=1, sticky='w')
btreadinfo = Button(root, text="识别CAN分析仪信息", command=readmess, state='disabled')
btreadinfo.grid(row=2, column=2, padx=1, pady=1, sticky='w')

# tab1 CAN1
lb_ID_CAN1 = Label(tab1, text="ID(Hex)", bd=3, font=("Arial", 12))
lb_ID_CAN1.grid(row=0, column=0, sticky='w')
e_ID_CAN1 = Entry(tab1, bd=3, font=("Arial", 12))
e_ID_CAN1.grid(row=1, column=0, sticky='w')
e_ID_CAN1.insert(0, "00000000")
ext_CAN1 = IntVar()
cb_Ext_CAN1 = Checkbutton(tab1, text="Extended", variable=ext_CAN1, bd=3, font=("Arial", 12), )
ext_CAN1.set(1)
cb_Ext_CAN1.grid(row=0, column=1, sticky='w')
rtr_CAN1 = IntVar()
cb_Rtr_CAN1 = Checkbutton(tab1, text="RTR", variable=rtr_CAN1, bd=3, font=("Arial", 12))
cb_Rtr_CAN1.grid(row=1, column=1, sticky='w')
ct_Length_CAN1 = Control(tab1, label='Length(0-8):', integer=True, max=8, min=0, value=8, step=1)
ct_Length_CAN1.grid(row=0, column=7, columnspan=4, sticky='w')
s1 = Scrollbar(tab1, orient=VERTICAL)
s1.grid(row=2, column=11, sticky='ns')
listreadcan1 = Listbox(tab1, font=("Arial", 12), height=28, width=107, yscrollcommand=s1.set)
listreadcan1.grid(row=2, column=0, columnspan=11, sticky='nw')
s1.config(command=listreadcan1.yview)

lb_Data_CAN1 = Label(tab1, text="Data(Hex)", bd=3, font=("Arial", 12))
lb_Data_CAN1.grid(row=0, column=3, columnspan=4, sticky='w')
Data0_CAN1 = StringVar()
e_Data0_CAN1 = Entry(tab1, textvariable=Data0_CAN1, width=3, bd=3, font=("Arial", 12))
e_Data0_CAN1.grid(row=1, column=3, padx=2, pady=1, sticky='w')
Data0_CAN1.set('00')
Data1_CAN1 = StringVar()
e_Data1_CAN1 = Entry(tab1, textvariable=Data1_CAN1, width=3, bd=3, font=("Arial", 12))
e_Data1_CAN1.grid(row=1, column=4, padx=2, pady=1, sticky='w')
Data1_CAN1.set('00')
Data2_CAN1 = StringVar()
e_Data2_CAN1 = Entry(tab1, textvariable=Data2_CAN1, width=3, bd=3, font=("Arial", 12))
e_Data2_CAN1.grid(row=1, column=5, padx=2, pady=1, sticky='w')
Data2_CAN1.set('00')
Data3_CAN1 = StringVar()
e_Data3_CAN1 = Entry(tab1, textvariable=Data3_CAN1, width=3, bd=3, font=("Arial", 12))
e_Data3_CAN1.grid(row=1, column=6, padx=2, pady=1, sticky='w')
Data3_CAN1.set('00')
Data4_CAN1 = StringVar()
e_Data4_CAN1 = Entry(tab1, textvariable=Data4_CAN1, width=3, bd=3, font=("Arial", 12))
e_Data4_CAN1.grid(row=1, column=7, padx=2, pady=1, sticky='w')
Data4_CAN1.set('00')
Data5_CAN1 = StringVar()
e_Data5_CAN1 = Entry(tab1, textvariable=Data5_CAN1, width=3, bd=3, font=("Arial", 12))
e_Data5_CAN1.grid(row=1, column=8, padx=2, pady=1, sticky='w')
Data5_CAN1.set('00')
Data6_CAN1 = StringVar()
e_Data6_CAN1 = Entry(tab1, textvariable=Data6_CAN1, width=3, bd=3, font=("Arial", 12))
e_Data6_CAN1.grid(row=1, column=9, padx=2, pady=1, sticky='w')
Data6_CAN1.set('00')
Data7_CAN1 = StringVar()
e_Data7_CAN1 = Entry(tab1, textvariable=Data7_CAN1, width=3, bd=3, font=("Arial", 12))
e_Data7_CAN1.grid(row=1, column=10, padx=2, pady=1, sticky='w')
Data7_CAN1.set('00')
bt_send_CAN1 = Button(tab1, text='发送数据', state='disabled', font=("Arial", 12), bd=3, command=sendcan1)
bt_send_CAN1.grid(row=1, column=12, padx=2, pady=1)
bt_clear_CAN1 = Button(tab1, text='清空', font=("Arial", 12), bd=3, command=clearcan1)
bt_clear_CAN1.grid(row=2, column=12, padx=2, pady=1)

# tab2 CAN2
lb_ID_CAN2 = Label(tab2, text="ID(Hex)", bd=3, font=("Arial", 12))
lb_ID_CAN2.grid(row=0, column=0, sticky='w')
e_ID_CAN2 = Entry(tab2, bd=3, font=("Arial", 12))
e_ID_CAN2.grid(row=1, column=0, sticky='w')
e_ID_CAN2.insert(0, "00000000")
ext_CAN2 = IntVar()
cb_Ext_CAN2 = Checkbutton(tab2, text="Extended", variable=ext_CAN2, bd=3, font=("Arial", 12))
ext_CAN2.set(1)
cb_Ext_CAN2.grid(row=0, column=1, sticky='w')
rtr_CAN2 = IntVar()
cb_Rtr_CAN2 = Checkbutton(tab2, text="RTR", variable=rtr_CAN2, bd=3, font=("Arial", 12))
cb_Rtr_CAN2.grid(row=1, column=1, sticky='w')
ct_Length_CAN2 = Control(tab2, label='Length(0-8):', integer=True, max=8, min=0, value=8, step=1)
ct_Length_CAN2.grid(row=0, column=7, columnspan=4, sticky='w')
s2 = Scrollbar(tab2, orient=VERTICAL)
s2.grid(row=2, column=11, sticky='ns')
listreadcan2 = Listbox(tab2, font=("Arial", 12), height=28, width=107, yscrollcommand=s2.set)
listreadcan2.grid(row=2, column=0, columnspan=11, sticky='nw')
s2.config(command=listreadcan2.yview)
lb_Data_CAN2 = Label(tab2, text="Data(Hex)", bd=3, font=("Arial", 12))
lb_Data_CAN2.grid(row=0, column=3, columnspan=4, sticky='w')
Data0_CAN2 = StringVar()
e_Data0_CAN2 = Entry(tab2, textvariable=Data0_CAN2, width=3, bd=3, font=("Arial", 12))
e_Data0_CAN2.grid(row=1, column=3, padx=2, pady=1, sticky='w')
Data0_CAN2.set('00')
Data1_CAN2 = StringVar()
e_Data1_CAN2 = Entry(tab2, textvariable=Data1_CAN2, width=3, bd=3, font=("Arial", 12))
e_Data1_CAN2.grid(row=1, column=4, padx=2, pady=1, sticky='w')
Data1_CAN2.set('00')
Data2_CAN2 = StringVar()
e_Data2_CAN2 = Entry(tab2, textvariable=Data2_CAN2, width=3, bd=3, font=("Arial", 12))
e_Data2_CAN2.grid(row=1, column=5, padx=2, pady=1, sticky='w')
Data2_CAN2.set('00')
Data3_CAN2 = StringVar()
e_Data3_CAN2 = Entry(tab2, textvariable=Data3_CAN2, width=3, bd=3, font=("Arial", 12))
e_Data3_CAN2.grid(row=1, column=6, padx=2, pady=1, sticky='w')
Data3_CAN2.set('00')
Data4_CAN2 = StringVar()
e_Data4_CAN2 = Entry(tab2, textvariable=Data4_CAN2, width=3, bd=3, font=("Arial", 12))
e_Data4_CAN2.grid(row=1, column=7, padx=2, pady=1, sticky='w')
Data4_CAN2.set('00')
Data5_CAN2 = StringVar()
e_Data5_CAN2 = Entry(tab2, textvariable=Data5_CAN2, width=3, bd=3, font=("Arial", 12))
e_Data5_CAN2.grid(row=1, column=8, padx=2, pady=1, sticky='w')
Data5_CAN2.set('00')
Data6_CAN2 = StringVar()
e_Data6_CAN2 = Entry(tab2, textvariable=Data6_CAN2, width=3, bd=3, font=("Arial", 12))
e_Data6_CAN2.grid(row=1, column=9, padx=2, pady=1, sticky='w')
Data6_CAN2.set('00')
Data7_CAN2 = StringVar()
e_Data7_CAN2 = Entry(tab2, textvariable=Data7_CAN2, width=3, bd=3, font=("Arial", 12))
e_Data7_CAN2.grid(row=1, column=10, padx=2, pady=1, sticky='w')
Data7_CAN2.set('00')
bt_send_CAN2 = Button(tab2, text='发送数据', state='disabled', font=("Arial", 12), bd=3, command=sendcan2)
bt_send_CAN2.grid(row=1, column=12, padx=2, pady=1)
bt_clear_CAN2 = Button(tab2, text='清空', font=("Arial", 12), bd=3, command=clearcan2)
bt_clear_CAN2.grid(row=2, column=12, padx=2, pady=1)

# tab3 PowerControl
lb_add = Label(tab3, text="地址方式：", bd=3, font=("Arial", 12))
lb_add.grid(row=1, column=1, pady=5, sticky='w')
addstr = StringVar()
addstr.set("自动设址")
addcom = tkinter.ttk.Combobox(master=tab3, state="readonly", font=("Arial", 12), textvariable=addstr,
                              values=["自动设址", "拨码设址"], width=7)
addcom.grid(row=1, column=2, pady=5)
bt_add = Button(tab3, text="设", bd=3, font=("Arial", 12), command=set_add)
bt_add.grid(row=1, column=3, pady=5, sticky='w', padx=(1, 0))

lb_module = Label(tab3, text="模块地址：", bd=3, font=("Arial", 12))
lb_module.grid(row=1, column=3, pady=5, padx=(75, 0), sticky='w')
modulenumber = StringVar()
modulenumber.set("0")
modulevalues = [str(x) for x in range(0, 60)]
modulecom = tkinter.ttk.Combobox(master=tab3, state="readonly", font=("Arial", 12), textvariable=modulenumber,
                                 values=modulevalues, width=2)
modulecom.grid(row=1, column=4, pady=5)

lb_group = Label(tab3, text="模块设组：", bd=3, font=("Arial", 12))
lb_group.grid(row=1, column=5, pady=5, padx=(75, 0), sticky='w')
groupnumber = StringVar()
e_group = Entry(tab3, textvariable=groupnumber, width=5, bd=3, font=("Arial", 12))
e_group.grid(row=1, column=6, pady=5)
bt_group = Button(tab3, text="设组", font=("Arial", 12))
bt_group.grid(row=1, column=7, pady=5)

bt_m_on = Button(tab3, text="模块开机", font=("Arial", 12), command=power_on, bg="springgreen")
bt_m_on.grid(row=1, column=8, pady=5, padx=(80, 5))
bt_m_sleep = Button(tab3, text="模块休眠", font=("Arial", 12), command=power_sleep, bg="khaki")
bt_m_sleep.grid(row=1, column=9, pady=5, padx=5)
bt_m_off = Button(tab3, text="模块关机", font=("Arial", 12), command=power_off, bg="tomato")
bt_m_off.grid(row=1, column=10, pady=5, sticky='e', padx=5)

lb_m_v = Label(tab3, text="模块电压(V)：0.000", bd=3, font=("Arial", 20), width=20, fg="red")
lb_m_v.grid(row=3, column=1, columnspan=3, pady=20)
lb_m_i = Label(tab3, text="模块电流(A)：0.000", bd=3, font=("Arial", 20), width=20, fg="red")
lb_m_i.grid(row=3, column=4, columnspan=3, pady=20)

lb_m_temp = Label(tab3, text="模块温度(°C)：0", bd=3, font=("Arial", 15))
lb_m_temp.grid(row=3, column=7, pady=20, columnspan=2)
lb_m_dispgroup = Label(tab3, text="模块组号：0", bd=3, font=("Arial", 15))
lb_m_dispgroup.grid(row=3, column=9, pady=20, columnspan=2)

lb_m_acinput = Label(tab3, text="交流输入(V)：0.0", bd=3, font=("Arial", 15), width=17)
lb_m_acinput.grid(row=2, column=1, pady=10, columnspan=2, sticky='w')

lb_m_dc_vmax = Label(tab3, text="Vmax(V)：0", bd=3, font=("Arial", 12))
lb_m_dc_vmax.grid(row=2, column=3, pady=10, columnspan=2, sticky='w', padx=(80, 0))
lb_m_dc_vmin = Label(tab3, text="Vmin(V)：0", bd=3, font=("Arial", 12))
lb_m_dc_vmin.grid(row=2, column=4, pady=10, columnspan=2, sticky='w', padx=(80, 0))
lb_m_dc_imax = Label(tab3, text="Imax(A)：0.0", bd=3, font=("Arial", 12))
lb_m_dc_imax.grid(row=2, column=7, pady=10, columnspan=2, sticky='w')
lb_m_powerlimit = Label(tab3, text="Pmax(KW)：0", bd=3, font=("Arial", 12))
lb_m_powerlimit.grid(row=2, column=9, pady=10, columnspan=2, sticky='w')

spet1 = Separator(tab3, orient=HORIZONTAL)
spet1.grid(row=4, column=1, columnspan=10, sticky='ew')

lb_state = Label(tab3, text="电源状态", bd=3, font=("Arial", 18))
lb_state.grid(row=5, column=3, columnspan=2)

lb_state0 = {}
lb_state0[2] = Label(tab3, text="异常放电", bd=3, font=("Arial", 15))
lb_state0[2].grid(row=6, column=1, pady=5, columnspan=2, sticky='w')
lb_state0[3] = Label(tab3, text="休眠", bd=3, font=("Arial", 15))
lb_state0[3].grid(row=7, column=1, pady=5, columnspan=2, sticky='w')
lb_state0[4] = Label(tab3, text="输入|出母线异常", bd=3, font=("Arial", 15))
lb_state0[4].grid(row=8, column=1, pady=5, columnspan=2, sticky='w')
lb_state0[5] = Label(tab3, text="内部通信故障", bd=3, font=("Arial", 15))
lb_state0[5].grid(row=9, column=1, pady=5, columnspan=2, sticky='w')
lb_state0[7] = Label(tab3, text="输出短路", bd=3, font=("Arial", 15))
lb_state0[7].grid(row=10, column=1, pady=5, columnspan=2, sticky='w')

lb_sel0 = {}
lb_sel0[0] = Label()
lb_sel0[1] = Label()
lb_sel0[6] = Label()
lb_sel0[2] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel0[2].grid(row=6, column=1, pady=5, columnspan=2, sticky='e')
lb_sel0[3] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel0[3].grid(row=7, column=1, pady=5, columnspan=2, sticky='e')
lb_sel0[4] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel0[4].grid(row=8, column=1, pady=5, columnspan=2, sticky='e')
lb_sel0[5] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel0[5].grid(row=9, column=1, pady=5, columnspan=2, sticky='e')
lb_sel0[7] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel0[7].grid(row=10, column=1, pady=5, columnspan=2, sticky='e')

lb_state1 = {}
lb_state1[0] = Label(tab3, text="通信中断警告", bd=3, font=("Arial", 15))
lb_state1[0].grid(row=6, column=3, pady=5, columnspan=2, sticky='w', padx=(50, 0))
lb_state1[1] = Label(tab3, text="WALK-IN使能", bd=3, font=("Arial", 15))
lb_state1[1].grid(row=7, column=3, pady=5, columnspan=2, sticky='w', padx=(50, 0))
lb_state1[2] = Label(tab3, text="输出过压警告", bd=3, font=("Arial", 15))
lb_state1[2].grid(row=8, column=3, pady=5, columnspan=2, sticky='w', padx=(50, 0))
lb_state1[3] = Label(tab3, text="过温警告", bd=3, font=("Arial", 15))
lb_state1[3].grid(row=9, column=3, pady=5, columnspan=2, sticky='w', padx=(50, 0))
lb_state1[4] = Label(tab3, text="风扇故障警告", bd=3, font=("Arial", 15))
lb_state1[4].grid(row=10, column=3, pady=5, columnspan=2, sticky='w', padx=(50, 0))
lb_state1[5] = Label(tab3, text="模块保护警告", bd=3, font=("Arial", 15))
lb_state1[5].grid(row=11, column=3, pady=5, columnspan=2, sticky='w', padx=(50, 0))
lb_state1[6] = Label(tab3, text="模块故障警告", bd=3, font=("Arial", 15))
lb_state1[6].grid(row=12, column=3, pady=5, columnspan=2, sticky='w', padx=(50, 0))
lb_state1[7] = Label(tab3, text="DC侧关机", bd=3, font=("Arial", 15))
lb_state1[7].grid(row=6, column=5, pady=5, columnspan=2, sticky='w', padx=(60, 0))

lb_sel1 = {}
lb_sel1[0] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel1[0].grid(row=6, column=3, pady=5, columnspan=2, sticky='e')
lb_sel1[1] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel1[1].grid(row=7, column=3, pady=5, columnspan=2, sticky='e')
lb_sel1[2] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel1[2].grid(row=8, column=3, pady=5, columnspan=2, sticky='e')
lb_sel1[3] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel1[3].grid(row=9, column=3, pady=5, columnspan=2, sticky='e')
lb_sel1[4] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel1[4].grid(row=10, column=3, pady=5, columnspan=2, sticky='e')
lb_sel1[5] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel1[5].grid(row=11, column=3, pady=5, columnspan=2, sticky='e')
lb_sel1[6] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel1[6].grid(row=12, column=3, pady=5, columnspan=2, sticky='e')
lb_sel1[7] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel1[7].grid(row=6, column=5, pady=5, columnspan=2, sticky='e')

lb_state2 = {}
lb_state2[0] = Label(tab3, text="PFC侧关机", bd=3, font=("Arial", 15))
lb_state2[0].grid(row=7, column=5, pady=5, columnspan=2, sticky='w', padx=(60, 0))
lb_state2[1] = Label(tab3, text="输入过压警告", bd=3, font=("Arial", 15))
lb_state2[1].grid(row=8, column=5, pady=5, columnspan=2, sticky='w', padx=(60, 0))
lb_state2[2] = Label(tab3, text="输入欠压警告", bd=3, font=("Arial", 15))
lb_state2[2].grid(row=9, column=5, pady=5, columnspan=2, sticky='w', padx=(60, 0))
lb_state2[5] = Label(tab3, text="模块不均流严重", bd=3, font=("Arial", 15))
lb_state2[5].grid(row=10, column=5, pady=5, columnspan=2, sticky='w', padx=(60, 0))
lb_state2[6] = Label(tab3, text="模块ID重复", bd=3, font=("Arial", 15))
lb_state2[6].grid(row=11, column=5, pady=5, columnspan=2, sticky='w', padx=(60, 0))
lb_state2[7] = Label(tab3, text="限功率状态", bd=3, font=("Arial", 15))
lb_state2[7].grid(row=12, column=5, pady=5, columnspan=2, sticky='w', padx=(60, 0))

lb_sel2 = {}
lb_sel2[3] = Label()
lb_sel2[4] = Label()
lb_sel2[0] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel2[0].grid(row=7, column=5, pady=5, columnspan=2, sticky='e')
lb_sel2[1] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel2[1].grid(row=8, column=5, pady=5, columnspan=2, sticky='e')
lb_sel2[2] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel2[2].grid(row=9, column=5, pady=5, columnspan=2, sticky='e')
lb_sel2[5] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel2[5].grid(row=10, column=5, pady=5, columnspan=2, sticky='e')
lb_sel2[6] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel2[6].grid(row=11, column=5, pady=5, columnspan=2, sticky='e')
lb_sel2[7] = Label(tab3, width=2, bd=3, font=("Arial", 15), bg='green')
lb_sel2[7].grid(row=12, column=5, pady=5, columnspan=2, sticky='e')

spet2 = Separator(tab3, orient="vertical")
spet2.grid(row=4, column=7, rowspan=10, sticky='nse')

lb_m_set_v_i = Label(tab3, text="设置模块输出电流电压", bd=3, font=("Arial", 15))
lb_m_set_v_i.grid(row=5, column=8, pady=5, columnspan=3)
lb_m_set_v = Label(tab3, text="输出电压(V)：", bd=3, font=("Arial", 15))
lb_m_set_v.grid(row=6, column=8, pady=5)
lb_m_set_i = Label(tab3, text="输出电流(A)：", bd=3, font=("Arial", 15))
lb_m_set_i.grid(row=7, column=8, pady=5)

set_v = StringVar()
e_set_v = Entry(tab3, textvariable=set_v, width=8, bd=3, font=("Arial", 15))
e_set_v.grid(row=6, column=8, pady=5, columnspan=2, sticky='e')
set_i = StringVar()
e_set_i = Entry(tab3, textvariable=set_i, width=8, bd=3, font=("Arial", 15))
e_set_i.grid(row=7, column=8, pady=5, columnspan=2, sticky='e')

bt_m_set_v_i = Button(tab3, text="设", bd=3, font=("Arial", 20), command=set_v_i, fg="red")
bt_m_set_v_i.grid(row=6, column=10, pady=5, rowspan=2)

spet3 = Separator(tab3, orient=HORIZONTAL)
spet3.grid(row=8, column=8, columnspan=3, sticky='ew')

lb_m_limit = Label(tab3, text="软件端限流限压保护", bd=3, font=("Arial", 15))
lb_m_limit.grid(row=9, column=8, pady=5, columnspan=3)
lb_m_set_vlimit = Label(tab3, text="限制电压(V)：", bd=3, font=("Arial", 15))
lb_m_set_vlimit.grid(row=10, column=8, pady=5)
lb_m_set_ilimit = Label(tab3, text="限制电流(A)：", bd=3, font=("Arial", 15))
lb_m_set_ilimit.grid(row=11, column=8, pady=5)
set_vlimit = StringVar()
e_set_vlimit = Entry(tab3, textvariable=set_vlimit, width=12, bd=3, font=("Arial", 15))
e_set_vlimit.grid(row=10, column=9, pady=5, columnspan=2)
set_ilimit = StringVar()
e_set_ilimit = Entry(tab3, textvariable=set_ilimit, width=12, bd=3, font=("Arial", 15))
e_set_ilimit.grid(row=11, column=9, pady=5, columnspan=2)
bt_m_limit_flag = Button(tab3, text="限流限压使能", bd=3, font=("Arial", 15), command=soft_v_i)
bt_m_limit_flag.grid(row=12, column=8, pady=5, columnspan=2)
lb_m_limit_state = Label(tab3, bd=3, font=("Arial", 15), bg="gray", width=2)
lb_m_limit_state.grid(row=12, column=10, pady=5, stick='w')

spet4 = Separator(tab3, orient=HORIZONTAL)
spet4.grid(row=13, column=1, columnspan=10, sticky='esw')

lb_m_user = Label(tab3, text="其他功能", bd=3, font=("Arial", 12))
lb_m_user.grid(row=13, column=1, rowspan=2)

bt_m_led = Button(tab3, text="绿灯闪烁", font=("Arial", 18), command=led)
bt_m_led.grid(row=15, column=1, columnspan=2)
bt_m_walkin = Button(tab3, text="walk-in", font=("Arial", 18), command=wall_in)
bt_m_walkin.grid(row=15, column=3, columnspan=2)

'''
窗口保持
'''
root.mainloop()
