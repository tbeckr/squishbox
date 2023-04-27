"""
Copyright (c) 2018 Bill Peterson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

"""
Description: This file includes helpful functions for creating other applications
for your stompbox-encased Raspberry Pi (in addition to the Squishbox)
"""
import RPi.GPIO as GPIO
from adafruit_character_lcd.character_lcd_i2c import Character_LCD_I2C
import board
import time
# model/hardware dependent values for buttons, wiring, etc.
from stompboxpi_hw_overlay import *

# adjust timings below as desired
POLL_TIME=0.025
HOLD_TIME=1.0
LONG_TIME=2.0
MENU_TIMEOUT=5.0
MENU_BLINK=0.1
SCROLL_SPEED=4.0

def poll_stompswitches():
    """
    call this to check the current state of the stompswitches
    result is stored in global variables r_state and l_state
    STATE_NONE - button has not been touched in a while
    STATE_DOWN - button has held down for a short time
    STATE_TAP  - button was just released after a short hold
    STATE_HOLD - button has been held for HOLD_TIME exactly
    STATE_HELD - button has been held longer than HOLD_TIME
                    but not as long as LONG_TIME
    STATE_LONG - button has been held for LONG_TIME or more
    """
    global r_time, r_state, l_time, l_state
    if GPIO.input(BTN_R)==GPIO.LOW:
        r_time=time.time() # prevent accidental repeats
        if r_state==STATE_DOWN:
            r_state=STATE_TAP
        else:
            r_state=STATE_NONE
    else:
        if r_state==STATE_NONE:
            r_time=time.time()
            r_state=STATE_DOWN
        elif r_state==STATE_DOWN and time.time()-r_time>HOLD_TIME:
            r_state=STATE_HOLD
        elif r_state==STATE_HOLD:
            r_state=STATE_HELD
        elif r_state==STATE_HELD and time.time()-r_time>LONG_TIME:
            r_state=STATE_LONG
    if GPIO.input(BTN_L)==GPIO.LOW:
        l_time=time.time() # prevent accidental repeats
        if l_state==STATE_DOWN:
            l_state=STATE_TAP
        else:
            l_state=STATE_NONE
    else:
        if l_state==STATE_NONE:
            l_time=time.time()
            l_state=STATE_DOWN
        elif l_state==STATE_DOWN and time.time()-l_time>HOLD_TIME:
            l_state=STATE_HOLD
        elif l_state==STATE_HOLD:
            l_state=STATE_HELD
        elif l_state==STATE_HELD and time.time()-l_time>LONG_TIME:
            l_state=STATE_LONG

def waitfortap(t):
    # wait :t seconds or until a button is tapped
    e=time.time()+t
    while time.time()<e:
        time.sleep(POLL_TIME)
        poll_stompswitches()
        if r_state==STATE_TAP or l_state==STATE_TAP:
            return

def waitforrelease(tmin=0):
    # wait for a button to be released, or at least :tmin seconds
    e=time.time()+tmin
    while True:
        time.sleep(POLL_TIME)
        poll_stompswitches()
        if r_state+l_state==STATE_NONE and time.time()>=e:
            return

def lcd_clear():
    LCD.clear()
        
def lcd_message(msg,row=0,col=0):
    LCD.set_cursor(col,row)
    LCD.message(msg)

def reset_scroll():
    # call this to restart scrolling
    global scrolltime
    scrolltime=time.time()
    
def lcd_scroll(msg,row=0):
    """
    scrolls a long line of text in either row
    call frequently to update the scroll
    msg: the text to scroll
    """
    global scrolltime
    j=int((time.time()-scrolltime)*SCROLL_SPEED)
    if j<4:
        lcd_message("%-16s" % msg[:16], row)
    elif j<len(msg)-12:
        lcd_message("%-16s" % msg[j-3:j+13], row)
    elif j<len(msg)-10:
        lcd_message("%-16s" % msg[-16:], row)
    else:
        scrolltime=time.time()
        
def choose_opt(opts, row=0, scroll=False):
    """
    has the user choose from a list of choices in :opts
    returns the index of the choice
    or -1 if the user backed out or time expired
    scroll: if True, scroll long menu items and don't time out
    """
    i=0
    while True:
        if scroll:
            reset_scroll()
        else:
            lcd_message("%-16s" % opts[i],row)
        e=time.time()+MENU_TIMEOUT
        while True:
            if scroll:
                lcd_scroll(opts[i],row)
            elif time.time()>e:
                lcd_message(' '*16,row)
                return -1
            time.sleep(POLL_TIME)
            poll_stompswitches()
            if r_state+l_state==STATE_NONE:
                continue
            elif r_state==STATE_TAP:
                i=(i+1)%len(opts)
                break
            elif l_state==STATE_TAP:
                i=(i-1)%len(opts)
                break
            elif r_state==STATE_HOLD:
                for j in range(4):
                    lcd_message([' '*16,"%-16s" % opts[i]][j%2],row)
                    time.sleep(MENU_BLINK)
                return i
            elif l_state==STATE_HOLD:
                lcd_message(' '*16,row)
                return -1
        

def choose_val(val, inc, min, max, format="%16s"):
    """
    lets the user change a numeric parameter
    returns the user's choice on timeout
    """
    while True:
        lcd_message(format % val,1)
        e=time.time()+MENU_TIMEOUT
        while time.time()<e:
            time.sleep(POLL_TIME)
            poll_stompswitches()
            if r_state+l_state==STATE_NONE:
                continue
            elif r_state>STATE_DOWN:
                val+=inc
            elif l_state>STATE_DOWN:
                val-=inc
            if val>max:
                val=max
            if val<min:
                val=min
            break
        else:
            return val

def char_input(t=' ', row=1, timeout=MENU_TIMEOUT):
    """
    a way of letting the user enter a text string with two buttons
    t: the initial value of the text
    user taps buttons to choose character, holds right to advance,
     holds left to backspace
    when cursor is at end of input, user can tap to
     delete or newline character
    newline returns text
    timeout returns empty string
    """
    charvals=[32]+list(range(65,91))+list(range(97,123))+list(range(48,65))\
        +list(range(33,48))+list(range(91,97))+[123,124,125,CHR_BSP,CHR_NEW]
    i=0
    LCD.blink(True)
    while True:
        if i<len(t):
            c=charvals.index(ord(t[i]))
        x=max(i-15,0)
        lcd_message("%-16s" % t[x:x+16],row)
        LCD.set_cursor(min(i,15),row)
        LCD.message(chr(charvals[c]))
        LCD.set_cursor(min(i,15),row)
        e=time.time()+timeout
        while time.time()<e:
            time.sleep(POLL_TIME)
            poll_stompswitches()
            if r_state+l_state==STATE_NONE:
                continue
            elif r_state==STATE_TAP or l_state==STATE_TAP:
                if i==len(t):
                    if r_state==STATE_TAP:
                        c=(c+1)%len(charvals)
                    else:
                        c=(c-1)%len(charvals)
                else:
                    if r_state==STATE_TAP:
                        c=(c+1)%(len(charvals)-2)
                    else:
                        c=(c-1)%(len(charvals)-2)
                if c<len(charvals)-2:
                    t=t[0:i]+chr(charvals[c])+t[i+1:]
                break
            elif r_state==STATE_HOLD or r_state==STATE_LONG:
                if charvals[c]==CHR_NEW and r_state==STATE_HOLD:
                    LCD.blink(False)
                    for j in range(4):
                        lcd_message([' '*16,"%-16s" % t.strip()[0:16]][j%2],row)
                        time.sleep(MENU_BLINK)
                    return t.strip()
                i=min(i+1,len(t))
                if i==len(t):
                    c=len(charvals)-1
                break
            elif l_state==STATE_HOLD or l_state==STATE_LONG:
                if charvals[c]==CHR_BSP:
                    t=t[0:max(0,i-1)]+t[i:]
                i=max(i-1,0)
                break
        else:
            LCD.blink(False)
            return ''

STATE_NONE=0
STATE_DOWN=1
STATE_TAP=2
STATE_HOLD=3
STATE_HELD=4
STATE_LONG=5
            
scrolltime=time.time()
r_time=0
r_state=0
l_time=0
l_state=0

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(BTN_L, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BTN_R, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
i2c = board.I2C()
LCD = Character_LCD_I2C(i2c, 16, 2)

CHR_BSP=0
CHR_NEW=1
LCD.create_char(CHR_BSP,[0,3,5,9,5,3,0,0])
LCD.create_char(CHR_NEW,[0,16,20,18,31,2,4,0])
